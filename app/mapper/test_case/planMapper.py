#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planMapper
# @Software: PyCharm
# @Desc: 测试计划数据访问层
from typing import List, Optional

from app.model.base.user import User
from sqlalchemy import insert, delete, select, and_, func, case
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.mapper import Mapper
from app.model.caseHub.case_plan import CasePlan
from app.model.caseHub.association import PlanRequirementAssociation, PlanCaseAssociation
from app.model.caseHub.requirement import Requirement
from utils import log
from app.model import async_session


class PlanMapper(Mapper[CasePlan]):
    __model__ = CasePlan
    
    @classmethod
    async def query_by_plan_name(cls,plan_name:Optional[str]=None) -> List[CasePlan]:
        """
        根据计划名称查询计划
        :param plan_name: 计划名称
        :return: 计划列表
        """
        try:
            async with async_session() as session:
                if not plan_name:
                    stmt = select(cls.__model__)
                else:
                    stmt = select(cls.__model__).where(cls.__model__.plan_name.like(f"%{plan_name}%"))
                result = await session.scalars(stmt)
                plans = result.all()
                return plans
        except Exception as e:
            log.error(f"query_by_plan_name error: {e}")
            raise
    
    @classmethod
    async def add_plan(cls,user:User,**kwargs) -> CasePlan:
        """
        添加测试计划
        :param user: 操作用户
        :param kwargs: 计划信息
        :return: 添加的计划
        """
        try:
            async with cls.transaction() as session:
                plan = CasePlan(**kwargs)
                plan.creator = user.id
                plan.creatorName = user.username
                plan = await cls.add_flush_expunge(model=plan, session=session)
                # 默认添加 root module
                from app.mapper.test_case.planModuleMapper import PlanModuleMapper
                
                root_module = await PlanModuleMapper.init_module(session=session,plan_id=plan.id,user=user)
                log.info(f"init_module: {root_module}")
                return plan
        except Exception as e:
            log.error(f"add_plan error: {e}")
            raise
        
    

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
        关联需求到计划（自动跳过已关联的项）

        利用 plan_requirement_association 的复合主键 (plan_id, requirement_id) 做去重：
        - 用 MySQL 的 INSERT IGNORE 语义，已存在的 (plan_id, requirement_id) 组合
          会被静默忽略，不会抛 IntegrityError
        - 返回值是「新增」的关联数（不含已存在的）

        :param plan_id: 计划ID
        :param requirement_ids: 需求ID列表
        :return: 实际新增的关联数量
        """
        if not requirement_ids:
            return 0
        # 输入去重：避免 (1,2,2,3) 这种调用方传重复导致 INSERT IGNORE 计数虚高
        unique_ids = list(dict.fromkeys(requirement_ids))
        try:
            async with cls.transaction() as session:
                values = [
                    {"plan_id": plan_id, "requirement_id": req_id}
                    for req_id in unique_ids
                ]
                # MySQL dialect 的 insert 支持 prefix_with("IGNORE") 跳过主键冲突
                stmt = mysql_insert(PlanRequirementAssociation).values(values)
                stmt = stmt.prefix_with("IGNORE")
                result = await session.execute(stmt)
                # result.rowcount 在 MySQL + INSERT IGNORE 下返回实际影响的行数
                return result.rowcount or 0
        except Exception as e:
            log.error(f"associate_requirements error: plan_id={plan_id}, error={e}")
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
        async with cls.transaction() as session:
            stmt = (
                select(Requirement)
                .join(
                    PlanRequirementAssociation,
                    PlanRequirementAssociation.requirement_id == Requirement.id
                )
                .where(PlanRequirementAssociation.plan_id == plan_id)
                .order_by(Requirement.create_time.desc())
            )
            result = await session.execute(stmt)
            requirements = result.scalars().all()
            return [req.map for req in requirements]

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

    @classmethod
    async def page_associated_requirements(
        cls,
        plan_id: int,
        current: int = 1,
        pageSize: int = 10,
        requirement_name: Optional[str] = None,
        requirement_level: Optional[str] = None,
        process: Optional[int] = None,
        uid: Optional[str] = None,
        sort: Optional[dict] = None,
    ) -> dict:
        """
        分页查询计划已关联的需求

        与 query_requirements_by_field 的区别：支持分页参数与排序，响应格式与项目
        其它列表接口保持一致：
        ```json
        { "items": [...], "pageInfo": { "total": N, "page": ..., "limit": ... } }
        ```

        :param plan_id: 计划ID（必填）
        :param current: 当前页码（1-based）
        :param pageSize: 每页大小
        :param requirement_name: 需求名（模糊匹配）
        :param requirement_level: 需求等级（精确匹配）
        :param process: 需求进度（精确匹配）
        :param uid: 需求 UID（精确匹配）
        :param sort: 排序参数，格式 ``{"create_time": "descend"}``
        :return: 分页结果字典
        """
        # 提前 short-circuit：避免无意义查询
        if plan_id is None:
            return await cls.map_page_data(
                data=[], total_num=0, page_size=pageSize, current=current
            )

        # 1) 收集过滤条件
        filter_conditions = [PlanRequirementAssociation.plan_id == plan_id]
        if requirement_name:
            filter_conditions.append(Requirement.requirement_name.like(f"%{requirement_name}%"))
        if requirement_level:
            filter_conditions.append(Requirement.requirement_level == requirement_level)
        if process is not None:
            filter_conditions.append(Requirement.process == process)
        if uid:
            filter_conditions.append(Requirement.uid == uid)

        offset = (current - 1) * pageSize

        try:
            async with async_session() as session:
                # 2) 基础查询
                base_query = (
                    select(Requirement)
                    .join(
                        PlanRequirementAssociation,
                        PlanRequirementAssociation.requirement_id == Requirement.id,
                    )
                    .where(and_(*filter_conditions))
                )

                # 3) 排序：与 Mapper.sorted_search 语义对齐
                if isinstance(sort, dict):
                    base_query = await cls.sorted_search(base_query, sort)
                else:
                    base_query = base_query.order_by(Requirement.create_time.desc())

                # 4) 总数：同样过滤条件
                count_query = (
                    select(func.count())
                    .select_from(PlanRequirementAssociation)
                    .join(
                        Requirement,
                        PlanRequirementAssociation.requirement_id == Requirement.id,
                    )
                    .where(and_(*filter_conditions))
                )
                total = (await session.execute(count_query)).scalar() or 0

                # 5) 分页数据
                paged = base_query.offset(offset).limit(pageSize)
                rows = (await session.execute(paged)).scalars().all()
                items = [req.map for req in rows]

                return await cls.map_page_data(
                    data=items, total_num=total, page_size=pageSize, current=current
                )
        except Exception as e:
            log.error(f"page_associated_requirements error: plan_id={plan_id}, error={e}")
            return await cls.map_page_data(
                data=[], total_num=0, page_size=pageSize, current=current
            )

    @classmethod
    async def page_query_with_stats(cls, current: int, pageSize: int, **kwargs):
        """
        分页查询测试计划（含完成率统计）

        完成率 = 已执行用例数(case_status != 0) / 用例总数

        Args:
            current: 当前页码
            pageSize: 每页大小
            **kwargs: 查询条件和排序

        Returns:
            dict: 分页结果，items 中包含 case_total、case_executed、completion_rate
        """
        async with async_session() as session:
            sort = kwargs.pop("sort", None)
            conditions = await cls.search_conditions(**kwargs)

            # 子查询：每个计划的用例统计
            stats_subq = (
                select(
                    PlanCaseAssociation.plan_id,
                    func.count().label("case_total"),
                    func.sum(
                        case((PlanCaseAssociation.first_status != 0, 1), else_=0)
                    ).label("case_executed")
                )
                .group_by(PlanCaseAssociation.plan_id)
                .subquery()
            )

            # 主查询：计划 + 统计
            base_query = (
                select(
                    CasePlan,
                    func.coalesce(stats_subq.c.case_total, 0).label("case_total"),
                    func.coalesce(stats_subq.c.case_executed, 0).label("case_executed"),
                    case(
                        (stats_subq.c.case_total > 0,
                         func.round(stats_subq.c.case_executed * 100.0 / stats_subq.c.case_total, 2)),
                        else_=0
                    ).label("completion_rate")
                )
                .outerjoin(stats_subq, stats_subq.c.plan_id == CasePlan.id)
                .filter(and_(*conditions))
            )

            # 排序
            base_query = await cls.sorted_search(base_query, sort)

            # 统计总数
            total_query = select(func.count()).select_from(CasePlan).filter(*conditions)
            total = (await session.execute(total_query)).scalar()

            # 分页
            paginated_query = base_query.offset((current - 1) * pageSize).limit(pageSize)
            result = await session.execute(paginated_query)
            rows = result.all()

            # 组装数据
            items = []
            for plan, case_total, case_executed, completion_rate in rows:
                plan_dict = plan.map if hasattr(plan, 'map') else plan.to_dict()
                plan_dict.update({
                    "case_total": int(case_total),
                    "case_executed": int(case_executed),
                    "completion_rate": float(completion_rate)
                })
                items.append(plan_dict)

            return await cls.map_page_data(items, total, pageSize, current)