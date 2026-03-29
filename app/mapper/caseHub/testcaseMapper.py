#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/27
# @Author : cyq
# @File : testcaseMapper
# @Software: PyCharm
# @Desc: 测试用例数据访问层
from typing import List, Dict, Any, Optional, Sequence

from sqlalchemy import select, insert, update, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.mapper.caseHub.requirementMapper import RequirementMapper
from app.mapper import Mapper, set_creator
from app.model import async_session
from app.model.base import User
from app.model.caseHub.caseHUB import TestCase, TestCaseStep, CaseStepDynamic
from app.model.caseHub.association import RequirementCaseAssociation
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


def diff_dict(old_case: Dict[str, Any], new_case: Dict[str, Any]) -> Optional[str]:
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


async def get_last_index(session: AsyncSession, requirement_id: int) -> int:
    """
    获取指定需求下用例的最大排序序号

    :param session: 数据库会话
    :param requirement_id: 需求ID
    :return: 最大排序序号，如果不存在则返回0
    """
    stmt = (
        select(RequirementCaseAssociation.order)
        .where(RequirementCaseAssociation.requirement_id == requirement_id)
        .order_by(RequirementCaseAssociation.order.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_case_index(session: AsyncSession, requirement_id: int, case_id: int) -> Optional[int]:
    """
    获取指定用例在需求下的排序序号

    :param session: 数据库会话
    :param requirement_id: 需求ID
    :param case_id: 用例ID
    :return: 排序序号
    """
    stmt = (
        select(RequirementCaseAssociation.order)
        .where(
            and_(
                RequirementCaseAssociation.requirement_id == requirement_id,
                RequirementCaseAssociation.case_id == case_id,
            )
        )
    )
    result = await session.execute(stmt)
    return result.scalar()


async def insert_requirement_case(session: AsyncSession, requirement_id: int, case_id: int):
    """
    将用例关联到需求，并更新需求的用例数量

    :param session: 数据库会话
    :param requirement_id: 需求ID
    :param case_id: 用例ID
    """
    last_order = await get_last_index(session, requirement_id)
    await session.execute(
        insert(RequirementCaseAssociation).values(
            requirement_id=requirement_id,
            case_id=case_id,
            order=last_order + 1
        )
    )
    req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
    req.case_number += 1


def _parse_steps(action: Optional[str], expected_result: Optional[str]) -> List[Dict[str, Optional[str]]]:
    """
    将按行分割的操作步骤和预期结果解析为步骤列表

    :param action: 操作步骤文本（按换行分割）
    :param expected_result: 预期结果文本（按换行分割）
    :return: 步骤字典列表
    """
    if action is None and expected_result is None:
        return [{"action": None, "expected_result": None}]

    act_lines = action.strip().split("\n") if action else None
    exp_lines = expected_result.strip().split("\n") if expected_result else None
    max_steps = max(len(act_lines) if act_lines else 0, len(exp_lines) if exp_lines else 0)

    return [
        {
            "action": act_lines[i] if act_lines and i < len(act_lines) else None,
            "expected_result": exp_lines[i] if exp_lines and i < len(exp_lines) else None,
        }
        for i in range(max_steps)
    ]


class TestCaseMapper(Mapper[TestCase]):
    __model__ = TestCase

    @classmethod
    async def update_cases_common(cls, case_ids: List[int], project_id: int, module_id: int):
        """
        批量将用例设为公共用例库

        :param case_ids: 用例ID列表
        :param project_id: 目标项目ID
        :param module_id: 目标模块ID
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    await session.execute(
                        update(cls.__model__)
                        .where(cls.__model__.id.in_(case_ids))
                        .values(
                            is_common=True,
                            project_id=project_id,
                            module_id=module_id,
                            case_status=0,
                            is_review=True,
                        )
                    )
        except Exception as e:
            log.error(e)
            raise

    @classmethod
    async def update_cases_status(cls, case_ids: List[int], status: int, user: User):
        """
        批量更新用例状态，并记录变更动态

        :param case_ids: 用例ID列表
        :param status: 目标状态
        :param user: 操作用户
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    for case_id in case_ids:
                        case_obj: TestCase = await cls.get_by_id(ident=case_id, session=session)
                        await CaseDynamicMapper.update_dynamic(
                            case_id=case_id,
                            old_case={"case_status": case_obj.case_status},
                            new_case={"case_status": status},
                            session=session,
                            cr=user
                        )

                    await session.execute(
                        update(cls.__model__)
                        .where(cls.__model__.id.in_(case_ids))
                        .values(case_status=status)
                    )
        except Exception as e:
            raise

    @classmethod
    async def update_cases_review(cls, case_ids: List[int], is_review: bool, user: User):
        """
        批量更新用例状态评审，并记录变更动态

        :param case_ids: 用例ID列表
        :param is_review: 是否评审
        :param user: 操作用户
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    for case_id in case_ids:
                        case_obj: TestCase = await cls.get_by_id(ident=case_id, session=session)
                        await CaseDynamicMapper.update_dynamic(
                            case_id=case_id,
                            old_case={"is_review": case_obj.is_review},
                            new_case={"is_review": is_review},
                            session=session,
                            cr=user
                        )

                    await session.execute(
                        update(cls.__model__)
                        .where(cls.__model__.id.in_(case_ids))
                        .values(reis_review=is_review)
                    )
        except Exception as e:
            raise

    @classmethod
    async def insert_upload_case(
            cls,
            cases: List[Dict[str, Any]],
            project_id: int,
            module_id: int,
            user: User,
            requirement_id: Optional[int] = None,
    ):
        """
        从Excel批量导入用例

        处理流程：
        1. 批量插入用例记录
        2. 解析步骤并关联到用例
        3. 关联需求（如有）并更新需求用例数量
        4. 记录用例动态

        :param cases: 用例数据列表
        :param project_id: 项目ID
        :param module_id: 模块ID
        :param requirement_id: 需求ID（可选）
        :param user: 操作用户
        """
        if not cases:
            return

        log.info(f"开始导入用例，共 {len(cases)} 条")
        try:
            async with async_session() as session:
                async with session.begin():
                    case_objects = []
                    all_steps = []
                    requirement_associations = []
                    last_order = await get_last_index(session, requirement_id) if requirement_id else 0

                    for case_index, case_data in enumerate(cases):
                        action = case_data.pop("action", None)
                        expected_result = case_data.pop("expected_result", None)

                        case_data.update({
                            "project_id": project_id,
                            "module_id": module_id,
                            "case_type": 2,
                            "case_status": 0,
                            "creator": user.id,
                            "creatorName": user.username,
                        })

                        case_objects.append(cls.__model__(**case_data))

                        steps = _parse_steps(action, expected_result)
                        for step_index, step_data in enumerate(steps):
                            step_data.update({
                                "test_case_index": case_index,
                                "order": step_index,
                                "creator": user.id,
                                "creatorName": user.username,
                            })
                            all_steps.append(step_data)

                        if requirement_id:
                            last_order += 1
                            requirement_associations.append(
                                RequirementCaseAssociation(
                                    requirement_id=requirement_id,
                                    case_id=case_index,
                                    order=last_order
                                )
                            )

                    session.add_all(case_objects)
                    await session.flush()

                    case_id_map = {i: case_obj.id for i, case_obj in enumerate(case_objects)}

                    step_objects = [
                        TestCaseStepMapper.__model__(**cls._map_step_id(step_data, case_id_map))
                        for step_data in all_steps
                    ]
                    session.add_all(step_objects)

                    if requirement_associations:
                        for assoc in requirement_associations:
                            assoc.case_id = case_id_map[assoc.case_id]
                        session.add_all(requirement_associations)

                        req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                        req.case_number += len(case_objects)

        except Exception as e:
            raise

    @staticmethod
    def _map_step_id(step_data: Dict[str, Any], case_id_map: Dict[int, int]) -> Dict[str, Any]:
        """将步骤的临时索引替换为实际用例ID"""
        case_index = step_data.pop("test_case_index")
        step_data["test_case_id"] = case_id_map[case_index]
        return step_data

    @classmethod
    async def remove_case(cls, case_id: int, requirement_id: Optional[int]):
        """
        删除测试用例

        :param case_id: 用例ID
        :param requirement_id: 需求ID（可选，用于更新需求用例数量）
        """
        try:
            async with async_session() as session:
                case_obj: TestCase = await cls.get_by_id(ident=case_id, session=session)

                if case_obj.is_common and requirement_id:
                    req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                    if req.case_number > 0:
                        req.case_number -= 1
                    await session.execute(
                        delete(RequirementCaseAssociation).where(
                            and_(
                                RequirementCaseAssociation.requirement_id == requirement_id,
                                RequirementCaseAssociation.case_id == case_id
                            )
                        )
                    )
                else:
                    await session.execute(
                        delete(cls.__model__).where(cls.__model__.id == case_id)
                    )

                await session.commit()
        except Exception as e:
            raise

    @classmethod
    async def query_by_req(cls, requirement_id: int):
        """
        根据需求ID查询所有关联用例

        :param requirement_id: 需求ID
        :return: 用例列表
        """
        try:
            async with async_session() as session:
                cases = await session.scalars(
                    select(TestCase)
                    .join(RequirementCaseAssociation, RequirementCaseAssociation.case_id == TestCase.id)
                    .where(RequirementCaseAssociation.requirement_id == requirement_id)
                    .order_by(RequirementCaseAssociation.order)
                )
                return cases.all()
        except Exception as e:
            raise

    @classmethod
    async def query_case_by_field(cls, requirement_id: int, **kwargs):
        """
        根据条件过滤查询用例

        :param requirement_id: 需求ID
        :param kwargs: 过滤条件
        :return: 符合条件的用例列表
        """
        try:
            async with async_session() as session:
                conditions = await cls.search_conditions(**kwargs)
                cases = await session.scalars(
                    select(TestCase)
                    .join(RequirementCaseAssociation, RequirementCaseAssociation.case_id == TestCase.id)
                    .where(RequirementCaseAssociation.requirement_id == requirement_id)
                    .where(and_(*conditions))
                    .order_by(RequirementCaseAssociation.order)
                )
                return cases.all()
        except Exception as e:
            raise

    @classmethod
    async def query_tags(cls, requirement_id: int):
        """
        获取需求下所有用例的标签集合

        :param requirement_id: 需求ID
        :return: 标签集合
        """
        try:
            async with async_session() as session:
                tags = await session.scalars(
                    select(TestCase.case_tag)
                    .join(RequirementCaseAssociation, RequirementCaseAssociation.case_id == TestCase.id)
                    .where(RequirementCaseAssociation.requirement_id == requirement_id)
                )
                return set(tags.all())
        except Exception as e:
            raise

    @classmethod
    async def save_case(cls, cr: User, requirement_id: Optional[int] = None, **kwargs):
        """
        创建测试用例及其步骤

        :param cr: 创建者用户
        :param requirement_id: 关联的需求ID（可选）
        :param kwargs: 用例字段数据
        :return: 创建的用例对象
        """
        case_sub_steps = kwargs.pop("case_sub_steps", [])
        kwargs = set_creator(cr, **kwargs)

        try:
            async with async_session() as session:
                async with session.begin():
                    case_obj: TestCase = await cls.save(session=session, **kwargs)

                    if case_sub_steps:
                        await TestCaseStepMapper.save_steps(
                            case_id=case_obj.id,
                            steps=case_sub_steps,
                            user=cr,
                            session=session
                        )

                    if requirement_id:
                        await insert_requirement_case(
                            session=session,
                            requirement_id=requirement_id,
                            case_id=case_obj.id
                        )

                    await CaseDynamicMapper.new_dynamic(
                        cr=cr,
                        test_case=case_obj,
                        session=session
                    )

                    return case_obj
        except Exception as e:
            raise

    @classmethod
    async def update_case(cls, ur: User, **kwargs):
        """
        更新测试用例信息，并记录变更动态

        :param ur: 更新者用户
        :param kwargs: 更新字段数据（必须包含id）
        """
        log.info(f"更新用例参数: {kwargs}")

        try:
            async with async_session() as session:
                async with session.begin():
                    case_obj = await cls.get_by_id(ident=kwargs.get("id"), session=session)
                    old_data = case_obj.map
                    new_case = await cls.update_cls(case_obj, session, **kwargs)

                    await CaseDynamicMapper.update_dynamic(
                        cr=ur,
                        case_id=case_obj.id,
                        old_case=old_data,
                        new_case=new_case.map,
                        session=session
                    )
        except Exception as e:
            raise

    @classmethod
    async def query_sub_steps(cls, case_id: int):
        """
        查询用例的所有步骤

        :param case_id: 用例ID
        :return: 步骤列表
        """
        try:
            async with async_session() as session:
                steps = await session.scalars(
                    select(TestCaseStep)
                    .where(TestCaseStep.test_case_id == case_id)
                    .order_by(TestCaseStep.order)
                )
                return steps.all()
        except Exception as e:
            raise

    @classmethod
    async def copy_case(cls, case_id: int, user: User, requirement_id: Optional[int]):
        """
        复制用例及其步骤到指定需求

        :param case_id: 被复制的源用例ID
        :param user: 操作用户
        :param requirement_id: 目标需求ID（可选）
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    source_case: TestCase = await cls.get_by_id(ident=case_id, session=session)
                    source_steps: Sequence[TestCaseStep] = await TestCaseStepMapper.query_steps_by_case_id(
                        case_id=source_case.id,
                        session=session
                    )

                    new_case_data = source_case.copy_map()
                    new_case_data["case_name"] += " - 副本"
                    new_case_data["case_status"] = 0
                    new_case_data["creator"] = user.id
                    new_case_data["creatorName"] = user.username

                    new_case_obj = await cls.save(session=session, **new_case_data)

                    for step in source_steps:
                        new_step_data = step.copy_map()
                        new_step_data["test_case_id"] = new_case_obj.id
                        new_step_data["creator"] = user.id
                        new_step_data["creatorName"] = user.username
                        await TestCaseStepMapper.save(session=session, **new_step_data)

                    if requirement_id:
                        req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                        req.case_number += 1

                        source_order = await get_case_index(session, requirement_id, source_case.id)

                        await session.execute(
                            update(RequirementCaseAssociation)
                            .where(
                                and_(
                                    RequirementCaseAssociation.requirement_id == requirement_id,
                                    RequirementCaseAssociation.order > source_order
                                )
                            )
                            .values(order=RequirementCaseAssociation.order + 1)
                        )

                        await session.execute(
                            insert(RequirementCaseAssociation).values(
                                requirement_id=requirement_id,
                                case_id=new_case_obj.id,
                                order=source_order + 1
                            )
                        )

                    await CaseDynamicMapper.new_dynamic(
                        cr=user,
                        test_case=new_case_obj,
                        session=session
                    )
        except Exception as e:
            raise

    @classmethod
    async def add_next_case(cls, requirement_id: int, case_id: int, user: User):
        """
        在当前用例后快速创建下一条用例（复制）

        :param requirement_id: 需求ID
        :param case_id: 当前用例ID
        :param user: 操作用户
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                    current_case = await cls.get_by_id(ident=case_id, session=session)

                    new_case = await cls._copy_case_data(
                        source=current_case,
                        user=user,
                        session=session
                    )

                    req.case_number += 1
                    await cls.add_flush_expunge(session=session, model=new_case)
        except Exception:
            raise

    @classmethod
    async def _copy_case_data(cls, source: TestCase, user: User, session: AsyncSession) -> TestCase:
        """
        复制用例数据（内部方法）

        :param source: 源用例对象
        :param user: 操作用户
        :param session: 数据库会话
        :return: 新的用例对象
        """
        new_data = source.copy_map()
        new_data["case_name"] += " - 副本"
        new_data["case_status"] = 0
        new_data["creator"] = user.id
        new_data["creatorName"] = user.username
        return await cls.save(session=session, **new_data)

    @classmethod
    async def add_default_case(cls, requirement_id: int, user: User):
        """
        在需求下添加一条默认模板用例

        :param requirement_id: 需求ID
        :param user: 操作用户
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                    req.case_number += 1

                    new_case = TestCase()
                    await new_case.set_default(user)
                    new_case.module_id = req.module_id
                    new_case.project_id = req.project_id

                    await cls.add_flush_expunge(session=session, model=new_case)

                    last_order = await get_last_index(session, requirement_id)
                    await session.execute(
                        insert(RequirementCaseAssociation).values(
                            requirement_id=requirement_id,
                            case_id=new_case.id,
                            order=last_order + 1
                        )
                    )
        except Exception as e:
            raise


class TestCaseStepMapper(Mapper[TestCaseStep]):
    __model__ = TestCaseStep

    @classmethod
    async def update_step(cls, user: User, id: int, **kwargs):
        """
        更新用例步骤，并记录变更动态

        :param user: 操作用户
        :param id: 步骤ID
        :param kwargs: 更新字段
        """
        log.info(f"更新步骤 {id}")
        log.debug(f"更新参数 {kwargs}")

        try:
            async with async_session() as session:
                async with session.begin():
                    step = await cls.get_by_id(ident=id, session=session)
                    before_info = {
                        "action": step.action,
                        "expected_result": step.expected_result
                    }

                    new_step = await cls.update_cls(step, session, **kwargs)
                    after_info = {
                        "action": new_step.action,
                        "expected_result": new_step.expected_result
                    }

                    await CaseDynamicMapper.update_dynamic(
                        cr=user,
                        case_id=new_step.test_case_id,
                        old_case=before_info,
                        new_case=after_info,
                        session=session
                    )
        except Exception:
            raise

    @classmethod
    async def reorder_steps(cls, step_ids: List[int]):
        """
        批量重排序用例步骤

        :param step_ids: 步骤ID列表（新的排序顺序）
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    for index, step_id in enumerate(step_ids, start=1):
                        await session.execute(
                            update(TestCaseStep)
                            .where(TestCaseStep.id == step_id)
                            .values(order=index)
                        )
        except Exception as e:
            raise

    @classmethod
    async def copy_step(cls, step_id: int, user: User):
        """
        复制指定步骤

        :param step_id: 被复制的步骤ID
        :param user: 操作用户
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    step: TestCaseStep = await cls.get_by_id(ident=step_id, session=session)

                    await session.execute(
                        update(TestCaseStep)
                        .where(
                            and_(
                                TestCaseStep.test_case_id == step.test_case_id,
                                TestCaseStep.order > step.order
                            )
                        )
                        .values(order=TestCaseStep.order + 1)
                    )

                    new_step_data = step.copy_map()
                    new_step_data["creator"] = user.id
                    new_step_data["creatorName"] = user.username
                    new_step_data["order"] = step.order + 1

                    await cls.save(session=session, **new_step_data)
        except Exception as e:
            raise

    @classmethod
    async def add_default_step(cls, caseId: int, user: User):
        """
        为用例添加一条默认空步骤

        :param caseId: 用例ID
        :param user: 操作用户
        """
        try:
            async with async_session() as session:
                last_order = await cls.get_last_order(case_id=caseId, session=session)

                session.add(
                    cls.__model__(
                        test_case_id=caseId,
                        order=last_order + 1,
                        creator=user.id,
                        creatorName=user.username
                    )
                )
                await session.commit()
        except Exception:
            raise

    @classmethod
    async def save_steps(cls, case_id: int, steps: List[Dict[str, Any]], session: AsyncSession, user: User):
        """
        批量保存用例步骤

        :param case_id: 用例ID
        :param steps: 步骤数据列表
        :param session: 数据库会话
        :param user: 操作用户
        """
        try:
            for index, step_data in enumerate(steps):
                step_data["test_case_id"] = case_id
                step_data["order"] = index
                step_data["creator"] = user.id
                step_data["creatorName"] = user.username
                await cls.save(session=session, **step_data)
        except Exception as e:
            raise

    @classmethod
    async def query_steps_by_case_id(cls, case_id: int, session: AsyncSession) -> Sequence[TestCaseStep]:
        """
        查询用例的所有步骤

        :param case_id: 用例ID
        :param session: 数据库会话
        :return: 步骤列表
        """
        try:
            steps = await session.scalars(
                select(TestCaseStep)
                .where(TestCaseStep.test_case_id == case_id)
                .order_by(TestCaseStep.order)
            )
            return steps.all()
        except Exception as e:
            raise

    @staticmethod
    async def get_last_order(case_id: int, session: AsyncSession) -> int:
        """
        获取用例的最大步骤排序号

        :param case_id: 用例ID
        :param session: 数据库会话
        :return: 最大排序号，不存在则返回0
        """
        stmt = (
            select(TestCaseStep.order)
            .where(TestCaseStep.test_case_id == case_id)
            .order_by(TestCaseStep.order.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar() or 0


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
