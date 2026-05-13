#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planMapper
# @Software: PyCharm
# @Desc: 测试计划数据访问层
from typing import List, Optional

from sqlalchemy import insert, delete, select, and_

from app.mapper import Mapper
from app.model.caseHub.case_plan import CasePlan
from app.model.caseHub.association import PlanRequirementAssociation
from app.model.caseHub.requirement import Requirement


class PlanMapper(Mapper[CasePlan]):
    __model__ = CasePlan

    @classmethod
    async def plan_info(cls, plan_id: int) -> dict:
        """
        获取计划详细信息
        :param plan_id: 计划ID
        :return: 计划信息字典
        """
        plan = await cls.get_by_id(ident=plan_id)
        return plan.map if plan else None

    @classmethod
    async def associate_requirements(cls, plan_id: int, requirement_ids: List[int]) -> int:
        """
        关联需求到计划
        :param plan_id: 计划ID
        :param requirement_ids: 需求ID列表
        :return: 关联数量
        """
        if not requirement_ids:
            return 0
        try:
            async with cls.transaction() as session:
                values = [
                    {
                        "plan_id": plan_id,
                        "requirement_id": req_id,
                    }
                    for req_id in requirement_ids
                ]
                await session.execute(
                    insert(PlanRequirementAssociation).values(values)
                )
                return len(values)
        except Exception as e:
            raise

    @classmethod
    async def disassociate_requirements(cls, plan_id: int, requirement_ids: List[int]) -> int:
        """
        解除计划关联的需求
        :param plan_id: 计划ID
        :param requirement_ids: 需求ID列表
        :return: 解除关联数量
        """
        if not requirement_ids:
            return 0
        try:
            async with cls.transaction() as session:
                result = await session.execute(
                    delete(PlanRequirementAssociation).where(
                        PlanRequirementAssociation.plan_id == plan_id,
                        PlanRequirementAssociation.requirement_id.in_(requirement_ids)
                    )
                )
                return result.rowcount
        except Exception as e:
            raise

    @classmethod
    async def get_associated_requirements(cls, plan_id: int) -> List[dict]:
        """
        查询计划关联的需求列表
        :param plan_id: 计划ID
        :return: 需求列表
        """
        try:
            async with cls.transaction() as session:
                stmt = select(PlanRequirementAssociation).where(
                    PlanRequirementAssociation.plan_id == plan_id
                )
                result = await session.execute(stmt)
                associations = result.scalars().all()
                return [assoc.map for assoc in associations]
        except Exception as e:
            raise

    @classmethod
    async def query_requirements_by_field(
        cls,
        plan_id: int,
        requirement_name: Optional[str] = None,
        requirement_level: Optional[str] = None,
        process: Optional[int] = None
    ) -> List[dict]:
        """
        根据需求字段查询计划关联的需求列表
        :param plan_id: 计划ID
        :param requirement_name: 需求名称（模糊查询）
        :param requirement_level: 需求等级
        :param process: 需求进度
        :return: 需求列表
        """
        try:
            async with cls.transaction() as session:
                conditions = [PlanRequirementAssociation.plan_id == plan_id]
                
                if requirement_name:
                    conditions.append(Requirement.requirement_name.like(f"%{requirement_name}%"))
                if requirement_level:
                    conditions.append(Requirement.requirement_level == requirement_level)
                if process is not None:
                    conditions.append(Requirement.process == process)
                
                stmt = (
                    select(Requirement)
                    .join(
                        PlanRequirementAssociation,
                        PlanRequirementAssociation.requirement_id == Requirement.id
                    )
                    .where(and_(*conditions))
                    .order_by(Requirement.create_time.desc())
                )
                result = await session.execute(stmt)
                requirements = result.scalars().all()
                return [req.map for req in requirements]
        except Exception as e:
            raise