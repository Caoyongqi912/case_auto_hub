#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planCaseMapper
# @Software: PyCharm
# @Desc: 计划用例关联数据访问层
from collections import defaultdict
from copy import deepcopy
from typing import List, Optional, Dict, Any

from sqlalchemy import insert, update, delete, select, and_, or_, func, case
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper, set_creator
from app.mapper.test_case.testcaseMapper import TestCaseMapper
from app.mapper.test_case.caseDynamicMapper import CaseDynamicMapper, CaseDynamicRenderer
from app.model.base import User
from app.model.caseHub.association import PlanCaseAssociation, PlanRequirementAssociation
from app.model.caseHub.case_step_dynamic import CaseStepDynamic
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.test_case_step import TestCaseStep, TestCaseStepResult
from app.model.caseHub.requirement import Requirement
from app.model.caseHub.plan_module import PlanModule
from utils import log


class PlanCaseMapper(Mapper[PlanCaseAssociation]):
    """
    计划用例关联数据访问层

    负责计划与用例之间的关联关系管理，包括：
    - 用例的导入、添加、复制、移动、移除
    - 用例步骤执行结果的 upsert 与状态同步
    - 计划维度的统计查询（概览、模块统计、详细统计）   
    """
    __model__ = PlanCaseAssociation

    # 状态字段名 -> TestCaseStepResult 列对象的映射
    # 用于在步骤状态同步场景中，根据字段名动态选择一轮/二轮状态列
    _STATUS_COLUMN_MAP: Dict[str, Any] = {
        'first_status': TestCaseStepResult.first_status,
        'second_status': TestCaseStepResult.second_status,
    }

    # 状态值 -> 统计桶名称的映射
    # 用于将数字状态码转为语义化的桶键（如 1->passed, 2->failed）
    _STATUS_BUCKET_MAP: Dict[int, str] = {
        0: "pending",
        1: "passed",
        2: "failed",
        3: "blocked",
        4: "skipped",
    }

    # 状态字段名 -> 中文标签的映射
    # 用于日志中标识操作的是一轮还是二轮测试状态
    _STATUS_FIELD_LABEL_MAP: Dict[str, str] = {
        'first_status': '一轮测试状态',
        'second_status': '二轮测试状态',
    }

    # ------------------------------------------------------------------
    #  数据准备辅助方法（纯函数，无数据库交互）
    # ------------------------------------------------------------------

    @classmethod
    def _prepare_plan_case_data(
            cls,
            case_data: Dict[str, Any],
            project_id: int,
            user: User
    ) -> TestCase:
        """
        准备单个计划用例数据

        从导入的原始数据中移除步骤相关字段（action/expected_result），
        注入项目ID和创建人信息，构造 TestCase 模型实例。

        :param case_data: 用例原始数据（会被原地修改，调用方应传入 copy）
        :param project_id: 项目ID
        :param user: 操作用户
        :return: 用例模型实例（尚未持久化，无 id）
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

        将操作步骤和预期结果文本解析为结构化步骤列表，
        并为每个步骤注入用例索引、排序号和创建人信息。

        :param action: 操作步骤文本（多步骤以换行分隔）
        :param expected_result: 预期结果文本（多步骤以换行分隔）
        :param case_index: 用例在批量导入中的临时索引（flush 前无真实 id）
        :param user: 操作用户
        :return: 步骤数据字典列表，每个字典包含 step_action/step_expected_result 等字段
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
            is_review: str,
            first_status: Optional[str] = None,
            second_status: Optional[str] = None
    ) -> PlanCaseAssociation:
        """
        准备计划用例关联数据

        构造 PlanCaseAssociation 模型实例，用于建立计划与用例的关联关系。
        case_index 在 flush 前为临时索引，flush 后需替换为真实 case_id。

        :param case_index: 用例临时索引（flush 前使用）
        :param plan_id: 计划ID
        :param plan_module_id: 计划分组ID
        :param order: 排序号
        :param is_review: 审核状态
        :param first_status: 一轮测试状态（默认 None）
        :param second_status: 二轮测试状态（默认 None）
        :return: 计划用例关联模型实例（尚未持久化）
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

    # ------------------------------------------------------------------
    #  通用辅助方法（消除冗余，提供复用）
    # ------------------------------------------------------------------

    @classmethod
    async def _get_plan_name(cls, session: AsyncSession, plan_id: int) -> str:
        """
        获取计划名称，不存在时返回兜底值

        多个业务方法（update_case、_record_step_result_dynamic）需要获取计划名称
        用于记录操作动态，提取为公共方法避免重复查询逻辑。

        :param session: 数据库会话（复用调用方的事务）
        :param plan_id: 计划ID
        :return: 计划名称；计划不存在时返回 "计划{plan_id}" 作为兜底
        """
        from app.mapper.test_case.planMapper import PlanMapper
        plan = await PlanMapper.get_by_id(ident=plan_id, session=session)
        return plan.plan_name if plan else f"计划{plan_id}"

    @classmethod
    def _resolve_status_column(cls, status_field: str):
        """
        根据状态字段名解析对应的 TestCaseStepResult 列对象

        在步骤状态同步场景中，需要根据 'first_status' 或 'second_status'
        动态选择对应的数据库列进行查询或更新，此方法统一映射逻辑。

        :param status_field: 状态字段名，仅支持 'first_status' 或 'second_status'
        :return: 对应的 SQLAlchemy Column 对象；字段名无效时返回 None
        """
        return cls._STATUS_COLUMN_MAP.get(status_field)

    @staticmethod
    def _build_optional_values(**field_values) -> dict:
        """
        从可选参数中构建非空值字典

        自动过滤值为 None 的参数，仅保留显式传入的有效字段。
        适用于批量更新场景中"只更新非空字段"的通用模式。

        :param field_values: 关键字参数，键为字段名，值为字段值
        :return: 过滤掉 None 值后的字典

        示例:
            >>> _build_optional_values(is_review=1, first_status=None, second_status=2)
            {'is_review': 1, 'second_status': 2}
        """
        return {k: v for k, v in field_values.items() if v is not None}

    @classmethod
    def _count_status_bucket(cls, bucket: Dict[str, int], status: int, count: int) -> None:
        """
        根据状态值将计数累加到对应的统计桶中

        在模块统计和概览统计中，需要将数字状态码映射为语义化的桶键
        （如 1->passed, 2->failed），此方法统一映射和累加逻辑，
        避免在 first_round/second_round 中重复 if-elif 链。

        :param bucket: 统计桶字典，键为语义化名称（passed/failed/...），值为计数
        :param status: 状态值（0=未开始 1=通过 2=失败 3=阻塞 4=跳过）
        :param count: 本次需累加的数量
        """
        key = cls._STATUS_BUCKET_MAP.get(status)
        if key is not None:
            bucket[key] += count

    # ------------------------------------------------------------------
    #  用例导入与添加
    # ------------------------------------------------------------------

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

        处理流程：
        1. 查询计划信息，获取 project_id
        2. 查询当前计划分组下的最大排序号，确定起始排序
        3. 批量构造 TestCase 对象并 flush 获取真实 ID
        4. 将临时索引替换为真实 ID 后，批量插入步骤和关联记录

        性能优化点：
        - 使用 add_all + flush 批量写入，避免逐条 INSERT
        - 步骤和关联记录均在内存中构建完成后一次性写入

        Args:
            cases: 用例数据列表，每项包含 case_name、action、expected_result 等字段
            user: 操作用户
            plan_id: 计划ID
            plan_module_id: 计划分组ID（可选，默认 None）
            is_review: 是否审核（默认 False）
            first_status: 一轮测试状态（默认 0=未开始）
            second_status: 二轮测试状态（默认 0=未开始）

        Returns:
            int: 导入的用例数量；输入为空时返回 0
        """
        if not cases:
            return 0

        from app.mapper.test_case.planMapper import PlanMapper
        from app.mapper.test_case.testcaseMapper import TestCaseStepMapper

        try:
            async with cls.transaction() as session:
                plan = await PlanMapper.get_by_id(ident=plan_id, session=session)

                # 查询当前分组下的最大排序号，新用例从 max+1 开始编号
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

                # 第一阶段：在内存中构建所有对象（无数据库交互）
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

                # 第二阶段：批量写入用例，flush 获取自增 ID
                session.add_all(case_objects)
                await session.flush()

                # 建立临时索引 -> 真实 ID 的映射
                case_id_map = {i: case_obj.id for i, case_obj in enumerate(case_objects)}

                # 第三阶段：替换步骤中的临时索引为真实 ID，批量写入步骤
                step_objects = [
                    TestCaseStep(**cls._map_step_id(step_data, case_id_map))
                    for step_data in all_steps
                ]
                session.add_all(step_objects)

                # 第四阶段：替换关联记录中的临时索引为真实 ID，批量写入关联
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
        适用于单个用例的手动创建场景。

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
            from app.mapper.test_case.planMapper import PlanMapper
            
            plan = await PlanMapper.get_by_id(ident=plan_id, session=session)
            kwargs['project_id'] = plan.project_id
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
            log.info(f"insert_plan_case success, case_id: {case_obj.id}")
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

    # ------------------------------------------------------------------
    #  步骤执行结果更新
    # ------------------------------------------------------------------

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
        """
        实际执行 upsert + 状态同步 + dynamic 记录的核心方法

        执行流程：
        1. 查询旧记录（用于变更对比和 dynamic 记录）
        2. 执行 MySQL INSERT ... ON DUPLICATE KEY UPDATE（upsert）
        3. 查询步骤所属用例ID
        4. 收集状态变更，逐个同步到父级用例
        5. 构建变更前后数据，记录操作动态
        """
        async with cls.transaction() as session:
            # 1. 查询旧数据（用于 dynamic 记录和变更对比）
            old_record = await cls._fetch_step_result(
                session=session, plan_id=plan_id, step_id=step_id
            )

            # 2. 执行 upsert：基于 (plan_id, step_id) 唯一约束，
            #    已存在则更新，不存在则插入
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

            # 3. 查询步骤所属用例（步骤 -> 用例的外键关联）
            test_case_id = await cls._fetch_step_case_id(
                session=session, step_id=step_id
            )
            if test_case_id is None:
                log.warning("步骤不存在: step_id=%s", step_id)
                return {"test_case_id": None}

            # 4. 收集状态变更并同步到父级用例
            #    仅当状态字段被显式传入（非 None）时才触发同步
            status_changes: Dict[str, int] = {}
            if first_status is not None:
                status_changes["first_status"] = first_status
            if second_status is not None:
                status_changes["second_status"] = second_status

            for status_field, status_value in status_changes.items():
                await cls._sync_single_step_status(
                    session=session,
                    plan_id=plan_id,
                    case_id=test_case_id,
                    step_id=step_id,
                    status=status_value,
                    status_field=status_field,
                )

            # 5. 构建变更前后数据字典，记录操作动态
            old_data, new_data = cls._build_diff_data(
                old_record=old_record,
                first_status=first_status,
                second_status=second_status,
                actual_result=actual_result,
                bug_url=bug_url,
            )

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
        """查询步骤执行结果（用于 dynamic 变更对比）"""
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
        """查询步骤所属的用例ID（通过 TestCaseStep 的外键关联）"""
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

        遍历所有可变更字段，仅当入参非 None 时纳入比较：
        - 新记录场景（old_record 为 None）：所有非 None 入参均视为新增
        - 更新场景（old_record 非 None）：仅当旧值与新值不同时记录旧值

        :returns: (old_data, new_data) - 仅包含发生变更或新增的字段
        """
        old_data: Dict[str, Any] = {}
        new_data: Dict[str, Any] = {}

        # 字段映射：入参名 -> 实际值，遍历时跳过 None 值
        field_mappings = [
            ("first_status", first_status),
            ("second_status", second_status),
            ("actual_result", actual_result),
            ("bug_url", bug_url),
        ]

        for field_name, new_value in field_mappings:
            if new_value is None:
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
        plan_name = await cls._get_plan_name(session=session, plan_id=plan_id)

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

        同步策略：
        - 非通过状态（!=1）：直接将父级用例状态更新为该状态（一票否决）
        - 通过状态（==1）：检查同用例下所有步骤是否都通过，全部通过才更新父级为通过

        性能优化：
        - 通过状态场景：使用单条 SQL 的 LEFT JOIN + COUNT 判断是否存在未通过的步骤，
          替代原有的"查全部步骤ID + 查全部步骤结果"两次查询方案，减少一次数据库往返

        Args:
            session: 数据库会话
            plan_id: 计划ID
            case_id: 用例ID
            step_id: 当前更新的步骤ID
            status: 当前步骤的新状态值
            status_field: 要更新的状态字段名 ('first_status', 'second_status')
        """
        target_column = cls._resolve_status_column(status_field)
        if target_column is None:
            return

        if status != 1:
            # 非通过状态：一票否决，直接更新父级用例状态
            update_assoc_stmt = update(PlanCaseAssociation).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id == case_id
                )
            ).values(**{status_field: status})
            await session.execute(update_assoc_stmt)
        else:
            # 通过状态：使用单条 SQL 检查是否存在未通过的步骤
            # 逻辑等价于：NOT EXISTS (step WHERE step.status != 1 OR step无结果记录)
            # 若 non_pass_count == 0，则所有步骤均已通过，可更新父级为通过
            non_pass_count_stmt = (
                select(func.count())
                .select_from(TestCaseStep)
                .outerjoin(
                    TestCaseStepResult,
                    and_(
                        TestCaseStepResult.step_id == TestCaseStep.id,
                        TestCaseStepResult.plan_id == plan_id
                    )
                )
                .where(
                    and_(
                        TestCaseStep.test_case_id == case_id,
                        or_(
                            # 步骤尚无结果记录（未执行）
                            TestCaseStepResult.id.is_(None),
                            # 步骤结果状态非通过（coalesce 防止 NULL 比较）
                            func.coalesce(target_column, 0) != 1,
                        )
                    )
                )
            )
            result = await session.execute(non_pass_count_stmt)
            if result.scalar() == 0:
                update_assoc_stmt = update(PlanCaseAssociation).where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_id == case_id
                    )
                ).values(**{status_field: 1})
                await session.execute(update_assoc_stmt)

    # ------------------------------------------------------------------
    #  用例批量更新
    # ------------------------------------------------------------------

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

        更新流程：
        1. 构建更新值字典（仅包含非 None 的字段）
        2. 查询更新前的旧记录（用于 dynamic 记录）
        3. 执行批量 UPDATE
        4. 同步子步骤结果状态
        5. 逐条记录操作动态

        Args:
            plan_id: 计划ID
            case_id_list: 用例ID列表
            user: 认证用户
            is_review: 是否审核
            first_status: 一轮测试状态
            second_status: 二轮测试状态

        Returns:
            int: 实际更新的记录数
        """
        values = cls._build_optional_values(
            is_review=is_review,
            first_status=first_status,
            second_status=second_status
        )
        if not values:
            return 0

        async with cls.transaction() as session:
            plan_name = await cls._get_plan_name(session=session, plan_id=plan_id)
            changed_fields = list(values.keys())

            # 查询旧记录（必须在 UPDATE 前查询，用 deepcopy 隔离 SQLAlchemy 身份映射）
            stmt = select(PlanCaseAssociation).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_id_list),
                )
            )
            result = await session.execute(stmt)
            old_records = {assoc.case_id: deepcopy(assoc.map()) for assoc in result.scalars().all()}

            # 执行批量更新
            update_stmt = update(PlanCaseAssociation).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_id_list),
                )
            ).values(values)
            update_result = await session.execute(update_stmt)

            # 同步子步骤结果状态
            if first_status is not None:
                await cls._sync_step_result_status(session, plan_id, case_id_list, first_status, 'first_status')
            if second_status is not None:
                await cls._sync_step_result_status(session, plan_id, case_id_list, second_status, 'second_status')

            # 逐条记录操作动态（renderer 只创建一次）
            renderer = await CaseDynamicRenderer.from_db(session=session)
            for case_id, old_record in old_records.items():
                old_data = {k: old_record[k] for k in changed_fields}

                # 跳过无实际变更的记录（兼容 int/str 类型差异）
                if all(str(old_data.get(k)) == str(values.get(k)) for k in changed_fields):
                    continue

                diff_info = renderer.diff_plan_case_dict(old_data, values)
                if not diff_info:
                    continue

                log.debug("用例 %d 变更: %s", case_id, diff_info)
                await cls.add_flush_expunge(
                    session=session,
                    model=CaseStepDynamic(
                        description=f"{user.username} 更新了计划【{plan_name}】中的用例 :{diff_info}",
                        test_case_id=case_id,
                        plan_id=plan_id,
                        creator=user.id,
                        creatorName=user.username
                    ),
                )

            return update_result.rowcount

    @classmethod
    async def _sync_step_result_status(
        cls,
        session: AsyncSession,
        plan_id: int,
        case_id_list: List[int],
        status: int,
        status_field: str 
    ) -> int:
        """
        同步更新计划下用例的子步骤结果状态

        当父级用例状态被批量更新时，需要将变更同步到其下属的所有步骤执行结果。
        使用子查询关联 TestCaseStep 表，避免先查 ID 再更新的两次交互。

        Args:
            session: 数据库会话
            plan_id: 计划ID
            case_id_list: 用例ID列表
            status: 用例状态值 (0:未开始 1:通过 2:失败 3:阻塞 4:跳过)
            status_field: 要更新的状态字段名 ('first_status', 'second_status')

        Returns:
            int: 实际更新的记录数
        """
        target_column = cls._resolve_status_column(status_field)
        if target_column is None:
            return 0

        # 子查询：查找属于指定用例的所有步骤ID
        subquery = select(TestCaseStep.id).where(
            TestCaseStep.test_case_id.in_(case_id_list)
        )
        step_ids_subquery = subquery.subquery()

        # 批量更新步骤结果状态
        update_stmt = update(TestCaseStepResult).where(
            and_(
                TestCaseStepResult.plan_id == plan_id,
                TestCaseStepResult.step_id.in_(select(step_ids_subquery))
            )
        ).values(**{target_column.key: status})

        result = await session.execute(update_stmt)
        field_label = cls._STATUS_FIELD_LABEL_MAP.get(status_field, '未知')
        log.info(
            f"同步更新计划{plan_id}下{len(case_id_list)}个用例的子步骤{field_label}为{status}，"
            f"影响{result.rowcount}条记录"
        )
        return result.rowcount

    # ------------------------------------------------------------------
    #  用例复制与移动
    # ------------------------------------------------------------------

    @classmethod
    async def copy_plan_case(cls, case_id: int, plan_id: int, plan_module_id: int, user: User) -> int:
        """
        复制单个计划用例

        复制指定用例并将其关联到同一计划中，新用例排在原用例之后。
        通过将原用例之后的所有关联记录排序号 +1，为新用例腾出位置。

        Args:
            case_id: 原始用例ID
            plan_id: 计划ID
            plan_module_id: 目标计划分组ID
            user: 操作用户

        Returns:
            int: 复制数量 (1=成功, 0=失败)
        """
        async with cls.transaction() as session:
            # 查询原用例的排序号
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

            # 将原用例之后的所有关联记录排序号 +1，腾出位置
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

            # 复制用例（含步骤）
            new_cases = await TestCaseMapper.copy_cases(
                case_ids=[case_id],
                user=user,
                session=session
            )
            if not new_cases:
                return 0

            # 创建新关联，排在原用例之后
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
        与 copy_plan_case 的区别：不处理排序位移，直接追加到目标分组末尾。

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
        优先执行 UPDATE，通过 rowcount 判断是否有匹配记录，避免多余的 SELECT 查询。

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
            # 直接执行更新，通过 rowcount 判断是否有匹配记录
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

    # ------------------------------------------------------------------
    #  关联关系管理
    # ------------------------------------------------------------------

    @classmethod
    async def _resolve_source_to_plan_module_map(
        cls,
        sess: AsyncSession,
        plan_id: int,
        user: Optional[User],
        module_ids: List[int],
    ) -> Dict[int, int]:
        """
        根据源项目 module_id 列表，构建 source_module_id -> plan_module_id 映射

        重要约束：**每个 plan 有且仅有一个根分组（parent_id IS NULL）**。
        所有关联过去的源目录必须挂在这个根下，**不会创建新的根**。
        若 plan 还没有根（理论上 init_module 会在 plan 创建时建好），兜底建一个
        名为"全部用例"的根。

        行为：
        1) 对每个 source module，沿 parent_id 走到根，得到完整路径 [src_root, ..., leaf]
        2) 取 plan 的根 plan_module 作为挂载点
        3) 沿路径逐层在 plan_module 中 find-or-create：
           - 匹配条件：plan_id, title, parent_id（父级已映射的 plan_module_id）
           - 第一层（src_root）作为 plan 根的子节点
           - 后续层依次嵌套
           - 找不到则新建
        4) 把每条 source module 映射到对应 plan_module（叶子节点就是目标）
        """
        from app.model.base.module import Module  # 局部导入避免循环

        if not module_ids:
            return {}

        # 1) 一次性把涉及的 source modules 全捞出来
        src_stmt = select(Module).where(Module.id.in_(module_ids))
        src_modules = (await sess.execute(src_stmt)).scalars().all()
        if not src_modules:
            return {}

        # 按 id 索引方便查找
        src_by_id: Dict[int, Module] = {m.id: m for m in src_modules}

        # 2) 收集所有涉及的 source module（包括所有祖先）
        involved_ids: set = set()
        # 用 BFS 走 parent 链
        queue: List[int] = list(src_by_id.keys())
        while queue:
            mid = queue.pop()
            if mid in involved_ids:
                continue
            involved_ids.add(mid)
            m = src_by_id.get(mid)
            if m is None:
                # 不在首次查询中：单独查一次
                extra = (await sess.execute(select(Module).where(Module.id == mid))).scalars().first()
                if extra is None:
                    continue
                src_by_id[mid] = extra
                m = extra
            if m.parent_id and m.parent_id not in involved_ids:
                queue.append(m.parent_id)

        # 3) 一次查全所有 source modules
        all_stmt = select(Module).where(Module.id.in_(involved_ids))
        all_modules = (await sess.execute(all_stmt)).scalars().all()
        all_by_id: Dict[int, Module] = {m.id: m for m in all_modules}

        # 4) 拉取该 plan 下所有 plan_modules，按 (title, parent_id) 索引
        plan_mod_stmt = select(PlanModule).where(PlanModule.plan_id == plan_id)
        plan_modules = (await sess.execute(plan_mod_stmt)).scalars().all()
        plan_mod_index: Dict[tuple, PlanModule] = {
            (pm.title, pm.parent_id): pm for pm in plan_modules
        }

        # 4.1) 关键：每个 plan 有且仅有一个根分组（parent_id IS NULL），
        #       所有关联过去的源目录都挂在这个根下，不能再造新的根。
        #       若 plan 还没有初始化根（理论上 init_module 已建好），兜底建一个
        #       名为"全部用例"的根。
        plan_root: Optional[PlanModule] = next(
            (pm for pm in plan_modules if pm.parent_id is None), None
        )
        if plan_root is None:
            plan_root = PlanModule(
                plan_id=plan_id,
                title="全部用例",
                parent_id=None,
                order=0,
            )
            if user is not None:
                plan_root.creator = user.id
                plan_root.creatorName = user.username
            sess.add(plan_root)
            await sess.flush()
            plan_mod_index[("全部用例", None)] = plan_root

        # 5) 对每个 leaf source module，沿根到叶逐层 find-or-create
        # 排序保证父级先处理
        sorted_ids = sorted(involved_ids, key=lambda i: (all_by_id[i].parent_id or 0))
        # 上面的排序对单链 OK，多叉场景下我们用更稳的方案：先按层级分批
        # 找出每个 source module 的 path：[root, ..., self]
        def build_path(mid: int) -> List[Module]:
            chain: List[Module] = []
            cur = all_by_id.get(mid)
            while cur is not None:
                chain.append(cur)
                if cur.parent_id is None:
                    break
                cur = all_by_id.get(cur.parent_id)
            chain.reverse()
            return chain

        # 6) 对每个 leaf source module 处理一遍
        #    关键：从 plan 已有根分组起步，源目录树成为它的子树。
        #    即 source 根节点会作为 plan 根的子节点创建（保留 title），
        #    中间节点依次嵌套。
        source_to_plan: Dict[int, int] = {}
        for leaf_id in module_ids:
            path = build_path(leaf_id)
            if not path:
                continue
            current_parent_id: int = plan_root.id
            for node in path:
                key = (node.title, current_parent_id)
                existing = plan_mod_index.get(key)
                if existing is not None:
                    current_parent_id = existing.id
                else:
                    new_pm = PlanModule(
                        plan_id=plan_id,
                        title=node.title,
                        parent_id=current_parent_id,
                        order=0,
                    )
                    if user is not None:
                        new_pm.creator = user.id
                        new_pm.creatorName = user.username
                    sess.add(new_pm)
                    await sess.flush()
                    # 同步到索引，避免同批次重复创建
                    plan_mod_index[key] = new_pm
                    current_parent_id = new_pm.id
            source_to_plan[leaf_id] = current_parent_id

        return source_to_plan

    @classmethod
    async def associate_cases(
        cls,
        plan_id: int,
        case_ids: List[int],
        plan_module_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
        order: Optional[int] = None,
        module_ids: Optional[List[int]] = None,
        merge_same_group: bool = False,
        user: Optional[User] = None,
        **kwargs,
    ) -> int:
        """
        批量关联用例到计划

        自动去重（跳过已关联的用例），支持指定插入位置（order），
        若指定 order 则自动后移已有记录的排序。

        两种模式：
        1) 不传 module_ids：所有 case_ids 关联到同一个 plan_module_id（兼容旧行为）
        2) 传 module_ids：按源目录结构在 plan 中 find-or-create PlanModule，
           然后按 case.module_id 把每条用例挂到对应的 plan_module

        Args:
            plan_id: 计划ID
            case_ids: 用例ID列表
            plan_module_id: 兜底目标分组（mode1 使用；mode2 找不到映射时也用它）
            session: 数据库会话（外部传入时复用，否则新建）
            order: 插入位置排序值（None 则追加到末尾）
            module_ids: 源项目模块ID列表（mode2 使用）
            merge_same_group: 是否合并相同用例分组（暂作语义开关保留，find-or-create 已天然合并同名）
            user: 操作用户（mode2 创建 plan_module 需要）
            **kwargs: 其他关联属性（如 is_review）

        Returns:
            int: 新增关联数量
        """
        if not case_ids:
            return 0

        async def _execute_association(sess: AsyncSession) -> int:
            # 1) 解析 source module -> plan module 映射
            source_to_plan: Dict[int, int] = {}
            if module_ids:
                source_to_plan = await cls._resolve_source_to_plan_module_map(
                    sess=sess,
                    plan_id=plan_id,
                    user=user,
                    module_ids=module_ids,
                )

            # 2) 如果有映射，需要把每个 case 按其 module_id 路由到对应 plan_module
            case_to_plan_module: Dict[int, int] = {}
            if source_to_plan:
                # 查询这些 case 的 module_id
                tc_stmt = select(TestCase.id, TestCase.module_id).where(TestCase.id.in_(case_ids))
                tc_rows = (await sess.execute(tc_stmt)).all()
                for cid, mid in tc_rows:
                    # 映射命中：用映射值；未命中（case 不在选中目录中）：用兜底 plan_module_id
                    case_to_plan_module[cid] = source_to_plan.get(mid) or plan_module_id
            else:
                # mode1：所有 case 走同一个 plan_module_id
                case_to_plan_module = {cid: plan_module_id for cid in case_ids}

            # 3) 查询已关联的用例ID，避免重复关联
            existing_stmt = select(PlanCaseAssociation.case_id).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_ids),
                )
            )
            result = await sess.execute(existing_stmt)
            existing_ids = set(result.scalars().all())

            new_case_ids = [cid for cid in case_ids if cid not in existing_ids]
            if not new_case_ids:
                return 0

            # 4) 处理排序：按 plan_module 分组后分别计算 start_order，
            #    不同 plan_module 的 order 各自连续追加
            # 默认行为：mode1 单 plan_module；mode2 按 plan_module 分桶
            # 这里为了简洁，统一追加到 plan 末尾（不指定 order 时）

            # 计算整张表当前最大 order
            max_order_stmt = select(
                func.coalesce(func.max(PlanCaseAssociation.order), 0)
            ).where(PlanCaseAssociation.plan_id == plan_id)
            max_result = await sess.execute(max_order_stmt)
            cursor = (max_result.scalar() or 0) + 1

            values = []
            for case_id in new_case_ids:
                values.append(
                    {
                        "plan_id": plan_id,
                        "plan_module_id": case_to_plan_module.get(case_id) or plan_module_id,
                        "case_id": case_id,
                        "order": cursor,
                        **kwargs,
                    }
                )
                cursor += 1

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
        is_review: Optional[int] = None,
        first_status: Optional[int] = None,
        second_status: Optional[int] = None,
        bug_url: Optional[str] = None
    ) -> PlanCaseAssociation:
        """
        更新单条用例关联状态

        通过计划用例关联ID定位记录，仅更新非 None 的字段。
        更新前后会记录操作动态。

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
        values = cls._build_optional_values(
            is_review=is_review,
            first_status=first_status,
            second_status=second_status,
            bug_url=bug_url
        )

        if not values:
            return await cls.get_by_id(plan_case_id)

        changed_fields = list(values.keys())

        async with cls.transaction() as session:
            # 查询旧记录用于 dynamic 记录
            old_assoc = await cls.get_by_id(ident=plan_case_id, session=session)
            if not old_assoc:
                raise Exception(f"未找到 plan_case_id={plan_case_id} 的记录")

            old_data = {field: getattr(old_assoc, field) for field in changed_fields}

            # 执行更新
            updated = await cls.update_by_id(
                id=plan_case_id,
                update_user=user,
                **values
            )

            # 记录操作动态
            renderer = await CaseDynamicRenderer.from_db(session=session)
            diff_info = renderer.diff_plan_case_dict(old_data, values)
            if diff_info:
                plan_name = await cls._get_plan_name(session=session, plan_id=updated.plan_id)
                session.add(
                    CaseStepDynamic(
                        description=f"{user.username} 更新了计划【{plan_name}】中的用例 :{diff_info}",
                        test_case_id=updated.case_id,
                        plan_id=updated.plan_id,
                        creator=user.id,
                        creatorName=user.username
                    )
                )
                await session.flush()

            return updated

    # ------------------------------------------------------------------
    #  查询方法
    # ------------------------------------------------------------------

    @classmethod
    async def get_plan_cases(
        cls,
        plan_id: int,
        plan_module_id: Optional[int] = None,
        case_level: Optional[str] = None,
        is_review: Optional[int] = None,
    ) -> list:
        """
        获取计划用例列表（含步骤及步骤执行结果）

        支持按分组（含子分组）、用例等级、审核状态筛选。
        采用两次查询策略：先查用例再查步骤，避免 JOIN 笛卡尔积导致数据膨胀。

        性能优化：
        - 使用 defaultdict 替代手动判空初始化，简化步骤映射构建
        - 步骤结果中未执行的步骤默认填充 first_status=0, second_status=0

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

            # 构建步骤映射：case_id -> 步骤结果列表（defaultdict 自动初始化空列表）
            step_map: Dict[int, list] = defaultdict(list)
            for step, step_result in steps_rows:
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

        性能优化：
        - 合并一轮/二轮状态分布查询为单次 SQL（按 first_status + second_status 联合分组），
          在 Python 层分别聚合两轮的计数，减少一次数据库往返
        - 消除 case_not_executed 的重复计算，使用变量复用

        Args:
            plan_id: 计划ID

        Returns:
            dict: 概览统计数据
        """
        async with cls.transaction() as session:
            # 合并查询：一轮/二轮状态分布（单次 SQL 替代原来的两次查询）
            status_stmt = (
                select(
                    PlanCaseAssociation.first_status,
                    PlanCaseAssociation.second_status,
                    func.count().label("count")
                )
                .where(PlanCaseAssociation.plan_id == plan_id)
                .group_by(
                    PlanCaseAssociation.first_status,
                    PlanCaseAssociation.second_status
                )
            )
            status_result = await session.execute(status_stmt)
            status_rows = status_result.all()

            # 分别聚合一轮和二轮的状态计数
            first_status_counts: Dict[int, int] = {}
            second_status_counts: Dict[int, int] = {}
            case_total = 0
            for row in status_rows:
                case_total += row.count
                first_status_counts[row.first_status] = \
                    first_status_counts.get(row.first_status, 0) + row.count
                second_status_counts[row.second_status] = \
                    second_status_counts.get(row.second_status, 0) + row.count

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

            # 计算派生指标（使用变量复用，避免重复计算 case_total - passed - failed）
            first_not_executed = case_total - first_passed - first_failed
            second_not_executed = case_total - second_passed - second_failed
            first_completion_rate = round((first_passed + first_failed) / case_total * 100, 2) if case_total > 0 else 0
            second_completion_rate = round((second_passed + second_failed) / case_total * 100, 2) if case_total > 0 else 0
            requirement_completion_rate = round(requirement_completed / requirement_total * 100, 2) if requirement_total > 0 else 0

            return {
                "plan_id": plan_id,
                "case_total": case_total,
                "first_round": {
                    "passed": first_passed,
                    "failed": first_failed,
                    "not_executed": first_not_executed,
                    "completion_rate": first_completion_rate
                },
                "second_round": {
                    "passed": second_passed,
                    "failed": second_failed,
                    "not_executed": second_not_executed,
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

        一次 SQL 按 (plan_module_id, first_status, second_status) 分组聚合，
        避免前端对每个模块单独调用接口造成的 N+1 问题。

        性能优化：
        - 使用 _count_status_bucket 辅助方法消除 first_round/second_round 的重复 if-elif 链

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

                # 使用辅助方法消除重复的 if-elif 状态桶计数
                cls._count_status_bucket(stats[key]["first_round"], row.first_status, cnt)
                cls._count_status_bucket(stats[key]["second_round"], row.second_status, cnt)

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

            for row in rows:
                # 按等级统计
                case_by_level[row.case_level] = case_by_level.get(row.case_level, 0) + row.count

                # 按一轮状态统计（使用类常量映射，替代硬编码字典）
                first_key = cls._STATUS_LABEL_MAP.get(row.first_status, "未知")
                case_by_first_status[first_key] = case_by_first_status.get(first_key, 0) + row.count

                # 按二轮状态统计
                second_key = cls._STATUS_LABEL_MAP.get(row.second_status, "未知")
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
        """将步骤的临时索引替换为实际用例ID（flush 后调用）"""
        case_index = step_data.pop("test_case_index")
        step_data["test_case_id"] = case_id_map[case_index]
        return step_data
