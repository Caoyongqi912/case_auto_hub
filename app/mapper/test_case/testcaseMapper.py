#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/27
# @Author : cyq
# @File : testcaseMapper
# @Software: PyCharm
# @Desc: 测试用例数据访问层
from re import L
from typing import List, Dict, Any, Optional, Sequence

from sqlalchemy import select, insert, update, and_, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper, set_creator
from app.mapper.test_case.requirementMapper import RequirementMapper
from app.mapper.test_case.testCaseStepMapper import TestCaseStepMapper
from app.mapper.test_case.caseDynamicMapper import CaseDynamicMapper
from app.model import async_session
from app.model.base import User
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.test_case_step import TestCaseStep
from app.model.caseHub.association import RequirementCaseAssociation
from utils import log
from sqlalchemy.ext.asyncio import AsyncSession


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
    async def case_info(cls,case_id:int):
        """
        获取指定用例的详细信息，包括步骤

        :param case_id: 用例ID
        :return: 用例详细信息字典
        """

        try:
            async with async_session() as session:
                case = await cls.get_by_id(ident=case_id, session=session)
                case_steps = await TestCaseStepMapper.query_sub_steps(case_id=case_id, session=session)
                return {
                    **case.to_dict(),
                    "case_sub_steps": case_steps,
                }
        except Exception as e:
            log.error(f"case_info error: case_id={case_id}, error={e}")
            raise

    @classmethod
    async def update_cases_common(cls, case_ids: List[int], project_id: int, module_id: int):
        """
        批量将用例设为公共用例库

        :param case_ids: 用例ID列表
        :param project_id: 目标项目ID
        :param module_id: 目标模块ID
        """
        try:
            async with cls.transaction() as session:
                await session.execute(
                    update(cls.__model__)
                    .where(cls.__model__.id.in_(case_ids))
                    .values(
                        is_common=True,
                        project_id=project_id,
                        module_id=module_id,
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
            async with cls.transaction() as session:

                stmt = select(RequirementCaseAssociation).where(
                    getattr(RequirementCaseAssociation, "case_id").in_(case_ids))
                ass = await session.scalars(stmt)
                for ass_obj in ass:
                    await CaseDynamicMapper.update_dynamic(
                        case_id=ass_obj.case_id,
                        old_case={"case_status": ass_obj.case_status},
                        new_case={"case_status": status},
                        session=session,
                        cr=user
                    )

                await session.execute(
                    update(RequirementCaseAssociation)
                    .where(RequirementCaseAssociation.case_id.in_(case_ids))
                    .values(case_status=status)
                )
        except Exception as e:
            log.error(f"update_cases_status error: case_ids={case_ids}, status={status}, error={e}")
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
            async with cls.transaction() as session:
                stmt = select(RequirementCaseAssociation).where(
                    getattr(RequirementCaseAssociation, "case_id").in_(case_ids))
                ass = await session.scalars(stmt)
                for ass_obj in ass:
                    await CaseDynamicMapper.update_dynamic(
                        case_id=ass_obj.case_id,
                        old_case={"is_review": ass.is_review},
                        new_case={"is_review": is_review},
                        session=session,
                        cr=user
                    )
                await session.execute(
                    update(RequirementCaseAssociation)
                    .where(RequirementCaseAssociation.case_id.in_(case_ids))
                    .values(is_review=is_review)
                )
        except Exception as e:
            log.error(f"update_cases_review error: case_ids={case_ids}, is_review={is_review}, error={e}")
            raise

    @classmethod
    async def insert_upload_case(
            cls,
            cases: List[Dict[str, Any]],
            project_id: int,
            module_id: int,
            user: User,
            requirement_id: Optional[int] = None,
            is_common: bool = True,
    ) -> int:
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
        :param is_common: 公共
        :return: 导入的用例数量
        """
        if not cases:
            return 0

        log.info(f"开始导入用例，共 {len(cases)} 条")
        async with cls.transaction() as session:
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
                    "creator": user.id,
                    "creatorName": user.username,
                    "is_common": is_common,
                })

                case_objects.append(cls.__model__(**case_data))
                log.debug(f"case_objects {case_objects}")
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
                            order=last_order,
                            is_review=False,
                            case_type=case_data.get("case_type", None),
                            case_status=case_data.get("case_status", None),
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

            log.info(f"成功导入用例 {len(case_objects)} 条")
            return len(case_objects)

    @staticmethod
    def _map_step_id(step_data: Dict[str, Any], case_id_map: Dict[int, int]) -> Dict[str, Any]:
        """将步骤的临时索引替换为实际用例ID"""
        case_index = step_data.pop("test_case_index")
        step_data["test_case_id"] = case_id_map[case_index]
        return step_data

    @classmethod
    async def remove_case(cls, caseId: int, requirement_id: Optional[int]):
        """
        删除测试用例

        :param caseId: 用例ID
        :param requirement_id: 需求ID（可选，用于更新需求用例数量）
        """
        try:
            async with cls.transaction() as session:
                case_obj: TestCase = await cls.get_by_id(ident=caseId, session=session)

                if case_obj.is_common and requirement_id:
                    req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                    if req.case_number > 0:
                        req.case_number -= 1
                    await session.execute(
                        delete(RequirementCaseAssociation).where(
                            and_(
                                RequirementCaseAssociation.requirement_id == requirement_id,
                                RequirementCaseAssociation.case_id == caseId
                            )
                        )
                    )
                else:
                    await session.execute(
                        delete(cls.__model__).where(cls.__model__.id == caseId)
                    )
        except Exception as e:
            log.error(f"remove_case error: caseId={caseId}, requirement_id={requirement_id}, error={e}")
            raise

    @classmethod
    async def query_case_by_field(cls, requirement_id: int, **kwargs):
        """
        根据条件过滤查询用例

        :param requirement_id: 需求ID
        :param kwargs: 过滤条件
            - TestCase字段: case_name, case_tag
            - RequirementCaseAssociation字段: is_review, case_status, case_type, case_level
        :return: 符合条件的用例列表（包含关联表的 is_review 和 case_status）
        """
        ASSOCIATION_FIELDS = {'is_review', 'case_status', 'case_type', 'case_level'}

        case_filters = {k: v for k, v in kwargs.items() if k not in ASSOCIATION_FIELDS}
        association_filters = {k: v for k, v in kwargs.items() if k in ASSOCIATION_FIELDS}

        try:
            async with async_session() as session:
                case_conditions = await cls.search_conditions(**case_filters)

                query = (
                    select(TestCase,
                           RequirementCaseAssociation.is_review,
                           RequirementCaseAssociation.case_status,
                           RequirementCaseAssociation.case_type,
                           RequirementCaseAssociation.case_level)
                    .join(RequirementCaseAssociation, RequirementCaseAssociation.case_id == TestCase.id)
                    .where(RequirementCaseAssociation.requirement_id == requirement_id)
                )

                if case_conditions:
                    query = query.where(and_(*case_conditions))

                for field_name, value in association_filters.items():
                    if hasattr(RequirementCaseAssociation, field_name):
                        field = getattr(RequirementCaseAssociation, field_name)
                        if value is None:
                            query = query.where(field.is_(None))
                        elif isinstance(value, (int, float, bool)):
                            query = query.where(field == value)
                        elif isinstance(value, str):
                            query = query.where(field == value)

                query = query.order_by(RequirementCaseAssociation.order)

                result = await session.execute(query)
                rows = result.all()

                return [
                    {
                        **(row[0].to_dict()),
                        "is_review": row[1],
                        "case_status": row[2],
                        "case_type": row[3],
                        "case_level": row[4],

                    }
                    for row in rows
                ]

        except Exception as e:
            log.exception(f"query_case_by_field error: requirement_id={requirement_id}, kwargs={kwargs}, error={e}")
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
                    .where(
                        RequirementCaseAssociation.requirement_id == requirement_id,
                        TestCase.case_tag.isnot(None)
                    )
                )
                all_tags = tags.all()
                log.info(all_tags)
                return set(all_tags) if all_tags else []
        except Exception as e:
            log.error(f"query_tags error: requirement_id={requirement_id}, error={e}")
            raise

    @classmethod
    async def save_case(cls, user: User, requirement_id: Optional[int] = None, **kwargs):
        """
        创建测试用例及其步骤

        :param user: 创建者用户
        :param requirement_id: 关联的需求ID（可选）
        :param kwargs: 用例字段数据
        :return: 创建的用例对象
        """
        case_sub_steps = kwargs.pop("case_sub_steps", [])

        kwargs = set_creator(user, **kwargs)

        try:
            async with cls.transaction() as session:
                case_obj: TestCase = await cls.save(session=session, **kwargs)

                if case_sub_steps:
                    steps = [TestCaseStep(
                        **i,
                        test_case_id=case_obj.id,
                        creator=user.id,
                        creatorName=user.username
                    )  for i in case_sub_steps]
                    session.add_all(steps)

                if requirement_id:
                    await insert_requirement_case(
                        session=session,
                        requirement_id=requirement_id,
                        case_id=case_obj.id
                    )
       
                await CaseDynamicMapper.new_dynamic(
                    cr=user,
                    test_case=case_obj,
                    session=session
                )

                return case_obj
        except Exception as e:
            log.error(f"save_case error: kwargs={kwargs}, error={e}")
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
            async with cls.transaction() as session:
                case_obj = await cls.get_by_id(ident=kwargs.get("id"), session=session)
                old_data = case_obj.map
                kwargs.pop("id", None)
                new_case = await cls.update_cls(case_obj, session, **kwargs)

                await CaseDynamicMapper.update_dynamic(
                    cr=ur,
                    case_id=case_obj.id,
                    old_case=old_data,
                    new_case=new_case.map,
                    session=session
                )
        except Exception as e:
            log.error(f"update_case error: kwargs={kwargs}, error={e}")
            raise

    @classmethod
    async def copy_cases(cls, case_ids: List[int], user: User, requirement_id: Optional[int]=None, session: Optional[AsyncSession]=None):
        """
        复制用例及其步骤

        :param case_ids: 被复制的源用例ID列表
        :param user: 操作用户
        :param requirement_id: 目标需求ID（可选）
        :param session: 异步会话（可选）
        :return: 复制的用例对象
        """
        try:
            async with cls.session_scope(session) as session:
                source_cases = await cls.query_by_in_clause("id", case_ids, session)

                source_steps_map = {}
                if source_cases:
                    steps_result = await session.execute(
                        select(TestCaseStep)
                        .where(TestCaseStep.test_case_id.in_(case_ids))
                        .order_by(TestCaseStep.order)
                    )
                    all_steps = steps_result.scalars().all()
                    for step in all_steps:
                        source_steps_map.setdefault(step.test_case_id, []).append(step)

                source_order_map = {}
                if requirement_id and source_cases:
                    order_result = await session.execute(
                        select(
                            RequirementCaseAssociation.case_id,
                            RequirementCaseAssociation.order
                        ).where(
                            and_(
                                RequirementCaseAssociation.requirement_id == requirement_id,
                                RequirementCaseAssociation.case_id.in_(case_ids)
                            )
                        )
                    )
                    for row in order_result.all():
                        source_order_map[row.case_id] = row.order

                new_case_list = []
                for source_case in source_cases:
                    new_case_data = source_case.copy_map()
                    new_case_data["case_name"] += " - 副本"
                    new_case_data["creator"] = user.id
                    new_case_data["creatorName"] = user.username
                    new_case_model = TestCase(**new_case_data)

                    steps = source_steps_map.get(source_case.id, [])
                    new_case_model.case_sub_steps = [
                        TestCaseStep(
                            **{
                                **step.copy_map(),
                                "test_case_id": new_case_model.id,
                                "creator": user.id,
                                "creatorName": user.username
                            }
                        )
                        for step in steps
                    ]
                    new_case_list.append(new_case_model)

                session.add_all(new_case_list)
                await session.flush()

                if requirement_id and source_cases:
                    req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                    req.case_number += len(new_case_list)

                    max_order_result = await session.execute(
                        select(func.max(RequirementCaseAssociation.order))
                        .where(RequirementCaseAssociation.requirement_id == requirement_id)
                    )
                    max_order = max_order_result.scalar() or 0

                    assoc_values = [
                        {
                            "requirement_id": requirement_id,
                            "case_id": new_case_obj.id,
                            "order": max_order + idx + 1
                        }
                        for idx, new_case_obj in enumerate(new_case_list)
                    ]
                    await session.execute(insert(RequirementCaseAssociation).values(assoc_values))

                for new_case_obj in new_case_list:
                    await CaseDynamicMapper.new_dynamic(
                        cr=user,
                        test_case=new_case_obj,
                        session=session
                    )

                return new_case_list
        except Exception as e:
            log.error(f"copy_cases error: case_ids={case_ids}, requirement_id={requirement_id}, error={e}")
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
            async with cls.transaction() as session:
                req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                current_case = await cls.get_by_id(ident=case_id, session=session)

                new_case = await cls._copy_case_data(
                    source=current_case,
                    user=user,
                    session=session
                )

                req.case_number += 1
                await cls.add_flush_expunge(session=session, model=new_case)
        except Exception as e:
            log.error(f"add_next_case error: requirement_id={requirement_id}, case_id={case_id}, error={e}")
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
            async with cls.transaction() as session:
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
            log.error(f"add_default_case error: requirement_id={requirement_id}, error={e}")
            raise
        
