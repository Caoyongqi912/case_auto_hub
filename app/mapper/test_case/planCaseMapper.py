#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planCaseMapper
# @Software: PyCharm
# @Desc: 计划用例关联数据访问层
from typing import List, Optional, Dict, Any

from sqlalchemy import insert, update, delete, select, and_, or_, func, case
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper, set_creator
from app.mapper.test_case.testcaseMapper import TestCaseMapper
from app.mapper.test_case.caseDynamicMapper import CaseDynamicMapper
from app.model.base import User
from app.model.caseHub.association import PlanCaseAssociation, PlanRequirementAssociation
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.test_case_step import TestCaseStep, TestCaseStepResult
from app.model.caseHub.requirement import Requirement
from app.model.caseHub.plan_module import PlanModule
from utils import log


class PlanCaseMapper(Mapper[PlanCaseAssociation]):
    __model__ = PlanCaseAssociation

    @classmethod
    def _prepare_plan_case_data(
            cls,
            case_data: Dict[str, Any],
            project_id: int,
            user: User
    ) -> TestCase:
        """
        准备单个计划用例数据

        :param case_data: 用例原始数据
        :param project_id: 项目ID
        :param user: 操作用户
        :return: 用例模型实例
        """
        case_data.pop("action", None)
        case_data.pop("expected_result", None)
        case_data.update({
            "project_id": project_id,
            "creator": user.id,
            "creatorName": user.username,
            "is_common": True,
        })
        return TestCase(**case_data)

    @classmethod
    def _prepare_plan_steps(
            cls,
            action: Optional[str],
            expected_result: Optional[str],
            case_index: int,
            user: User
    ) -> List[Dict[str, Any]]:
        """
        准备计划用例步骤数据

        :param action: 操作步骤文本
        :param expected_result: 预期结果文本
        :param case_index: 用例索引
        :param user: 操作用户
        :return: 步骤数据字典列表
        """
        from app.mapper.test_case.testcaseMapper import _parse_steps
        steps = _parse_steps(action, expected_result)
        result = []
        for step_index, step_data in enumerate(steps):
            step_data.update({
                "test_case_index": case_index,
                "order": step_index,
                "creator": user.id,
                "creatorName": user.username,
            })
            result.append(step_data)
        return result

    @classmethod
    def _prepare_plan_associations(
            cls,
            case_index: int,
            plan_id: int,
            plan_module_id: Optional[int],
            order: int,
            is_review: bool,
            first_status: int = 0,
            second_status: int = 0
    ) -> PlanCaseAssociation:
        """
        准备计划用例关联数据

        :param case_index: 用例索引
        :param plan_id: 计划ID
        :param plan_module_id: 计划分组ID
        :param order: 排序号
        :param is_review: 是否审核
        :param first_status: 一轮测试状态
        :param second_status: 二轮测试状态
        :return: 计划用例关联模型
        """
        return PlanCaseAssociation(
            plan_id=plan_id,
            plan_module_id=plan_module_id,
            case_id=case_index,
            order=order,
            is_review=is_review,
            first_status=first_status,
            second_status=second_status,
        )

    @classmethod
    async def insert_upload_case(
            cls,
            cases: List[Dict[str, Any]],
            user: User,
            plan_id: int,
            plan_module_id: Optional[int] = None,
            is_review: bool = False,
            first_status: int = 0,
            second_status: int = 0
    ):
        """
        批量导入计划用例关联记录

        Args:
            cases: 用例数据列表
            user: 操作用户
            plan_id: 计划ID
            plan_module_id: 计划分组ID（可选）
            is_review: 是否审核
            first_status: 一轮测试状态
            second_status: 二轮测试状态

        Returns:
            int: 导入的用例数量
        """
        if not cases:
            return 0

        from app.mapper.test_case.planMapper import PlanMapper
        from app.mapper.test_case.testcaseMapper import TestCaseStepMapper

        try:
            async with cls.transaction() as session:
                plan = await PlanMapper.get_by_id(ident=plan_id, session=session)

                max_order_stmt = select(
                    func.coalesce(func.max(PlanCaseAssociation.order), 0)
                ).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.plan_module_id == plan_module_id,
                    )
                )
                max_result = await session.execute(max_order_stmt)
                start_order = max_result.scalar() + 1

                log.info(f"case_data: {cases}")

                case_objects = []
                all_steps = []
                case_plan_associations = []

                for case_index, case_data in enumerate(cases):
                    case_obj = cls._prepare_plan_case_data(
                        case_data=case_data.copy(),
                        project_id=plan.project_id,
                        user=user
                    )
                    case_objects.append(case_obj)

                    steps = cls._prepare_plan_steps(
                        action=case_data.get("action"),
                        expected_result=case_data.get("expected_result"),
                        case_index=case_index,
                        user=user
                    )
                    all_steps.extend(steps)

                    start_order += 1
                    assoc = cls._prepare_plan_associations(
                        case_index=case_index,
                        plan_id=plan_id,
                        plan_module_id=plan_module_id,
                        order=start_order,
                        is_review=is_review,
                        first_status=first_status,
                        second_status=second_status
                    )
                    case_plan_associations.append(assoc)

                session.add_all(case_objects)
                await session.flush()

                case_id_map = {i: case_obj.id for i, case_obj in enumerate(case_objects)}

                step_objects = [
                    TestCaseStep(**cls._map_step_id(step_data, case_id_map))
                    for step_data in all_steps
                ]
                session.add_all(step_objects)

                if case_plan_associations:
                    for assoc in case_plan_associations:
                        assoc.case_id = case_id_map[assoc.case_id]
                    session.add_all(case_plan_associations)

                log.info(f"insert_upload_case success, case number: {len(case_objects)}")
                return len(case_objects)
        except Exception as e:
            log.error(f"insert_upload_case error: cases={cases}, error={e}")
            raise
            
            
            
        
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
        user: User,
        actual_result: Optional[str] = None,
        bug_url: Optional[str] = None,
        first_status: Optional[int] = None,
        second_status: Optional[int] = None
    ):
        """
        新增或更新计划用例步骤执行结果（upsert）

        基于 (plan_id, step_id) 唯一约束，若记录已存在则更新，否则插入新记录。
        任意字段变更都会触发：
        1. 状态字段变更 → 自动同步父级用例的对应状态
        2. 任意字段变更 → 记录操作动态

        Args:
            plan_id: 计划ID
            step_id: 用例步骤ID
            user: 操作用户
            actual_result: 实际结果
            bug_url: 缺陷链接
            first_status: 一轮测试状态 (0:未开始 1:通过 2:失败 3:阻塞 4:跳过)
            second_status: 二轮测试状态 (0:未开始 1:通过 2:失败 3:阻塞 4:跳过)

        Returns:
            dict: {"test_case_id": int} 用例ID（供调用方使用）
        """
        try:
            return await cls._do_update_case_step_result(
                plan_id=plan_id,
                step_id=step_id,
                user=user,
                actual_result=actual_result,
                bug_url=bug_url,
                first_status=first_status,
                second_status=second_status,
            )
        except Exception as err:
            log.error(
                "更新步骤结果失败: plan_id=%s, step_id=%s, error=%s",
                plan_id, step_id, err,
            )
            raise

    @classmethod
    async def _do_update_case_step_result(
        cls,
        plan_id: int,
        step_id: int,
        user: User,
        actual_result: Optional[str],
        bug_url: Optional[str],
        first_status: Optional[int],
        second_status: Optional[int],
    ) -> dict:
        """实际执行 upsert 同步 dynamic 记录的核心方法"""
        from app.mapper.test_case.planMapper import PlanMapper

        async with cls.transaction() as session:
            # 1. 查询旧数据（用于 dynamic 记录和变更对比）
            old_record = await cls._fetch_step_result(
                session=session, plan_id=plan_id, step_id=step_id
            )

            # 2. 执行 upsert
            await session.execute(
                mysql_insert(TestCaseStepResult).values(
                    plan_id=plan_id,
                    step_id=step_id,
                    actual_result=actual_result,
                    bug_url=bug_url,
                    first_status=first_status,
                    second_status=second_status,
                ).on_duplicate_key_update(
                    actual_result=actual_result,
                    bug_url=bug_url,
                    first_status=first_status,
                    second_status=second_status,
                )
            )

            # 3. 查询步骤所属用例
            test_case_id = await cls._fetch_step_case_id(
                session=session, step_id=step_id
            )
            if test_case_id is None:
                log.warning("步骤不存在: step_id=%s", step_id)
                return {"test_case_id": None}

            # 4. 收集状态变更（用于同步父级用例）
            status_changes: Dict[str, int] = {}
            if first_status is not None:
                status_changes["first_status"] = first_status
            if second_status is not None:
                status_changes["second_status"] = second_status

            # 5. 同步父级用例状态
            for status_field, status_value in status_changes.items():
                await cls._sync_single_step_status(
                    session=session,
                    plan_id=plan_id,
                    case_id=test_case_id,
                    step_id=step_id,
                    status=status_value,
                    status_field=status_field,
                )

            # 6. 收集所有变更字段（用于 dynamic 记录）
            old_data, new_data = cls._build_diff_data(
                old_record=old_record,
                first_status=first_status,
                second_status=second_status,
                actual_result=actual_result,
                bug_url=bug_url,
            )

            # 7. 记录操作动态（任意字段变更都会触发）
            if old_data or new_data:
                await cls._record_step_result_dynamic(
                    session=session,
                    user=user,
                    plan_id=plan_id,
                    test_case_id=test_case_id,
                    old_data=old_data,
                    new_data=new_data,
                )

            return {"test_case_id": test_case_id}

    @classmethod
    async def _fetch_step_result(
        cls,
        session: AsyncSession,
        plan_id: int,
        step_id: int,
    ) -> Optional[TestCaseStepResult]:
        """查询步骤执行结果（用于 dynamic 记录）"""
        stmt = select(TestCaseStepResult).where(
            and_(
                TestCaseStepResult.plan_id == plan_id,
                TestCaseStepResult.step_id == step_id,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def _fetch_step_case_id(
        cls,
        session: AsyncSession,
        step_id: int,
    ) -> Optional[int]:
        """查询步骤所属的用例ID"""
        stmt = select(TestCaseStep.test_case_id).where(TestCaseStep.id == step_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _build_diff_data(
        old_record: Optional[TestCaseStepResult],
        first_status: Optional[int],
        second_status: Optional[int],
        actual_result: Optional[str],
        bug_url: Optional[str],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        构建变更前后数据字典

        :returns: (old_data, new_data) - 仅包含发生变更或新增的字段
        """
        old_data: Dict[str, Any] = {}
        new_data: Dict[str, Any] = {}

        # 字段映射：(入参名, old 取值方式, new 取值方式)
        field_mappings = [
            ("first_status", first_status),
            ("second_status", second_status),
            ("actual_result", actual_result),
            ("bug_url", bug_url),
        ]

        for field_name, new_value in field_mappings:
            if new_value is None:
                # 入参未提供，跳过该字段
                continue

            new_data[field_name] = new_value
            if old_record is not None:
                old_value = getattr(old_record, field_name, None)
                if old_value is not None and old_value != new_value:
                    old_data[field_name] = old_value

        return old_data, new_data

    @classmethod
    async def _record_step_result_dynamic(
        cls,
        session: AsyncSession,
        user: User,
        plan_id: int,
        test_case_id: int,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
    ) -> None:
        """记录步骤结果变更的 dynamic 动态"""
        from app.mapper.test_case.planMapper import PlanMapper

        plan = await PlanMapper.get_by_id(ident=plan_id, session=session)
        plan_name = plan.plan_name if plan else f"计划{plan_id}"

        await CaseDynamicMapper.update_plan_case_dynamic(
            cr=user,
            plan_id=plan_id,
            plan_name=plan_name,
            case_id=test_case_id,
            old_data=old_data,
            new_data=new_data,
            session=session,
        )
        log.info(
            "记录步骤结果动态成功: plan_id=%s, case_id=%s, changes=%s",
            plan_id, test_case_id, list(new_data.keys()),
        )

    @classmethod
    async def _sync_single_step_status(
        cls,
        session: AsyncSession,
        plan_id: int,
        case_id: int,
        step_id: int,
        status: int,
        status_field: str
    ) -> None:
        """
        同步单个步骤的状态到父级用例

        根据当前步骤的状态更新，决定是否需要更新父级 PlanCaseAssociation 的对应状态字段。
        - 如果当前步骤状态为非通过（!=1），则直接更新父级用例状态为该状态
        - 如果当前步骤状态为通过（==1），则检查同用例下所有步骤是否都通过

        Args:
            session: 数据库会话
            plan_id: 计划ID
            case_id: 用例ID
            step_id: 当前更新的步骤ID
            status: 当前步骤的新状态值
            status_field: 要更新的状态字段名 ('first_status', 'second_status')
        """
        if status != 1:
            # 非通过状态：直接更新父级用例状态
            update_assoc_stmt = update(PlanCaseAssociation).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id == case_id
                )
            ).values(**{status_field: status})
            await session.execute(update_assoc_stmt)
        else:
            # 通过状态：检查该用例下所有步骤是否都为通过
            all_steps_stmt = select(TestCaseStep.id).where(
                TestCaseStep.test_case_id == case_id
            )
            all_steps_result = await session.execute(all_steps_stmt)
            all_step_ids = [row[0] for row in all_steps_result.fetchall()]

            if not all_step_ids:
                return

            # 确定要查询的目标字段
            if status_field == 'first_status':
                target_column = TestCaseStepResult.first_status
            elif status_field == 'second_status':
                target_column = TestCaseStepResult.second_status
            else:
                return

            # 查询所有步骤的对应状态
            result_stmt = select(target_column).where(
                and_(
                    TestCaseStepResult.plan_id == plan_id,
                    TestCaseStepResult.step_id.in_(all_step_ids)
                )
            )
            result_data = await session.execute(result_stmt)
            step_statuses = [row[0] for row in result_data.fetchall()]

            # 如果所有步骤都为通过（或NULL视为未执行），则更新父级用例为通过
            executed_statuses = [s for s in step_statuses if s is not None and s != 0]
            if len(executed_statuses) == len(all_step_ids) and all(s == 1 for s in executed_statuses):
                update_assoc_stmt = update(PlanCaseAssociation).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_id == case_id
                    )
                ).values(**{status_field: 1})
                await session.execute(update_assoc_stmt)

    @classmethod
    async def update_case(
        cls,
        plan_id: int,
        case_id_list: List[int],
        user: User,
        is_review: Optional[int] = None,
        first_status: Optional[int] = None,
        second_status: Optional[int] = None
    ) -> int:
        """
        批量更新计划用例关联属性


        Args:
            plan_id: 计划ID
            case_id_list: 用例ID列表
            user: 认证用户
            is_review: 是否审核
            first_status: 一轮测试状态 (0:未开始 1:通过 2:失败 3:阻塞 4:跳过)
            second_status: 二轮测试状态 (0:未开始 1:通过 2:失败 3:阻塞 4:跳过)

        Returns:
            int: 实际更新的记录数
        """
        values = {}
        if is_review is not None:
            values["is_review"] = is_review
        if first_status is not None:
            values["first_status"] = first_status
        if second_status is not None:
            values["second_status"] = second_status

        if not values:
            return 0

        async with cls.transaction() as session:
            from app.mapper.test_case.planMapper import PlanMapper
            plan = await PlanMapper.get_by_id(ident=plan_id, session=session)
            plan_name = plan.plan_name if plan else f"计划{plan_id}"

            changed_fields = list(values.keys())
            stmt = select(PlanCaseAssociation).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_id_list),
                )
            )
            result = await session.execute(stmt)
            old_records = {assoc.case_id: assoc for assoc in result.scalars().all()}

            update_stmt = update(PlanCaseAssociation).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_id_list),
                )
            ).values(values)
            update_result = await session.execute(update_stmt)

            # 更新子步骤结果状态
            if case_id_list:
                if first_status is not None:
                    await cls._sync_step_result_status(session, plan_id, case_id_list, first_status, 'first_status')
                if second_status is not None:
                    await cls._sync_step_result_status(session, plan_id, case_id_list, second_status, 'second_status')

            for case_id, assoc in old_records.items():
                old_data = {field: getattr(assoc, field) for field in changed_fields}
                await CaseDynamicMapper.update_plan_case_dynamic(
                    cr=user,
                    plan_id=plan_id,
                    plan_name=plan_name,
                    case_id=case_id,
                    old_data=old_data,
                    new_data=values,
                    session=session
                )

            return update_result.rowcount

    @classmethod
    async def _sync_step_result_status(
        cls,
        session: AsyncSession,
        plan_id: int,
        case_id_list: List[int],
        status: int,
        status_field: str = 'status'
    ) -> int:
        """
        同步更新计划下用例的子步骤结果状态

        状态映射关系：
        - status 0(未开始) -> step_result 对应状态字段 0(未填写)
        - status 1(通过) -> step_result 对应状态字段 1(通过)
        - status 2(失败) -> step_result 对应状态字段 2(失败)
        ...

        Args:
            session: 数据库会话
            plan_id: 计划ID
            case_id_list: 用例ID列表
            status: 用例状态值 (0:未开始 1:通过 2:失败 3:阻塞 4:跳过)
            status_field: 要更新的状态字段名 ('first_status', 'second_status')

        Returns:
            int: 实际更新的记录数
        """

        if status_field == 'first_status':
            target_column = TestCaseStepResult.first_status
        elif status_field == 'second_status':
            target_column = TestCaseStepResult.second_status
        else:
            return 0

        subquery = select(TestCaseStep.id).where(
            TestCaseStep.test_case_id.in_(case_id_list)
        )
        step_ids_subquery = subquery.subquery()

        update_stmt = update(TestCaseStepResult).where(
            and_(
                TestCaseStepResult.plan_id == plan_id,
                TestCaseStepResult.step_id.in_(select(step_ids_subquery))
            )
        ).values(**{target_column.key: status})

        result = await session.execute(update_stmt)
        field_name = {'first_status': '一轮测试状态', 'second_status': '二轮测试状态'}.get(status_field, '未知')
        log.info(f"同步更新计划{plan_id}下{len(case_id_list)}个用例的子步骤{field_name}为{status}，影响{result.rowcount}条记录")
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
            origin_order_stmt = select(PlanCaseAssociation.order).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id == case_id
                )
            )
            origin_result = await session.execute(origin_order_stmt)
            origin_order = origin_result.scalar_one_or_none()
            if origin_order is None:
                return 0

            await session.execute(
                update(PlanCaseAssociation)
                .where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.plan_module_id == plan_module_id,
                        PlanCaseAssociation.order > origin_order
                    )
                )
                .values(order=PlanCaseAssociation.order + 1)
            )

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
                order=origin_order + 1,
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
        first_status: Optional[int] = None,
        second_status: Optional[int] = None,
        bug_url: Optional[str] = None
    ) -> PlanCaseAssociation:
        """
        更新单条用例关联状态

        Args:
            plan_case_id: 计划用例关联ID（作为 update_by_id 的查询条件）
            user: 操作用户
            is_review: 是否审核
            first_status: 一轮测试状态 (0:未开始 1:通过 2:失败 3:阻塞 4:跳过)
            second_status: 二轮测试状态 (0:未开始 1:通过 2:失败 3:阻塞 4:跳过)
            bug_url: 缺陷链接

        Returns:
            PlanCaseAssociation: 更新后的关联记录
        """
        kwargs = {"id": plan_case_id}
        if is_review is not None:
            kwargs["is_review"] = is_review
        if first_status is not None:
            kwargs["first_status"] = first_status
        if second_status is not None:
            kwargs["second_status"] = second_status
        if bug_url is not None:
            kwargs["bug_url"] = bug_url

        return await cls.update_by_id(update_user=user, **kwargs)

    @classmethod
    async def get_plan_cases(
        cls,
        plan_id: int,
        plan_module_id: Optional[int] = None,
        case_level: Optional[str] = None,
        is_review: Optional[bool] = None,
    ) -> list:
        """
        获取计划用例列表（含步骤及步骤执行结果）

        支持按分组（含子分组）、用例等级、审核状态筛选。
        采用两次查询策略：先查用例再查步骤，避免 JOIN 笛卡尔积导致数据膨胀。

        Args:
            plan_id: 计划ID
            plan_module_id: 计划分组ID（包含其子模块下的用例）
            case_level: 用例等级筛选
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
                    "bug_url": step_result.bug_url if step_result else None,
                    "first_status": step_result.first_status if step_result else 0,
                    "second_status": step_result.second_status if step_result else 0,
                })

            # 组装返回数据：用例信息 + 关联属性 + 步骤结果
            data = [
                {
                    **case.to_dict(),
                    "case_id": assoc.case_id,
                    "plan_module_id": assoc.plan_module_id,
                    "is_review": assoc.is_review,
                    "first_status": assoc.first_status,
                    "second_status": assoc.second_status,
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
            # 一轮测试状态分布统计
            first_status_stmt = (
                select(
                    PlanCaseAssociation.first_status,
                    func.count().label("count")
                )
                .where(PlanCaseAssociation.plan_id == plan_id)
                .group_by(PlanCaseAssociation.first_status)
            )
            first_status_result = await session.execute(first_status_stmt)
            first_status_counts = {row.first_status: row.count for row in first_status_result.all()}

            # 二轮测试状态分布统计
            second_status_stmt = (
                select(
                    PlanCaseAssociation.second_status,
                    func.count().label("count")
                )
                .where(PlanCaseAssociation.plan_id == plan_id)
                .group_by(PlanCaseAssociation.second_status)
            )
            second_status_result = await session.execute(second_status_stmt)
            second_status_counts = {row.second_status: row.count for row in second_status_result.all()}

            case_total = sum(first_status_counts.values())
            first_passed = first_status_counts.get(1, 0)
            first_failed = first_status_counts.get(2, 0)
            second_passed = second_status_counts.get(1, 0)
            second_failed = second_status_counts.get(2, 0)

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
            case_not_executed = case_total - first_passed - first_failed
            first_completion_rate = round((first_passed + first_failed) / case_total * 100, 2) if case_total > 0 else 0
            second_completion_rate = round((second_passed + second_failed) / case_total * 100, 2) if case_total > 0 else 0
            requirement_completion_rate = round(requirement_completed / requirement_total * 100, 2) if requirement_total > 0 else 0

            return {
                "plan_id": plan_id,
                "case_total": case_total,
                "first_round": {
                    "passed": first_passed,
                    "failed": first_failed,
                    "not_executed": case_total - first_passed - first_failed,
                    "completion_rate": first_completion_rate
                },
                "second_round": {
                    "passed": second_passed,
                    "failed": second_failed,
                    "not_executed": case_total - second_passed - second_failed,
                    "completion_rate": second_completion_rate
                },
                "bug_total": len(bug_urls),
                "bug_urls": bug_urls,
                "requirement_total": requirement_total,
                "requirement_completed": requirement_completed,
                "requirement_completion_rate": requirement_completion_rate
            }

    @classmethod
    async def get_module_stats(cls, plan_id: int) -> Dict[str, Dict[str, int]]:
        """
        批量获取计划下每个模块的用例状态分布统计

        一次 SQL 按 (plan_module_id, first_status, second_status) 分组聚合，避免前端对每个模块
        单独调用 /api/hub/plan/cases 造成的 N+1。

        Args:
            plan_id: 计划ID

        Returns:
            字典：{module_id_str: {total, first_round: {passed, failed, ...}, second_round: {passed, failed, ...}}}
            只包含至少有一条用例关联的模块（plan_module_id 非空）。
        """
        async with cls.transaction() as session:
            stmt = (
                select(
                    PlanCaseAssociation.plan_module_id,
                    PlanCaseAssociation.first_status,
                    PlanCaseAssociation.second_status,
                    func.count().label("count"),
                )
                .where(PlanCaseAssociation.plan_id == plan_id)
                .group_by(
                    PlanCaseAssociation.plan_module_id,
                    PlanCaseAssociation.first_status,
                    PlanCaseAssociation.second_status,
                )
            )
            result = await session.execute(stmt)
            rows = result.all()

            stats: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                mid = row.plan_module_id
                if mid is None:
                    continue
                key = str(mid)
                if key not in stats:
                    stats[key] = {
                        "total": 0,
                        "first_round": {"passed": 0, "failed": 0, "pending": 0, "blocked": 0, "skipped": 0},
                        "second_round": {"passed": 0, "failed": 0, "pending": 0, "blocked": 0, "skipped": 0},
                    }

                cnt = row.count
                stats[key]["total"] += cnt

                # 统计一轮测试状态
                first_bucket = stats[key]["first_round"]
                if row.first_status == 1:
                    first_bucket["passed"] += cnt
                elif row.first_status == 2:
                    first_bucket["failed"] += cnt
                elif row.first_status == 0:
                    first_bucket["pending"] += cnt
                elif row.first_status == 3:
                    first_bucket["blocked"] += cnt
                elif row.first_status == 4:
                    first_bucket["skipped"] += cnt

                # 统计二轮测试状态
                second_bucket = stats[key]["second_round"]
                if row.second_status == 1:
                    second_bucket["passed"] += cnt
                elif row.second_status == 2:
                    second_bucket["failed"] += cnt
                elif row.second_status == 0:
                    second_bucket["pending"] += cnt
                elif row.second_status == 3:
                    second_bucket["blocked"] += cnt
                elif row.second_status == 4:
                    second_bucket["skipped"] += cnt

            # 计算通过率和执行率
            for s in stats.values():
                for round_name in ["first_round", "second_round"]:
                    round_data = s[round_name]
                    executed = round_data["passed"] + round_data["failed"]
                    round_data["pass_rate"] = round((round_data["passed"] / executed) * 100) if executed > 0 else 0
                    round_data["execution_rate"] = round((executed / s["total"]) * 100) if s["total"] > 0 else 0

            return stats

    @classmethod
    async def get_statistics(cls, plan_id: int) -> dict:
        """
        获取计划详细统计数据

        按用例等级和多轮测试状态两个维度进行分组统计。
        通过 JOIN TestCase 获取 case_level（PlanCaseAssociation 无此字段）。

        Args:
            plan_id: 计划ID

        Returns:
            dict: 统计数据，包含 case_by_level、case_by_first_status、case_by_second_status、daily_trend
        """
        async with cls.transaction() as session:
            stmt = (
                select(
                    TestCase.case_level,
                    PlanCaseAssociation.first_status,
                    PlanCaseAssociation.second_status,
                    func.count().label("count")
                )
                .join(TestCase, TestCase.id == PlanCaseAssociation.case_id)
                .where(PlanCaseAssociation.plan_id == plan_id)
                .group_by(TestCase.case_level, PlanCaseAssociation.first_status, PlanCaseAssociation.second_status)
            )
            result = await session.execute(stmt)
            rows = result.all()

            case_by_level = {}
            case_by_first_status = {}
            case_by_second_status = {}
            status_map = {0: "未开始", 1: "通过", 2: "失败", 3: "阻塞", 4: "跳过"}

            for row in rows:
                # 按等级统计
                case_by_level[row.case_level] = case_by_level.get(row.case_level, 0) + row.count

                # 按一轮状态统计
                first_key = status_map.get(row.first_status, "未知")
                case_by_first_status[first_key] = case_by_first_status.get(first_key, 0) + row.count

                # 按二轮状态统计
                second_key = status_map.get(row.second_status, "未知")
                case_by_second_status[second_key] = case_by_second_status.get(second_key, 0) + row.count

            return {
                "plan_id": plan_id,
                "case_by_level": case_by_level,
                "case_by_first_status": case_by_first_status,
                "case_by_second_status": case_by_second_status,
                "daily_trend": []
            }

    @staticmethod
    def _map_step_id(step_data: Dict[str, Any], case_id_map: Dict[int, int]) -> Dict[str, Any]:
        """将步骤的临时索引替换为实际用例ID"""
        case_index = step_data.pop("test_case_index")
        step_data["test_case_id"] = case_id_map[case_index]
        return step_data