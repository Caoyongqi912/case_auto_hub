#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/27
# @Author : cyq
# @File : caseDynamicMapper
# @Software: PyCharm
# @Desc: 测试用例动态记录数据访问层
from typing import Dict, Any, Optional
from app.constant.caseStatus import BUILTIN_CASE_STATUS_LABEL_MAP, CASE_STATUS_KEY

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model.base import User
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.case_step_dynamic import CaseStepDynamic
from utils import log


# 系统 / 业务关系字段: 用例编辑场景 (M1 update_step / M2 commit) 不应该出现在
# dynamic 描述里.
# - id / uid / create_time / update_time / creator / creatorName / updater / updaterName
#   元数据 (主键 / 时间戳 / 审计人)
# - is_common: "是否入库" 标志, 是后台入库动作产物, 不是用例编辑产物
# - module_id: "所属模块", 改 = 挪目录, 是用例管理动作, 不是用例编辑
# - project_id: "所属项目", 跨项目不应该走用例编辑
# 任何 "M2 导回只能改 Excel 9 列" 的诉求都依赖此集合覆盖.
IGNORE_KEYS = {
    "id", "uid", "create_time", "update_time",
    "creator", "creatorName", "updater", "updaterName",
    "is_common", "module_id", "project_id",
}


class CaseDynamicRenderer:
    """
    用例变更动态渲染器，持有枚举配置映射（从 CaseConfig 表加载）。

    将字段值转换为可读文本、比较字典差异并生成变更描述。
    实例级隔离，无全局状态，便于测试和按需刷新。

    用法::

        renderer = await CaseDynamicRenderer.from_db(session=session)
        diff_info = renderer.diff_dict(old_data, new_data)
    """

    # 字段名 → 中文显示名（用例自身字段）
    KEY_MAP: Dict[str, str] = {
        "action": "操作步骤",
        "expected_result": "预期结果",
        "case_name": "用例名称",
        "case_level": "用例等级",
        "case_type": "用例类型",
        "case_tag": "用例标签",
        "case_setup": "前置条件",
        "case_status": "用例状态",
        "case_mark": "用例描述",
        "is_review": "是否审核",
        "case_platform": "适用端",
    }

    # 字段名 → 中文显示名（计划关联字段）
    PLAN_ASSOCIATION_KEY_MAP: Dict[str, str] = {
        "is_review": "是否审核",
        "case_status": "用例状态",
        "first_status": "一轮测试状态",
        "second_status": "二轮测试状态",
        "actual_result": "实际结果",
        "bug_url": "缺陷链接",
    }

    # 字段名 → CaseConfig.config_key 的映射
    # CASE_STATUS 已被 hardcode (见 BUILTIN_CASE_STATUS_LABEL_MAP), 不再从 case_config 加载.
    # 这里保留字段映射, 让 _resolve_config_key 仍能识别 first/second/case_status 是枚举字段.
    FIELD_CONFIG_KEY_MAP: Dict[str, str] = {
        "case_type": "CASE_TYPE",
        "case_level": "CASE_LEVEL",
        "case_status": "CASE_STATUS",
        "case_platform": "PLATFORM",
        "is_review": "IS_REVIEW",
        "first_status": "CASE_STATUS",
        "second_status": "CASE_STATUS",
    }

    def __init__(self, value_mappings: Optional[Dict[str, Dict[Any, str]]] = None):
        """
        :param value_mappings: 字段名 -> {原始值: 显示文本} 的映射；
                               为 None 时 transform_value 对枚举字段 fallback 到 str(value)
        """
        self._value_mappings = value_mappings or {}

    # 不走 case_config 表的 config_key. 这些枚举 hardcode 在代码层.
    # 见 app/constant/caseStatus.py.
    _HARDCODED_CONFIG_KEYS = frozenset({CASE_STATUS_KEY})

    @classmethod
    async def from_db(cls, session: AsyncSession) -> "CaseDynamicRenderer":
        """
        从 CaseConfig 表加载枚举配置, 构建渲染器实例.

        CASE_STATUS 走 hardcode 常量 (BUILTIN_CASE_STATUS_LABEL_MAP), 不查 DB.
        其余 config_key 仍走 case_config 表, 允许 admin 改 label / color.

        :param session: 数据库会话; 为 None 时创建临时会话
        :return: 持有最新配置的渲染器实例
        """
        from app.mapper.test_case.caseConfigMapper import CaseConfigMapper

        mappings: Dict[str, Dict[Any, str]] = {}
        # CASE_STATUS 不走 DB, 提前注入 hardcode 映射
        mappings[CASE_STATUS_KEY] = dict(BUILTIN_CASE_STATUS_LABEL_MAP)

        # 过滤掉 hardcode 的 key, 只查 DB 里的
        config_keys = [
            k for k in cls.FIELD_CONFIG_KEY_MAP.values()
            if k not in cls._HARDCODED_CONFIG_KEYS
        ]

        if config_keys:
            try:
                rows = []
                for key in config_keys:
                    try:
                        rows.extend(await CaseConfigMapper.query_by_key(key, session=session))
                    except Exception as err:
                        log.warning("CaseDynamicRenderer 加载 config_key=%s 失败: %s", key, err)
                log.debug(f"CaseDynamicRenderer 加载 {len(rows)} 条 CaseConfig 记录 {rows}")
                for row in rows:
                    config_key = row.config_key
                    mappings.setdefault(config_key, {})[row.value] = row.label
            except Exception as err:
                log.exception(f"CaseDynamicRenderer.from_db 加载失败, 将使用 hardcode + 空映射: %s", err)
        return cls(mappings)

    def _resolve_config_key(self, field_key: str) -> Optional[str]:
        """根据字段名查找对应的 CaseConfig config_key"""
        return self.FIELD_CONFIG_KEY_MAP.get(field_key)

    def transform_value(self, field_key: str, value: Any) -> str:
        """
        根据字段类型转换值的显示格式。

        优先从 DB 配置映射取值，未命中时按类型降级处理。
        该方法为同步调用，不产生 IO。

        :param field_key: 字段名
        :param value: 字段值
        :return: 可读的字符串表示
        """
        if value is None:
            return "空"

        # 优先从 CaseConfig 加载的映射中查找
        config_key = self._resolve_config_key(field_key)
        if config_key and config_key in self._value_mappings:
            mapping = self._value_mappings[config_key]
            str_value = str(value)
            if str_value in mapping:
                return mapping[str_value]

        if isinstance(value, list):
            return "、".join(str(v) for v in value) if value else "空"

        if isinstance(value, bool):
            return "是" if value else "否"

        return str(value)

    def diff_dict(self, old_case: Dict[str, Any], new_case: Dict[str, Any]) -> Optional[str]:
        """
        比较两个字典的差异，生成变更描述（用例自身字段）。

        比较走 display form (transform_value) 而非 raw，避免 raw != raw 但
        display == display 的假阳性 (典型场景: M2 导回时 DB 历史值是枚举
        code 如 'GN'，Excel 解析回 label '功能测试'，二者实际未变).

        :param old_case: 变更前的用例数据
        :param new_case: 变更后的用例数据
        :return: 变更描述字符串，如果无变更则返回 None
        """
        all_keys = set(old_case.keys()) | set(new_case.keys())
        relevant_keys = all_keys - IGNORE_KEYS
        diff_args: list[str] = []

        for key in relevant_keys:
            old_value = old_case.get(key)
            new_value = new_case.get(key)

            # 两侧都为空: 无变更
            if old_value is None and new_value is None:
                continue

            field_name = self.KEY_MAP.get(key, key)
            old_display = self.transform_value(key, old_value)
            new_display = self.transform_value(key, new_value)

            # display form 一致: 无变更 (覆盖 raw 不等但 label 相同的枚举场景)
            if old_display == new_display:
                continue

            if old_value is None:
                diff_args.append(f"{field_name} 新增 {new_display}")
            elif new_value is None:
                diff_args.append(f"{field_name} 从 {old_display} 变更为 空")
            else:
                diff_args.append(f"{field_name} 从 {old_display} 变更为 {new_display}")

        return "\n".join(diff_args) if diff_args else None

    def diff_plan_case_dict(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Optional[str]:
        """
        比较计划关联用例的变更，生成变更描述。

        比较走 display form (transform_value) 而非 raw，理由同 diff_dict。

        :param old_data: 变更前的数据（仅变更字段）
        :param new_data: 变更后的数据（仅变更字段）
        :return: 变更描述字符串，如果无变更则返回 None
        """
        diff_args: list[str] = []
        changed_keys = set(old_data.keys()) & set(new_data.keys())

        for key in changed_keys:
            old_value = old_data.get(key)
            new_value = new_data.get(key)
            log.debug(f"diff_plan_case_dict key={key}, old_value={old_value}, new_value={new_value}")
            
            if old_value is None and new_value is None:
                continue

            field_name = self.PLAN_ASSOCIATION_KEY_MAP.get(key, key)
            
            old_display = self.transform_value(key, old_value)
            new_display = self.transform_value(key, new_value)

            if old_display == new_display:
                continue

            if old_value is None:
                diff_args.append(f"{field_name} 新增 {new_display}")
            elif new_value is None:
                diff_args.append(f"{field_name} 从 {old_display} 变更为 空")
            else:
                diff_args.append(f"{field_name} 从 {old_display} 变更为 {new_display}")

        return "\n".join(diff_args) if diff_args else None


class CaseDynamicMapper(Mapper[CaseStepDynamic]):
    __model__ = CaseStepDynamic

    @classmethod
    async def query_dynamic(cls, case_id: int, plan_id: Optional[int] = None):
        """
        获取用例的变更动态记录

        :param case_id: 用例ID
        :param plan_id: 计划ID（可选，为None时只查用例自身变更，非None时同时查该计划的变更）
        :return: 动态记录列表
        """
        try:
            async with cls.session_scope() as session:
                conditions = [CaseStepDynamic.test_case_id == case_id]
                if plan_id is not None:
                    conditions.append(
                        or_(
                            CaseStepDynamic.plan_id.is_(None),
                            CaseStepDynamic.plan_id == plan_id
                        )
                    )
                else:
                    conditions.append(CaseStepDynamic.plan_id.is_(None))

                dynamics = await session.scalars(
                    select(CaseStepDynamic)
                    .where(and_(*conditions))
                    .order_by(CaseStepDynamic.create_time.desc())
                )
                return dynamics.all()
        except Exception as e:
            log.exception(f"query_dynamic error: case_id=%s, error=%s", case_id, e)
            raise

    @classmethod
    async def new_dynamic(cls, cr: User, test_case: TestCase, session: AsyncSession):
        """
        记录用例创建动态

        :param cr: 创建者用户
        :param test_case: 创建的用例对象
        :param session: 数据库会话
        """
        await cls.save(
            session=session,
            description=f"{cr.username} 创建了测试用例。 {test_case.case_name}",
            test_case_id=test_case.id,
            creator_user=cr,
        )

    @classmethod
    async def update_dynamic(
            cls,
            cr: User,
            case_id: int,
            old_case: Dict[str, Any],
            new_case: Dict[str, Any],
            session: AsyncSession
    ):
        """
        记录用例更新动态

        :param cr: 更新者用户
        :param case_id: 用例ID
        :param old_case: 更新前数据
        :param new_case: 更新后数据
        :param session: 数据库会话
        """
        renderer = await CaseDynamicRenderer.from_db(session=session)
        diff_info = renderer.diff_dict(old_case, new_case)
        if not diff_info:
            return

        session.add(
            CaseStepDynamic(
                description=f"{cr.username} 更新了测试用例 :{diff_info}",
                test_case_id=case_id,
                creator=cr.id,
                creatorName=cr.username
            )
        )
        await session.flush()

    @classmethod
    async def update_plan_case_dynamic(
            cls,
            cr: User,
            plan_id: int,
            plan_name: str,
            case_id: int,
            old_data: Dict[str, Any],
            new_data: Dict[str, Any],
            session: AsyncSession
    ):
        """
        记录计划关联用例的更新动态

        :param cr: 更新者用户
        :param plan_id: 计划ID
        :param plan_name: 计划名称
        :param case_id: 用例ID
        :param old_data: 更新前数据（仅包含变更字段）
        :param new_data: 更新后数据（仅包含变更字段）
        :param session: 数据库会话
        """
        renderer = await CaseDynamicRenderer.from_db(session=session)
        diff_info = renderer.diff_plan_case_dict(old_data, new_data)
        if not diff_info:
            return

        session.add(
            CaseStepDynamic(
                description=f"{cr.username} 更新了计划【{plan_name}】中的用例 :{diff_info}",
                test_case_id=case_id,
                plan_id=plan_id,
                creator=cr.id,
                creatorName=cr.username
            )
        )
        await session.flush()


# ============================================================
# PR-3 Step 3 新增 (M2 导回 commit 用, 见 PLAN.md Step 3 段)
# ============================================================

class M2CaseDynamicWriter:
    """
    PR-3 Step 3: M2 导回 commit 时用的动态写入工具 (跟 update_dynamic 不同, 接受
    已经渲染好的 description 字符串, 不在这里算 diff).

    跟 update_dynamic 的差异:
    - update_dynamic 接受 old_case / new_case, 内部调 CaseDynamicRenderer.diff_dict 算
      变更描述. 适合"FE 提交 case_id + 字段改动"这种走 controller 的场景.
    - write_case_dynamic (M2) 接受已经渲染好的 description, 适合"BE 内部
      M2ImportService 走 RoundtripReader 拿到 valid_cases, 自己渲染 diff 后
      写入"这种内部链路.

    共用同一个 CaseStepDynamic model, 字段语义跟 update_dynamic 一致:
    - test_case_id: 必填, 用例 ID
    - plan_id: 传 None (用例自身变更, 跟 update_dynamic 一致)
    - description: 必填, 已经是渲染好的可读文本 (跟 update_dynamic 输出格式一致)
    - creator / creatorName: 来自 User 对象
    """

    @staticmethod
    async def write_case_dynamic(
        cr: User,
        case_id: int,
        description: str,
        session: AsyncSession,
        plan_id: Optional[int] = None,
    ) -> None:
        """
        写入用例变更动态 (M2 导回 commit 专用).

        :param cr: 更新者用户
        :param case_id: 用例 ID
        :param description: 渲染好的可读变更描述 (例如 "用例等级 从 P1 变更为 P2")
        :param session: 数据库会话 (事务由调用方控制)
        :param plan_id: 计划 ID (用例自身变更传 None, 默认)
        """
        if not description:
            return
        session.add(
            CaseStepDynamic(
                description=f"{cr.username} 更新了测试用例 :{description}",
                test_case_id=case_id,
                plan_id=plan_id,
                creator=cr.id,
                creatorName=cr.username,
            )
        )
        # 不 flush, 留给调用方的事务统一 commit; 跟 update_dynamic 的语义一致
