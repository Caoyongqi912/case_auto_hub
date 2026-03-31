#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/27
# @Author : cyq
# @File : caseDynamicMapper
# @Software: PyCharm
# @Desc: 测试用例动态记录数据访问层
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.caseHub.caseHUB import TestCase, CaseStepDynamic
from utils import log


IGNORE_KEYS = {"id", "uid", "create_time", "update_time", "creator", "creatorName", "updater", "updaterName"}

KEY_MAP = {
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

VALUE_MAPPINGS = {
    "case_type": {1: "冒烟", 2: "普通"},
    "case_status": {1: "成功", 2: "失败", 0: "待执行"},
    "is_review": {True: "已评审", False: "未评审"}
}


def _transform_value(field_key: str, value: Any) -> str:
    """
    根据字段类型转换值的显示格式

    :param field_key: 字段名
    :param value: 字段值
    :return: 可读的字符串表示
    """
    if value is None:
        return "空"

    if field_key in VALUE_MAPPINGS and value in VALUE_MAPPINGS[field_key]:
        return VALUE_MAPPINGS[field_key][value]

    if isinstance(value, list):
        return "、".join(str(v) for v in value) if value else "空"

    if isinstance(value, bool):
        return "是" if value else "否"

    return str(value)


def diff_dict(old_case: Dict[str, Any], new_case: Dict[str, Any]) -> str | None:
    """
    比较两个字典的差异，生成变更描述

    :param old_case: 变更前的用例数据
    :param new_case: 变更后的用例数据
    :return: 变更描述字符串，如果无变更则返回None
    """
    all_keys = set(old_case.keys()) | set(new_case.keys())
    relevant_keys = all_keys - IGNORE_KEYS
    diff_args = []

    for key in relevant_keys:
        old_value = old_case.get(key)
        new_value = new_case.get(key)

        if old_value == new_value:
            continue

        field_name = KEY_MAP.get(key, key)
        old_display = _transform_value(key, old_value)
        new_display = _transform_value(key, new_value)

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
    async def query_dynamic(cls, case_id: int):
        """
        获取用例的变更动态记录

        :param case_id: 用例ID
        :return: 动态记录列表
        """
        try:
            async with async_session() as session:
                dynamics = await session.scalars(
                    select(CaseStepDynamic)
                    .where(CaseStepDynamic.test_case_id == case_id)
                    .order_by(CaseStepDynamic.create_time.asc())
                )
                return dynamics.all()
        except Exception as e:
            log.error(f"query_dynamic error: case_id={case_id}, error={e}")
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
            creator=cr.id,
            creatorName=cr.username
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
        diff_info = diff_dict(old_case, new_case)
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
