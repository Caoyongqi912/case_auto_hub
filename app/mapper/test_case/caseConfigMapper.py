#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : caseConfigMapper
# @Software: PyCharm
# @Desc: 用例枚举配置数据访问层
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.exception import CommonError, ParamsError
from app.mapper import Mapper, set_updater
from app.model.base import User
from app.constant.caseStatus import CASE_STATUS_KEY
from app.model.caseHub.case_config import CaseConfig
from utils import log


class CaseConfigMapper(Mapper[CaseConfig]):
    """
    用例枚举配置 Mapper

    业务约束：
    - 同一 ``(config_key, value)`` 组合在业务上必须唯一。
    - 同 config_key 下的多条记录通过 sort 字段排序展示。
    """
    __model__ = CaseConfig

    @classmethod
    async def page_config(
        cls,
        current: int,
        pageSize: int,
        config_key: Optional[str] = None,
        keyword: Optional[str] = None,
        sort: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        分页查询用例枚举配置

        :param current: 当前页码（从 1 开始）
        :param pageSize: 每页条数
        :param config_key: 按配置键精确过滤
        :param keyword: 模糊匹配 label / description
        :param sort: 排序信息，如 {"sort": "ascend"}，默认按 sort asc, id asc
        :return: 包含 items / total / pages / page / limit 的分页字典
        """
        try:
            async with cls.transaction() as session:
                conditions = []

                if config_key:
                    conditions.append(CaseConfig.config_key == config_key)

                if keyword:
                    like = f"%{keyword.strip()}%"
                    conditions.append(
                        or_(
                            CaseConfig.label.like(like),
                            CaseConfig.description.like(like),
                        )
                    )

                base_query = select(CaseConfig)
                if conditions:
                    base_query = base_query.where(and_(*conditions))

                # 1. 统计总数
                count_stmt = select(func.count()).select_from(CaseConfig)
                if conditions:
                    count_stmt = count_stmt.where(and_(*conditions))
                total = (await session.execute(count_stmt)).scalar() or 0

                # 2. 排序
                sort_field = (sort or {}).get("sort", "ascend")
                order_col = (
                    CaseConfig.sort.asc() if sort_field != "descend"
                    else CaseConfig.sort.desc()
                )
                base_query = base_query.order_by(order_col, CaseConfig.id.asc())

                # 3. 分页
                offset = (current - 1) * pageSize
                rows = (
                    await session.execute(base_query.offset(offset).limit(pageSize))
                ).scalars().all()

                return await cls.map_page_data(list(rows), total, pageSize, current)
        except Exception as err:
            log.exception(
                "page_config error: config_key=%s, keyword=%s, error=%s",
                config_key, keyword, err,
            )
            raise

    @classmethod
    async def query_by_key(
        cls,
        config_key: str,
        enabled_only: bool = True,
        session: Optional[AsyncSession] = None,
    ) -> List[CaseConfig]:
        """
        根据 config_key 全量查询配置项

        :param config_key: 配置键
        :param enabled_only: 是否只查询启用的配置，默认 True
        :return: 按 sort 升序排序的 CaseConfig 列表
        """
        try:
            async with cls.session_scope(session) as session:
                stmt = select(CaseConfig).where(CaseConfig.config_key == config_key)
                if enabled_only:
                    stmt = stmt.where(CaseConfig.enabled.is_(True))
                stmt = stmt.order_by(CaseConfig.sort.asc(), CaseConfig.id.asc())
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as err:
            log.exception(f"query_by_key error: config_key={config_key}, error={err}")
            raise

    @classmethod
    async def add_config(cls, user: User, **kwargs: Any) -> CaseConfig:
        """
        新增枚举配置

        业务校验：同一 ``config_key`` 下 ``value`` 值必须唯一。

        :param user: 操作用户（用于写入 creator / creatorName）
        :param kwargs: ICaseEnumConfig 字段
        :return: 新建的 CaseConfig 实例

        :raises CommonError: 当 ``(config_key, value)`` 组合已存在时
        :raises ParamsError: 当 ``config_key`` 或 ``value`` 为空时
        """
        config_key = kwargs.get("config_key")
        value = kwargs.get("value")
        if not config_key or not value:
            raise ParamsError("config_key 和 value 不能为空")
        # CASE_STATUS 已 hardcode, 不允许通过配置中心新增/修改/删除
        if config_key == CASE_STATUS_KEY:
            raise ParamsError("CASE_STATUS 已 hardcode, 不支持新增; 如需调整请修改 app/constant/caseStatus.py")

        try:
            async with cls.transaction() as session:
                await cls._assert_value_unique(
                    session=session, config_key=config_key, value=value,
                )
                return await cls.save(
                    creator_user=user, session=session, **kwargs,
                )
        except (CommonError, ParamsError):
            raise
        except Exception as err:
            log.exception(f"add_config error: kwargs={kwargs}, error={err}")
            raise

    @classmethod
    async def update_config(cls, user: User, **kwargs: Any) -> CaseConfig:
        """
        通过 uid 更新枚举配置（仅更新传入的字段）

        业务校验：当 ``config_key`` 或 ``value`` 实际发生变更时，
        同一 ``config_key`` 下 ``value`` 值必须唯一。

        :param user: 操作用户
        :param kwargs: 必须包含 uid，其余字段可选
        :return: 更新后的 CaseConfig 实例

        :raises CommonError: 当 ``(config_key, value)`` 已被其他记录占用时
        :raises ParamsError: 当 ``uid`` 为空时
        """
        uid = kwargs.get("uid")
        if not uid:
            raise ParamsError("uid 不能为空")

        # 防御层：value 字段在业务上一旦创建不可修改
        # - UpdateCaseConfigSchema 不会再带出 value
        # - 即便调用方手动塞入（直接调用 mapper / 旧调用方未升级），
        #   此处也忽略并记录告警，避免 value 被静默修改
        if "value" in kwargs:
            log.warning(
                "CaseConfig value 字段在更新时被忽略: uid=%s, value=%s",
                uid, kwargs["value"],
            )
            kwargs.pop("value", None)

        try:
            async with cls.transaction() as session:
                target = await cls.get_by_uid(
                    uid=uid, session=session, raise_error=True,
                )

                # CASE_STATUS 已 hardcode, 不允许通过配置中心修改
                if target.config_key == CASE_STATUS_KEY:
                    raise ParamsError("CASE_STATUS 已 hardcode, 不支持修改; 如需调整请修改 app/constant/caseStatus.py")
                # 防御: 阻止把其他 config_key 改成 CASE_STATUS
                new_key = kwargs.get("config_key", target.config_key)
                if new_key == CASE_STATUS_KEY:
                    raise ParamsError("CASE_STATUS 已 hardcode, 不支持通过 update 切到该 key")

                # 合并新旧值：未传入则沿用旧值
                new_key = kwargs.get("config_key", target.config_key)
                new_value = kwargs.get("value", target.value)

                # 只有在 key / value 真正变化时才校验唯一性（性能优化）
                if new_key != target.config_key or new_value != target.value:
                    await cls._assert_value_unique(
                        session=session,
                        config_key=new_key,
                        value=new_value,
                        exclude_uid=uid,
                    )

                # 应用更新（剥离 uid，避免被写入 update_cls 触发 "无效列" 警告）
                update_fields = {k: v for k, v in kwargs.items() if k != "uid"}
                update_fields = set_updater(user, **update_fields)
                return await cls.update_cls(target, session, **update_fields)
        except (CommonError, ParamsError):
            raise
        except Exception as err:
            log.exception(f"update_config error: kwargs={kwargs}, error={err}")
            raise

    @classmethod
    async def remove_config(cls, uid: str) -> None:
        """
        通过 uid 删除枚举配置

        :param uid: 配置项唯一标识
        :raises ParamsError: 当 uid 对应记录的 config_key 为 CASE_STATUS (已 hardcode)
        """
        # CASE_STATUS 已 hardcode, 删除前先查 target. config_key 命中则拒绝.
        try:
            target = await cls.get_by_uid(uid=uid, raise_error=True)
        except (CommonError, ParamsError):
            raise
        except Exception as err:
            log.exception(f"remove_config 预查失败: uid=%s, error=%s", uid, err)
            raise
        if target.config_key == CASE_STATUS_KEY:
            raise ParamsError("CASE_STATUS 已 hardcode, 不支持删除; 如需调整请修改 app/constant/caseStatus.py")
        try:
            await cls.delete_by_uid(uid=uid)
        except Exception as err:
            log.exception(f"remove_config error: uid=%s, error=%s", uid, err)
            raise

    @classmethod
    async def init_case_configs(cls, configs: List[Dict[str, Any]]) -> None:
        """
        批量初始化用例枚举配置数据

        :param configs: 配置字典列表，每项包含 config_key/label/value/color/description/sort/enabled
        """
        try:
            async with cls.transaction() as session:
                await session.execute(
                    insert(cls.__model__).values(configs)
                )
        except Exception as e:
            log.exception(f"init_case_configs error: {e}")
            raise

    @classmethod
    async def _assert_value_unique(
        cls,
        session: AsyncSession,
        config_key: str,
        value: str,
        exclude_uid: Optional[str] = None,
    ) -> None:
        """
        断言同一 ``(config_key, value)`` 组合在业务上唯一

        私有辅助方法：在新增和更新场景下复用，避免重复 SQL 逻辑。

        :param session: 当前事务会话
        :param config_key: 配置键
        :param value: 配置值
        :param exclude_uid: 更新场景下排除自身 uid（避免误判）
        :raises CommonError: 当组合已存在时
        """
        conditions = [
            CaseConfig.config_key == config_key,
            CaseConfig.value == value,
        ]
        if exclude_uid is not None:
            conditions.append(CaseConfig.uid != exclude_uid)

        count_stmt = (
            select(func.count())
            .select_from(CaseConfig)
            .where(and_(*conditions))
        )
        count = (await session.execute(count_stmt)).scalar() or 0
        if count > 0:
            log.warning(
                "CaseConfig value 冲突: config_key=%s, value=%s, exclude_uid=%s",
                config_key, value, exclude_uid,
            )
            raise CommonError(
                message=f"配置组【{config_key}】下已存在 value={value} 的配置项，请勿重复添加"
            )
