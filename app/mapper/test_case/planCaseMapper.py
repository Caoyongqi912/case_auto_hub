#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planCaseMapper
# @Software: PyCharm
# @Desc: 计划用例关联数据访问层
from typing import List, Optional

from sqlalchemy import insert, delete, select, and_, func, update

from app.mapper import Mapper
from app.model.base import User
from app.model.caseHub.association import PlanCaseAssociation, PlanRequirementAssociation
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.requirement import Requirement


class PlanCaseMapper(Mapper[PlanCaseAssociation]):
    __model__ = PlanCaseAssociation

    @classmethod
    async def associate_cases(
        cls,
        plan_id: int,
        case_ids: List[int],
        user: User,
        plan_module_id: Optional[int] = None,
        case_level: str = "P2"
    ) -> int:
        """
        关联用例到计划
        :param plan_id: 计划ID
        :param case_ids: 用例ID列表
        :param user: 操作用户
        :param plan_module_id: 计划分组ID
        :param case_level: 用例等级
        :return: 关联数量
        """
        if not case_ids:
            return 0
        try:
            async with cls.transaction() as session:
                stmt = select(PlanCaseAssociation.case_id).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_id.in_(case_ids)
                    )
                )
                result = await session.execute(stmt)
                existing_ids = set(result.scalars().all())
                
                new_case_ids = [cid for cid in case_ids if cid not in existing_ids]
                if not new_case_ids:
                    return 0
                
                values = [
                    {
                        "plan_id": plan_id,
                        "plan_module_id": plan_module_id,
                        "case_id": case_id,
                        "case_level": case_level,
                        "creator": user.id,
                        "creatorName": user.username,
                    }
                    for case_id in new_case_ids
                ]
                await session.execute(insert(PlanCaseAssociation).values(values))
                return len(values)
        except Exception as e:
            raise

    @classmethod
    async def remove_association(cls, plan_case_id: int) -> int:
        """
        移除用例关联
        :param plan_case_id: 计划用例关联ID
        :return: 删除数量
        """
        try:
            async with cls.transaction() as session:
                result = await session.execute(
                    delete(PlanCaseAssociation).where(PlanCaseAssociation.id == plan_case_id)
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
        current: int = 1,
        pageSize: int = 10
    ) -> dict:
        """
        分页获取计划用例列表
        :param plan_id: 计划ID
        :param plan_module_id: 计划分组ID
        :param case_level: 用例等级
        :param case_status: 用例状态
        :param is_review: 是否审核
        :param current: 当前页
        :param pageSize: 每页大小
        :return: 分页数据
        """
        try:
            async with cls.transaction() as session:
                conditions = [PlanCaseAssociation.plan_id == plan_id]
                
                if plan_module_id is not None:
                    conditions.append(PlanCaseAssociation.plan_module_id == plan_module_id)
                if case_level:
                    conditions.append(PlanCaseAssociation.case_level == case_level)
                if case_status is not None:
                    conditions.append(PlanCaseAssociation.case_status == case_status)
                if is_review is not None:
                    conditions.append(PlanCaseAssociation.is_review == is_review)
                
                count_stmt = select(func.count()).select_from(PlanCaseAssociation).where(and_(*conditions))
                total = (await session.execute(count_stmt)).scalar()
                
                stmt = (
                    select(PlanCaseAssociation, TestCase)
                    .join(TestCase, TestCase.id == PlanCaseAssociation.case_id)
                    .where(and_(*conditions))
                    .order_by(PlanCaseAssociation.order, PlanCaseAssociation.create_time.desc())
                    .offset((current - 1) * pageSize)
                    .limit(pageSize)
                )
                result = await session.execute(stmt)
                rows = result.all()
                
                items = []
                for row in rows:
                    assoc, case = row
                    item = case.to_dict()
                    item.update({
                        "plan_case_id": assoc.id,
                        "plan_module_id": assoc.plan_module_id,
                        "case_level": assoc.case_level,
                        "is_review": assoc.is_review,
                        "case_status": assoc.case_status,
                        "bug_url": assoc.bug_url,
                        "order": assoc.order
                    })
                    items.append(item)
                
                return {
                    "items": items,
                    "pageInfo": {
                        "total": total,
                        "page": current,
                        "limit": pageSize
                    }
                }
        except Exception as e:
            raise

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