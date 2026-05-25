#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planCaseMapper
# @Software: PyCharm
# @Desc: 计划用例关联数据访问层
from typing import List, Optional

from app.mapper.test_case.testcaseMapper import TestCaseMapper
from sqlalchemy import insert, update, delete, select, and_, or_, func
from sqlalchemy.orm import selectinload
from app.model.caseHub.test_case_step import TestCaseStep
from app.mapper.test_case.caseDynamicMapper import CaseDynamicMapper

from app.mapper import Mapper, set_creator
from app.model.base import User
from app.model.caseHub.association import PlanCaseAssociation, PlanRequirementAssociation
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.requirement import Requirement
from app.model.caseHub.plan_module import PlanModule
from app.model.caseHub.test_case_step import TestCaseStepResult
from sqlalchemy.ext.asyncio import AsyncSession
from utils import log


async def get_last_order(plan_id: int, session: AsyncSession) -> int:
    """
    获取用例的最大步骤排序号

    :param plan_id: 计划ID
    :param session: 数据库会话
    :return: 最大排序号，不存在则返回0
    """
    stmt = (
        select(PlanCaseAssociation.order)
        .where(PlanCaseAssociation.plan_id == plan_id)
        .order_by(PlanCaseAssociation.order.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


class PlanCaseMapper(Mapper[PlanCaseAssociation]):
    __model__ = PlanCaseAssociation

    @classmethod
    async def insert_plan_case(cls,user:User,plan_id:int,plan_module_id:int,**kwargs):
        """
        添加计划关联的用例
        :param user: 认证用户
        :param plan_id: 计划ID
        :param plan_module_id: 计划分组ID
        :param kwargs: 其他用例关联属性
        :return: 创建的关联记录
        """
        case_sub_steps = kwargs.pop("case_sub_steps", [])

        kwargs = set_creator(user, **kwargs)
        kwargs['is_common'] = True

        try:
            async with cls.transaction() as session:
                case_obj: TestCase = await TestCaseMapper.save(session=session, **kwargs)
                if case_sub_steps:
                    steps = [TestCaseStep(
                        **i,
                        test_case_id=case_obj.id,
                        creator=user.id,
                        creatorName=user.username
                    )  for i in case_sub_steps]
                    session.add_all(steps)
                await cls.associate_cases(
                    plan_id=plan_id,
                    plan_module_id=plan_module_id,
                    case_ids=[case_obj.id],
                    session=session
                )

                await CaseDynamicMapper.new_dynamic(
                    cr=user,
                    test_case=case_obj,
                    session=session
                )
                return case_obj
        except Exception as e:
            raise e
    
    @classmethod
    async def update_case_step_result(cls,plan_id:int,step_id:int,actual_result:Optional[str]=None,status:Optional[int]=None,bug_url:Optional[str]=None):
        """ 更新计划用例步骤结果

        Args:
            plan_id (int): 计划ID
            step_id (int): 用例步骤ID
            actual_result (Optional[str], optional): 实际结果. Defaults to None.
            status (Optional[int], optional): 用例状态 0:未填写 1:通过 2:阻塞 3:跳过 4:其他. Defaults to None.
            bug_url (Optional[str], optional): 缺陷链接. Defaults to None.

        """
        try:
            async with cls.transaction() as session:
                result = TestCaseStepResult(
                    plan_id=plan_id,
                    step_id=step_id,
                    actual_result=actual_result,
                    status=status,
                    bug_url=bug_url
                )
                session.add(result)
        except Exception as e:
            raise e
    
    @classmethod
    async def update_case(cls,plan_id:int,case_id_list:List[int],user:User,is_review:Optional[int]=None,case_status:Optional[int]=None):
        """
        更新计划用例关联的属性

        Args:
            plan_id (int): 计划ID
            user (User): 认证用户
            case_id_list (List[int]): 用例ID列表
            is_review (Optional[int], optional): 是否审核. Defaults to None.
            case_status (Optional[int], optional): 用例状态 0:未开始 1:通过 2:失败.. Defaults to None.
        """
        try:
            async with cls.transaction() as session:
                values = {}
                if is_review is not None:
                    values["is_review"] = is_review
                if case_status is not None:
                    values["case_status"] = case_status
                
                if not values:
                    return 0
                stmt = update(PlanCaseAssociation).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id, 
                        PlanCaseAssociation.case_id.in_(case_id_list),
                    )
                ).values(values)
                await session.execute(stmt)
                return len(case_id_list)
        except Exception as e:
            raise e
    @classmethod
    async def copy_plan_case(cls,case_id:int,plan_id:int,plan_module_id:int,user:User):
        
        """
        复制单个计划用例  

        Raises:
            e: _description_
            e: _description_

        Returns:
            _type_: _description_
        """
        try:
            async with cls.transaction() as session:
                #查询就用例所在索引order
                stmt = (
                        select(PlanCaseAssociation.order)
                        .where(and_(
                            PlanCaseAssociation.plan_id == plan_id,
                            PlanCaseAssociation.case_id == case_id
                               ))
                        .order_by(PlanCaseAssociation.order.desc())
                        .limit(1)
                    )
                result = await session.execute(stmt)
                case_order = result.scalar() or 0
                                
                new_cases = await TestCaseMapper.copy_cases(
                    case_ids=[case_id],
                    user=user,
                    session=session
                )
                if not new_cases:
                    return 0
                else:
                    new_case = new_cases[0]
                    await cls.associate_cases(
                        plan_id=plan_id,
                        case_ids=[new_case.id],
                        plan_module_id=plan_module_id,
                        order=case_order + 1,
                        session=session
                    )
                return 1
        except Exception as e:
            log.error(e)
            raise e
    
        
    @classmethod
    async def copy_cases(cls,case_id_list:List[int],plan_id:int,plan_case_module_id:int,user:User,is_review:bool=False):
        """
        复制计划用例到新的分组

        Args:
            case_id_list (List[int]): 用例ID列表
            plan_id (int): 计划ID
            plan_case_module_id (int): 计划分组ID
            is_review (bool): 是否审核

        Raises:
            e: _description_

        Returns:
            _type_: _description_
        """
        try:
            async with cls.transaction() as session:
                # 查询用例
                new_cases = await TestCaseMapper.copy_cases(
                    case_ids=case_id_list,
                    user=user,
                    session=session
                )
                if not new_cases:
                    return 0
                
                new_case_ids = [case.id for case in new_cases]
                
                await cls.associate_cases(
                    plan_id=plan_id,
                    case_ids=new_case_ids,
                    plan_module_id=plan_case_module_id,
                    session=session,
                    is_review=is_review
                )
                return len(new_case_ids)
        except Exception as e:
            raise e
    
    @classmethod
    async def move_case(
        cls,
        case_id_list: List[int],
        plan_id: int,
        plan_case_module_id: int,
    ) -> int:
        """
        移动计划用例到新的分组
        如果仍是当前plan、只是更新plan module则只更新module，不移动用例
        如果是其他plan则移动用例到新的plan关联下。
        :param case_id_list: 用例ID列表
        :param plan_id: 计划ID
        :param plan_case_module_id: 计划分组ID
        :return: 移动数量
        """
        if not case_id_list:
            return 0
        try:
            async with cls.transaction() as session:
                stmt = select(PlanCaseAssociation).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_id.in_(case_id_list)
                    )
                )
                result = await session.execute(stmt)
                existing_data = result.scalars().all()
                
                if existing_data:
                    update_stmt = (
                        update(PlanCaseAssociation)
                        .where(
                            and_(
                                PlanCaseAssociation.plan_id == plan_id,
                                PlanCaseAssociation.case_id.in_(case_id_list)
                            )
                        )
                        .values(plan_module_id=plan_case_module_id)
                    )
                    await session.execute(update_stmt)
                    return len(existing_data)
                else:
                    return await cls.associate_cases(
                        plan_id=plan_id,
                        case_ids=case_id_list,
                        plan_module_id=plan_case_module_id,
                        session=session
                    )
        except Exception as e:
            raise e
    
    @classmethod
    async def associate_cases(
        cls,
        plan_id: int,
        case_ids: List[int],
        plan_module_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
        order: Optional[int] = None,
        **kwargs,
    ) -> int:
        """
        关联用例到计划
        :param plan_id: 计划ID
        :param case_ids: 用例ID列表
        :param plan_module_id: 计划分组ID
        :param session: 数据库会话
        :param kwargs: 其他关联字段
        :return: 关联数量
        """
        if not case_ids:
            return 0
        try:
            async with cls.session_scope(session) as session:
                stmt = select(PlanCaseAssociation.case_id).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_id.in_(case_ids)
                    )
                )
                result = await session.execute(stmt)
                existing_ids = set(result.scalars().all())
                
                new_case_ids = [cid for cid in case_ids if cid not in existing_ids]
                log.info(f"new_case_ids: {new_case_ids}")
                if not new_case_ids:
                    return 0
                
                if order is not None:
                    # 指定位置插入：将 >= order 的用例顺序后移，为新用例腾出位置
                    await session.execute(
                        update(PlanCaseAssociation)
                        .where(
                            and_(
                                PlanCaseAssociation.plan_id == plan_id,
                                PlanCaseAssociation.order >= order,
                            )
                        )
                        .values(order=PlanCaseAssociation.order + len(new_case_ids))
                    )
                    start_order = order
                else:
                    # 未指定位置：追加到末尾
                    last_order = await get_last_order(plan_id, session)
                    start_order = last_order + 1

                values = [
                    {
                        "plan_id": plan_id,
                        "plan_module_id": plan_module_id,
                        "case_id": case_id,
                        "order": case_order,
                        **kwargs,
                    }
                    for case_order, case_id in enumerate(new_case_ids, start=start_order)
                ]
                await session.execute(insert(PlanCaseAssociation).values(values))
                return len(values)
        except Exception as e:
            log.error(e)
            raise

    @classmethod
    async def remove_association(cls, case_ids: List[int], plan_id: int) -> int:
        """
        移除用例关联
        :param case_ids: 用例ID列表
        :param plan_id: 计划ID
        :return: 删除数量
        """
        try:
            async with cls.transaction() as session:
                result = await session.execute(
                    delete(PlanCaseAssociation).where(and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_id.in_(case_ids),
                    ))
                )
                return result.rowcount
        except Exception as e:
            raise

    @classmethod
    async def update_case_status(
        cls,
        plan_case_id: int,
        user: User,
        is_review: Optional[bool] = None,
        case_status: Optional[int] = None,
        bug_url: Optional[str] = None
    ) -> PlanCaseAssociation:
        """
        更新用例关联状态
        :param plan_case_id: 计划用例关联ID
        :param user: 操作用户
        :param is_review: 是否审核
        :param case_status: 用例状态
        :param bug_url: 缺陷链接
        :return: 更新后的关联
        """
        kwargs = {"id": plan_case_id}
        if is_review is not None:
            kwargs["is_review"] = is_review
        if case_status is not None:
            kwargs["case_status"] = case_status
        if bug_url is not None:
            kwargs["bug_url"] = bug_url
        
        return await cls.update_by_id(update_user=user, **kwargs)

    @classmethod
    async def get_plan_cases(
        cls,
        plan_id: int,
        plan_module_id: Optional[int] = None,
        case_level: Optional[str] = None,
        case_status: Optional[int] = None,
        is_review: Optional[bool] = None,
    ) -> list:
        """
        获取计划用例列表（全部）
        :param plan_id: 计划ID
        :param plan_module_id: 计划分组ID（包含其子模块）
        :param case_level: 用例等级
        :param case_status: 用例状态
        :param is_review: 是否审核
        :return: 用例列表
        """
        async with cls.transaction() as session:
            conditions = [PlanCaseAssociation.plan_id == plan_id]

            if plan_module_id is not None:
                module_ids = select(PlanModule.id).where(
                    or_(
                        PlanModule.parent_id == plan_module_id,
                        PlanModule.id == plan_module_id
                    )
                )
                conditions.append(PlanCaseAssociation.plan_module_id.in_(module_ids))

            filter_mapping = {
                (case_level, "case_level"): TestCase.case_level == case_level,
                (case_status, "case_status"): PlanCaseAssociation.case_status == case_status,
                (is_review, "is_review"): PlanCaseAssociation.is_review == is_review,
            }
            for key, condition in filter_mapping.items():
                if key[0] is not None:
                    conditions.append(condition)

            stmt = (
                select(PlanCaseAssociation, TestCase)
                .join(TestCase, TestCase.id == PlanCaseAssociation.case_id)
                .where(and_(*conditions))
                .options(selectinload(TestCase.case_sub_steps))
                .order_by(PlanCaseAssociation.order)
            )
            result = await session.execute(stmt)
            rows = result.unique().all()

            # 收集所有 step_id，批量查询步骤结果
            all_step_ids = []
            for _, case in rows:
                all_step_ids.extend([s.id for s in case.case_sub_steps])

            step_results = {}
            if all_step_ids:
                result_stmt = select(TestCaseStepResult).where(
                    and_(
                        TestCaseStepResult.plan_id == plan_id,
                        TestCaseStepResult.step_id.in_(all_step_ids),
                    )
                )
                result_rows = await session.execute(result_stmt)
                for r in result_rows.scalars().all():
                    step_results[r.step_id] = r

            data = [
                {
                    **case.to_dict(),
                    "plan_case_id": assoc.case_id,
                    "plan_module_id": assoc.plan_module_id,
                    "is_review": assoc.is_review,
                    "case_status": assoc.case_status,
                    "bug_url": assoc.bug_url,
                    "order": assoc.order,
                    "case_sub_steps": [
                        {
                            **s.to_dict(),
                            **({
                                "actual_result": r.actual_result,
                                "status": r.status,
                                "bug_url": r.bug_url,
                            } if (r := step_results.get(s.id)) else {
                                "actual_result": None,
                                "status": 0,
                                "bug_url": None,
                            })
                        }
                        for s in case.case_sub_steps
                    ]
                }
                for assoc, case in rows
            ]
            return data 

    @classmethod
    async def get_overview(cls, plan_id: int) -> dict:
        """
        获取计划概览统计
        :param plan_id: 计划ID
        :return: 统计数据
        """
        try:
            async with cls.transaction() as session:
                case_total_stmt = select(func.count()).select_from(PlanCaseAssociation).where(
                    PlanCaseAssociation.plan_id == plan_id
                )
                case_total = (await session.execute(case_total_stmt)).scalar() or 0
                
                case_passed_stmt = select(func.count()).select_from(PlanCaseAssociation).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_status == 1
                    )
                )
                case_passed = (await session.execute(case_passed_stmt)).scalar() or 0
                
                case_failed_stmt = select(func.count()).select_from(PlanCaseAssociation).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_status == 2
                    )
                )
                case_failed = (await session.execute(case_failed_stmt)).scalar() or 0
                
                bug_stmt = select(func.count()).select_from(PlanCaseAssociation).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.bug_url.isnot(None),
                        PlanCaseAssociation.bug_url != ""
                    )
                )
                bug_total = (await session.execute(bug_stmt)).scalar() or 0
                
                bug_urls_stmt = select(PlanCaseAssociation.bug_url).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.bug_url.isnot(None),
                        PlanCaseAssociation.bug_url != ""
                    )
                )
                bug_urls_result = await session.execute(bug_urls_stmt)
                bug_urls = [url for url in bug_urls_result.scalars().all() if url]
                
                req_total_stmt = select(func.count()).select_from(PlanRequirementAssociation).where(
                    PlanRequirementAssociation.plan_id == plan_id
                )
                requirement_total = (await session.execute(req_total_stmt)).scalar() or 0
                
                req_completed_stmt = (
                    select(func.count())
                    .select_from(PlanRequirementAssociation)
                    .join(Requirement, Requirement.id == PlanRequirementAssociation.requirement_id)
                    .where(
                        and_(
                            PlanRequirementAssociation.plan_id == plan_id,
                            Requirement.process == 4
                        )
                    )
                )
                requirement_completed = (await session.execute(req_completed_stmt)).scalar() or 0
                
                case_not_executed = case_total - case_passed - case_failed
                case_completion_rate = round((case_passed + case_failed) / case_total * 100, 2) if case_total > 0 else 0
                requirement_completion_rate = round(requirement_completed / requirement_total * 100, 2) if requirement_total > 0 else 0
                
                return {
                    "plan_id": plan_id,
                    "case_total": case_total,
                    "case_passed": case_passed,
                    "case_failed": case_failed,
                    "case_not_executed": case_not_executed,
                    "case_completion_rate": case_completion_rate,
                    "bug_total": bug_total,
                    "bug_urls": bug_urls,
                    "requirement_total": requirement_total,
                    "requirement_completed": requirement_completed,
                    "requirement_completion_rate": requirement_completion_rate
                }
        except Exception as e:
            raise

    @classmethod
    async def get_statistics(cls, plan_id: int) -> dict:
        """
        获取计划详细统计
        :param plan_id: 计划ID
        :return: 统计数据
        """
        try:
            async with cls.transaction() as session:
                level_stmt = (
                    select(PlanCaseAssociation.case_level, func.count().label("count"))
                    .where(PlanCaseAssociation.plan_id == plan_id)
                    .group_by(PlanCaseAssociation.case_level)
                )
                level_result = await session.execute(level_stmt)
                case_by_level = {row.case_level: row.count for row in level_result.all()}
                
                status_stmt = (
                    select(PlanCaseAssociation.case_status, func.count().label("count"))
                    .where(PlanCaseAssociation.plan_id == plan_id)
                    .group_by(PlanCaseAssociation.case_status)
                )
                status_result = await session.execute(status_stmt)
                status_map = {0: "未开始", 1: "通过", 2: "失败"}
                case_by_status = {status_map.get(row.case_status, "未知"): row.count for row in status_result.all()}
                
                return {
                    "plan_id": plan_id,
                    "case_by_level": case_by_level,
                    "case_by_status": case_by_status,
                    "daily_trend": []
                }
        except Exception as e:
            raise