#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planCaseMapper
# @Software: PyCharm
# @Desc: 计划用例关联数据访问层
from typing import List, Optional

from app.mapper.test_case.testcaseMapper import TestCaseMapper
from sqlalchemy import insert, update, delete, select, and_, or_, func, case
from sqlalchemy.dialects.mysql import insert as mysql_insert
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


class PlanCaseMapper(Mapper[PlanCaseAssociation]):
    __model__ = PlanCaseAssociation

    @classmethod
    async def insert_plan_case(cls, user: User, plan_id: int, plan_module_id: int, **kwargs):
        """
        添加计划关联的用例（含步骤和动态记录）

        创建测试用例及其步骤，关联到指定计划，并记录操作动态。

        Args:
            user: 认证用户
            plan_id: 计划ID
            plan_module_id: 计划分组ID
            **kwargs: 用例属性（case_name, case_level 等）及 case_sub_steps 步骤列表

        Returns:
            TestCase: 创建的用例对象
        """
        case_sub_steps = kwargs.pop("case_sub_steps", [])
        kwargs = set_creator(user, **kwargs)
        kwargs['is_common'] = True

        async with cls.transaction() as session:
            case_obj: TestCase = await TestCaseMapper.save(session=session, **kwargs)
            if case_sub_steps:
                steps = [
                    TestCaseStep(
                        **i,
                        test_case_id=case_obj.id,
                        creator=user.id,
                        creatorName=user.username
                    )
                    for i in case_sub_steps
                ]
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

    @classmethod
    async def update_case_step_result(
        cls,
        plan_id: int,
        step_id: int,
        actual_result: Optional[str] = None,
        status: Optional[int] = None,
        bug_url: Optional[str] = None
    ):
        """
        新增或更新计划用例步骤执行结果（upsert）

        基于 (plan_id, step_id) 唯一约束，若记录已存在则更新，否则插入新记录。
        使用 MySQL INSERT ... ON DUPLICATE KEY UPDATE 实现，保证原子性。

        Args:
            plan_id: 计划ID
            step_id: 用例步骤ID
            actual_result: 实际结果
            status: 步骤状态 (0:未填写 1:通过 2:阻塞 3:跳过 4:其他)
            bug_url: 缺陷链接
        """
        async with cls.transaction() as session:
            stmt = mysql_insert(TestCaseStepResult).values(
                plan_id=plan_id,
                step_id=step_id,
                actual_result=actual_result,
                status=status,
                bug_url=bug_url
            ).on_duplicate_key_update(
                actual_result=actual_result,
                status=status,
                bug_url=bug_url
            )
            await session.execute(stmt)

    @classmethod
    async def update_case(
        cls,
        plan_id: int,
        case_id_list: List[int],
        user: User,
        is_review: Optional[int] = None,
        case_status: Optional[int] = None
    ) -> int:
        """
        批量更新计划用例关联属性

        Args:
            plan_id: 计划ID
            case_id_list: 用例ID列表
            user: 认证用户（预留，当前未用于更新人记录）
            is_review: 是否审核
            case_status: 用例状态 (0:未开始 1:通过 2:失败)

        Returns:
            int: 实际更新的记录数
        """
        values = {}
        if is_review is not None:
            values["is_review"] = is_review
        if case_status is not None:
            values["case_status"] = case_status

        if not values:
            return 0

        async with cls.transaction() as session:
            stmt = update(PlanCaseAssociation).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_id_list),
                )
            ).values(values)
            result = await session.execute(stmt)
            return result.rowcount

    @classmethod
    async def copy_plan_case(cls, case_id: int, plan_id: int, plan_module_id: int, user: User) -> int:
        """
        复制单个计划用例

        复制指定用例并将其关联到同一计划中，新用例排在原用例之后。

        Args:
            case_id: 原始用例ID
            plan_id: 计划ID
            plan_module_id: 目标计划分组ID
            user: 操作用户

        Returns:
            int: 复制数量 (1=成功, 0=失败)
        """
        async with cls.transaction() as session:
            # 获取原用例在当前计划中的最大排序位置
            max_order_stmt = select(
                func.coalesce(func.max(PlanCaseAssociation.order), 0)
            ).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id == case_id
                )
            )
            max_result = await session.execute(max_order_stmt)
            case_order = max_result.scalar()

            new_cases = await TestCaseMapper.copy_cases(
                case_ids=[case_id],
                user=user,
                session=session
            )
            if not new_cases:
                return 0

            new_case = new_cases[0]
            await cls.associate_cases(
                plan_id=plan_id,
                case_ids=[new_case.id],
                plan_module_id=plan_module_id,
                order=case_order + 1,
                session=session
            )
            return 1

    @classmethod
    async def copy_cases(
        cls,
        case_id_list: List[int],
        plan_id: int,
        plan_case_module_id: int,
        user: User,
        is_review: bool = False
    ) -> int:
        """
        批量复制计划用例到新的分组

        复制用例并创建与指定计划的关联关系。

        Args:
            case_id_list: 用例ID列表
            plan_id: 计划ID
            plan_case_module_id: 目标计划分组ID
            user: 操作用户
            is_review: 是否审核

        Returns:
            int: 复制的用例数量
        """
        async with cls.transaction() as session:
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

    @classmethod
    async def move_case(
        cls,
        case_id_list: List[int],
        plan_id: int,
        plan_case_module_id: int,
    ) -> int:
        """
        移动计划用例到新的分组

        若用例已在当前计划中，则仅更新其分组；否则创建新的关联。

        Args:
            case_id_list: 用例ID列表
            plan_id: 计划ID
            plan_case_module_id: 目标计划分组ID

        Returns:
            int: 移动/关联的用例数量
        """
        if not case_id_list:
            return 0

        async with cls.transaction() as session:
            # 直接执行更新，通过 rowcount 判断是否有匹配记录，避免多余的 SELECT 查询
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
            result = await session.execute(update_stmt)
            if result.rowcount > 0:
                return result.rowcount

            # 用例不在当前计划中，创建新关联
            return await cls.associate_cases(
                plan_id=plan_id,
                case_ids=case_id_list,
                plan_module_id=plan_case_module_id,
                session=session
            )

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
        批量关联用例到计划

        自动去重（跳过已关联的用例），支持指定插入位置（order），
        若指定 order 则自动后移已有记录的排序。

        Args:
            plan_id: 计划ID
            case_ids: 用例ID列表
            plan_module_id: 计划分组ID
            session: 数据库会话（外部传入时复用，否则新建）
            order: 插入位置排序值（None 则追加到末尾）
            **kwargs: 其他关联属性（如 is_review）

        Returns:
            int: 新增关联数量
        """
        if not case_ids:
            return 0

        async def _execute_association(sess: AsyncSession) -> int:
            # 查询已关联的用例ID，避免重复关联
            existing_stmt = select(PlanCaseAssociation.case_id).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_ids)
                )
            )
            result = await sess.execute(existing_stmt)
            existing_ids = set(result.scalars().all())

            new_case_ids = [cid for cid in case_ids if cid not in existing_ids]
            if not new_case_ids:
                return 0

            # 处理排序：指定位置插入需后移已有记录，否则追加到末尾
            if order is not None:
                await sess.execute(
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
                max_order_stmt = select(
                    func.coalesce(func.max(PlanCaseAssociation.order), 0)
                ).where(PlanCaseAssociation.plan_id == plan_id)
                max_result = await sess.execute(max_order_stmt)
                start_order = max_result.scalar() + 1

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
            await sess.execute(insert(PlanCaseAssociation).values(values))
            return len(values)

        try:
            if session:
                result = await _execute_association(session)
                await session.flush()
                return result
            else:
                async with cls.transaction() as session:
                    return await _execute_association(session)
        except Exception as e:
            log.error(e)
            raise

    @classmethod
    async def remove_association(cls, case_ids: List[int], plan_id: int) -> int:
        """
        移除用例与计划的关联

        Args:
            case_ids: 用例ID列表
            plan_id: 计划ID

        Returns:
            int: 删除的关联记录数
        """
        async with cls.transaction() as session:
            result = await session.execute(
                delete(PlanCaseAssociation).where(and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_ids),
                ))
            )
            return result.rowcount

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
        更新单条用例关联状态

        Args:
            plan_case_id: 计划用例关联ID（作为 update_by_id 的查询条件）
            user: 操作用户
            is_review: 是否审核
            case_status: 用例状态 (0:未开始 1:通过 2:失败 3:阻塞 4:跳过)
            bug_url: 缺陷链接

        Returns:
            PlanCaseAssociation: 更新后的关联记录
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
        获取计划用例列表（含步骤及步骤执行结果）

        支持按分组（含子分组）、用例等级、状态、审核状态筛选。
        采用两次查询策略：先查用例再查步骤，避免 JOIN 笛卡尔积导致数据膨胀。

        Args:
            plan_id: 计划ID
            plan_module_id: 计划分组ID（包含其子模块下的用例）
            case_level: 用例等级筛选
            case_status: 用例状态筛选 (0:未开始 1:通过 2:失败)
            is_review: 是否审核筛选

        Returns:
            list: 用例字典列表，每项包含用例信息、关联属性及步骤结果
        """
        async with cls.transaction() as session:
            conditions = [PlanCaseAssociation.plan_id == plan_id]

            # 分组筛选：包含指定分组及其直接子分组下的用例
            if plan_module_id is not None:
                module_ids = select(PlanModule.id).where(
                    or_(
                        PlanModule.parent_id == plan_module_id,
                        PlanModule.id == plan_module_id
                    )
                )
                conditions.append(PlanCaseAssociation.plan_module_id.in_(module_ids))

            if case_level is not None:
                conditions.append(TestCase.case_level == case_level)
            if case_status is not None:
                conditions.append(PlanCaseAssociation.case_status == case_status)
            if is_review is not None:
                conditions.append(PlanCaseAssociation.is_review == is_review)

            # 第一次查询：获取计划关联的用例基本信息
            stmt = (
                select(PlanCaseAssociation, TestCase)
                .join(TestCase, TestCase.id == PlanCaseAssociation.case_id)
                .where(and_(*conditions))
                .order_by(PlanCaseAssociation.order)
            )
            result = await session.execute(stmt)
            rows = result.unique().all()

            if not rows:
                return []

            case_ids = [case.id for _, case in rows]

            # 第二次查询：获取用例步骤及对应计划下的执行结果
            steps_stmt = (
                select(TestCaseStep, TestCaseStepResult)
                .outerjoin(
                    TestCaseStepResult,
                    and_(
                        TestCaseStepResult.step_id == TestCaseStep.id,
                        TestCaseStepResult.plan_id == plan_id
                    )
                )
                .where(TestCaseStep.test_case_id.in_(case_ids))
                .order_by(TestCaseStep.order)
            )
            steps_result = await session.execute(steps_stmt)
            steps_rows = steps_result.all()

            # 构建步骤映射：case_id -> 步骤结果列表
            step_map = {}
            for step, step_result in steps_rows:
                if step.test_case_id not in step_map:
                    step_map[step.test_case_id] = []
                step_map[step.test_case_id].append({
                    **step.to_dict(),
                    "actual_result": step_result.actual_result if step_result else None,
                    "status": step_result.status if step_result else 0,
                    "bug_url": step_result.bug_url if step_result else None,
                })

            # 组装返回数据：用例信息 + 关联属性 + 步骤结果
            data = [
                {
                    **case.to_dict(),
                    "plan_case_id": assoc.case_id,
                    "plan_module_id": assoc.plan_module_id,
                    "is_review": assoc.is_review,
                    "case_status": assoc.case_status,
                    "bug_url": assoc.bug_url,
                    "order": assoc.order,
                    "case_sub_steps": step_map.get(case.id, [])
                }
                for assoc, case in rows
            ]
            return data

    @classmethod
    async def get_overview(cls, plan_id: int) -> dict:
        """
        获取计划概览统计数据

        包含用例执行统计、缺陷统计、需求完成统计及各项完成率。

        Args:
            plan_id: 计划ID

        Returns:
            dict: 概览统计数据
        """
        async with cls.transaction() as session:
            # 用例状态分布统计
            status_stmt = (
                select(
                    PlanCaseAssociation.case_status,
                    func.count().label("count")
                )
                .where(PlanCaseAssociation.plan_id == plan_id)
                .group_by(PlanCaseAssociation.case_status)
            )
            status_result = await session.execute(status_stmt)
            status_counts = {row.case_status: row.count for row in status_result.all()}

            case_total = sum(status_counts.values())
            case_passed = status_counts.get(1, 0)
            case_failed = status_counts.get(2, 0)

            # 缺陷链接统计（SQL 层已过滤 NULL 和空串，无需 Python 层再过滤）
            bug_urls_stmt = select(PlanCaseAssociation.bug_url).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.bug_url.isnot(None),
                    PlanCaseAssociation.bug_url != ""
                )
            )
            bug_urls_result = await session.execute(bug_urls_stmt)
            bug_urls = bug_urls_result.scalars().all()

            # 需求完成度统计
            req_stmt = (
                select(
                    func.count().label("total"),
                    func.sum(
                        case((Requirement.process == 4, 1), else_=0)
                    ).label("completed")
                )
                .select_from(PlanRequirementAssociation)
                .join(Requirement, Requirement.id == PlanRequirementAssociation.requirement_id)
                .where(PlanRequirementAssociation.plan_id == plan_id)
            )
            req_result = await session.execute(req_stmt)
            req_row = req_result.one()
            requirement_total = req_row.total or 0
            requirement_completed = int(req_row.completed or 0)

            # 计算派生指标
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
                "bug_total": len(bug_urls),
                "bug_urls": bug_urls,
                "requirement_total": requirement_total,
                "requirement_completed": requirement_completed,
                "requirement_completion_rate": requirement_completion_rate
            }

    @classmethod
    async def get_statistics(cls, plan_id: int) -> dict:
        """
        获取计划详细统计数据

        按用例等级和状态两个维度进行分组统计。
        通过 JOIN TestCase 获取 case_level（PlanCaseAssociation 无此字段）。

        Args:
            plan_id: 计划ID

        Returns:
            dict: 统计数据，包含 case_by_level、case_by_status、daily_trend
        """
        async with cls.transaction() as session:
            stmt = (
                select(
                    TestCase.case_level,
                    PlanCaseAssociation.case_status,
                    func.count().label("count")
                )
                .join(TestCase, TestCase.id == PlanCaseAssociation.case_id)
                .where(PlanCaseAssociation.plan_id == plan_id)
                .group_by(TestCase.case_level, PlanCaseAssociation.case_status)
            )
            result = await session.execute(stmt)
            rows = result.all()

            case_by_level = {}
            case_by_status = {}
            status_map = {0: "未开始", 1: "通过", 2: "失败", 3: "阻塞", 4: "跳过"}
            for row in rows:
                case_by_level[row.case_level] = case_by_level.get(row.case_level, 0) + row.count
                status_key = status_map.get(row.case_status, "未知")
                case_by_status[status_key] = case_by_status.get(status_key, 0) + row.count

            return {
                "plan_id": plan_id,
                "case_by_level": case_by_level,
                "case_by_status": case_by_status,
                "daily_trend": []
            }
