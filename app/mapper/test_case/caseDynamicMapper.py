#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/27
# @Author : cyq
# @File : caseDynamicMapper
# @Software: PyCharm
# @Desc: 测试用例动态记录数据访问层
from typing import Dict, Any, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.case_step_dynamic import CaseStepDynamic
from utils import log


IGNORE_KEYS = {"id", "uid", "create_time", "update_time", "creator", "creatorName", "updater", "updaterName"}


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
    FIELD_CONFIG_KEY_MAP: Dict[str, str] = {
        "case_type": "CASE_TYPE",
        "case_level": "CASE_LEVEL",
        "case_status": "CASE_STATUS",
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

    @classmethod
    async def from_db(cls, session: AsyncSession) -> "CaseDynamicRenderer":
        """
        从 CaseConfig 表加载所有枚举配置，构建渲染器实例。

        :param session: 数据库会话；为 None 时创建临时会话
        :return: 持有最新配置的渲染器实例
        """
        from app.mapper.test_case.caseConfigMapper import CaseConfigMapper

        mappings: Dict[str, Dict[Any, str]] = {}
        config_keys = list(cls.FIELD_CONFIG_KEY_MAP.values())

        try:
            rows = []
            for key in config_keys:
                try:
                    rows.extend(await CaseConfigMapper.query_by_key(key, session=session))
                except Exception as err:
                    log.warning("CaseDynamicRenderer 加载 config_key=%s 失败: %s", key, err)
            for row in rows:
                config_key = row.config_key
                mappings.setdefault(config_key, {})[row.value] = row.label
        except Exception as err:
            log.error("CaseDynamicRenderer.from_db 加载失败，将使用空映射: %s", err)

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

            if old_value == new_value:
                continue

            field_name = self.KEY_MAP.get(key, key)
            old_display = self.transform_value(key, old_value)
            new_display = self.transform_value(key, new_value)

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

        :param old_data: 变更前的数据（仅变更字段）
        :param new_data: 变更后的数据（仅变更字段）
        :return: 变更描述字符串，如果无变更则返回 None
        """
        diff_args: list[str] = []
        changed_keys = set(old_data.keys()) & set(new_data.keys())

        for key in changed_keys:
            old_value = old_data.get(key)
            new_value = new_data.get(key)

            if old_value == new_value:
                continue

            field_name = self.PLAN_ASSOCIATION_KEY_MAP.get(key, key)
            old_display = self.transform_value(key, old_value)
            new_display = self.transform_value(key, new_value)

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
            async with async_session() as session:
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
            log.error("query_dynamic error: case_id=%s, error=%s", case_id, e)
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
