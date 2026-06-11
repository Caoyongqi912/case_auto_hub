#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planCaseMapper
# @Software: PyCharm
# @Desc: 计划用例关联数据访问层
from collections import defaultdict
from typing import List,Tuple, Optional, Dict, Any

from sqlalchemy import insert, update, delete, select, and_, or_, func, case
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.exception import CommonError
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
from utils.caseEnumResolver import find_group_path, resolve_plan_group_path, _split_group_path
from app.mapper.test_case.testcaseMapper import _parse_steps





def _step_to_dict(
    step: TestCaseStep,
    step_result: Optional[TestCaseStepResult],
) -> Dict[str, Any]:
    """把 (step, step_result) 拍平成返回 dict；未执行步骤默认值 0。

    提取为 module-level 纯函数，便于：
    - 单测覆盖（不需要 class 实例）
    - 其它查询步骤的逻辑复用
    """
    if step_result is None:
        return {
            **step.to_dict(),
            "actual_result": None,
            "bug_url": None,
            "first_status": 0,
            "second_status": 0,
        }
    return {
        **step.to_dict(),
        "actual_result": step_result.actual_result,
        "bug_url": step_result.bug_url,
        "first_status": step_result.first_status,
        "second_status": step_result.second_status,
    }



async def get_plan_module_subtree_ids(
    session: AsyncSession,
    plan_id: int,
    plan_module_id: int,
) -> List[int]:
    """
    递归查询某个 PlanModule 节点及其所有子节点的 ID (在指定 plan 内).

    与 moduleMapper.get_subtree_ids 对称: 那里是 Module (用例库) 的 parent_id 递归,
    这里是 plan_module (计划内) 的 parent_id 递归, 多一层 plan_id 限定避免跨计划.

    :param session: 异步数据库会话
    :param plan_id: 所属计划 ID
    :param plan_module_id: 起始节点的 ID
    :return: 所有子节点 (含自身) 的 ID 列表
    """
    try:
        base_query = select(PlanModule.id).where(and_(
            PlanModule.id == plan_module_id,
            PlanModule.plan_id == plan_id,
        ))
        cte = base_query.cte(name="PlanModuleSubtree", recursive=True)
        cte = cte.union_all(
            select(PlanModule.id).where(PlanModule.parent_id == cte.c.id)
        )
        return (await session.execute(select(cte.c.id))).scalars().all()
    except Exception as e:
        log.error(
            f"PlanModule 递归查询失败: plan_id={plan_id}, "
            f"plan_module_id={plan_module_id}, error={e}"
        )
        raise


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
    # 把 step_result.first_status/second_status 的数字状态码
    # 转为 passed/failed/pending 等语义化桶键, 用于聚合统计.
    # 状态码定义与 TestCaseStepResult.first_status/second_status 列保持一致.
    _STATUS_BUCKET_MAP: Dict[int, str] = {
        0: "pending",
        1: "passed",
        2: "failed",
        3: "blocked",
        4: "skipped",
    }

    # 状态字段名 -> 中文标签的映射
    # 仅用于日志/异常信息中标识操作的是一轮还是二轮测试状态,
    # 不参与业务逻辑判断 (避免文案变更触发行为变更).
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
            user: User,
            module_id: Optional[int] = None,
    ) -> TestCase:
        """
        准备单个计划用例数据

        从导入的原始数据中移除步骤相关字段（action/expected_result），
        注入项目ID和创建人信息，构造 TestCase 模型实例。

        :param case_data: 用例原始数据（会被原地修改，调用方应传入 copy）
        :param project_id: 项目ID
        :param user: 操作用户
        :param module_id: 用例库模块ID（可选）
            - 来自 group_path 在用例库树上解析后的 Module.id
            - 缺失或解析失败时为 None, 表示落入用例库"未分组数据"虚拟分组
        :return: 用例模型实例（尚未持久化，无 id）
        """
        case_data.pop("action", None)
        case_data.pop("expected_result", None)
        # group_path 是解析阶段预留给 UploadPlanModuleResolver / UploadModuleResolver
        # 的字段, 已经在 insert_upload_case 里分别解析成 plan_module_id 和 module_id,
        # 这里必须弹出, 否则 TestCase(**case_data) 会抛 `group_path is an invalid keyword argument`.
        case_data.pop("group_path", None)
        # _row 是预览阶段 aioFileReader 注入的"Excel 行号"元数据, 仅供错误提示,
        # 提交入库时已无意义, 必须弹出, 否则 TestCase(**case_data) 会抛
        # `_row is an invalid keyword argument`.
        case_data.pop("_row", None)
        case_data.update({
            "project_id": project_id,
            "creator": user.id,
            "creatorName": user.username,
            "is_common": True,
            # 用例库 module_id: 与 plan_module_id 完全独立的两棵树.
            # plan_module_id 走 plan_module 表, module_id 走 module 表 (module_type=CASE=10).
            # 即便该用例后续从 plan 移除, 用例库侧的目录定位依然成立.
            "module_id": module_id,
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
            >>> _build_optional_values(is_review="1", first_status=None, second_status="2")
            {'is_review': '1', 'second_status': '2'}
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
        :param status: 状态值
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
            is_review: Optional[str] = None,
            first_status: Optional[str] = None,
            second_status: Optional[str] = None,
            skip_duplicate: bool = False,
    ) -> Tuple[int, int]:
        """
        批量导入计划用例关联记录

        处理流程：
        0. skip_duplicate 过滤 (过滤后再做路径解析, 避免 index 漂移)
        1. 预查询 plan, 获取 project_id (提到事务外, 供用例库路径校验使用)
        2. 预解析 group_path -> plan_module_id (计划树, plan_module 表, find-or-create)
           - dedupe path: N 条 case 经常只对应 K 个 unique path
           - 每个 unique path 只 resolve 一次, 大幅减少 find_or_create_path 调用
           - 解析失败的回退到入参 plan_module_id
           - 业务语义: 计划分组是"从用例库复制"出来, 源头必须在用例库存在 (步骤 3 校验)
        3. 预校验 group_path -> module_id (用例库树, module 表 module_type=CASE)
           - **只查不建**: 任一路径缺失即整批 raise, 由 controller 转 400
           - 通过校验的 id 绑定到 TestCase.module_id, 让 is_common=True 的用例能在
             用例库正确定位; 即便该用例后续从 plan 移除, 用例库侧的定位依然成立
        4. 按 (plan_module_id) 分组, 各自查询最大排序号, 维护 per-module 的 order 游标
        5. 批量构造 TestCase 对象并 flush 获取真实 ID
        6. 将临时索引替换为真实 ID 后, 批量插入步骤和关联记录

        性能优化点：
        - 使用 add_all + flush 批量写入, 避免逐条 INSERT
        - 步骤和关联记录均在内存中构建完成后一次性写入
        - group_path 预解析在事务外进行, 不污染事务状态

        Args:
            cases: 用例数据列表, 每项包含 case_name、action、expected_result、group_path 等字段
            user: 操作用户
            plan_id: 计划ID
            plan_module_id: 默认计划分组ID (group_path 解析失败时兜底)
            is_review: 审核状态 (默认 None; 取值 "0"=未审核 / "1"=已审核)
            first_status: 一轮测试状态 (默认 None=未开始; 取值 "0"-"4")
            second_status: 二轮测试状态 (默认 None=未开始; 取值 "0"-"4")

        Returns:
            Tuple[int, int]: (imported_count, skipped_count).
            - imported_count: 实际写入并关联的用例数
            - skipped_count: 因 skip_duplicate=True 且 case_name 命中既有 case 而被跳过的用例数
            当输入 cases 为空时返回 (0, 0)
        """
        if not cases:
            return 0, 0

        from app.mapper.test_case.planMapper import PlanMapper

        # 0) skip_duplicate 过滤必须放在 group_path 解析之前.
        #    原因: case_module_map 用 case 在 cases 中的 index 当 key,
        #    过滤后重新 enumerate, index 会漂移, 旧 key 全部失配 -> 所有
        #    group_path 解析结果走兑底, 重复创建的目录在 "全部用例" 下而不是
        #    用户上传的 "前端/登录" 路径下. 先过滤, 再在过滤后的列表上构建
        #    case_module_map, index 天然对齐.
        skip_indices: set = set()
        if skip_duplicate and cases:
            # 查询 plan 下已关联的 case_name 集合, 用于"已存在同名"判定.
            # 范围已锁 plan_id, 不会拿全表.
            #
            # 注意 - TOCTOU 边界 (P1a):
            # 1) 此次查询与后续 INSERT 不在同一事务, 且未对 plan 行加锁;
            # 2) 并发场景下两个上传都通过检查后会同时写入, 出现同名双胞胎;
            # 3) 在 PlanCaseAssociation 上加 UNIQUE(plan_id, case_name) 是
            #    唯一硬性修复, 但这要求同 plan 内 TestCase.name 也要唯一,
            #    会改用例库语义, 故暂不引入; 视为后台工具的"尽力而为"去重.
            existing_names_stmt = (
                select(TestCase.case_name)
                .join(
                    PlanCaseAssociation,
                    PlanCaseAssociation.case_id == TestCase.id,
                )
                .where(PlanCaseAssociation.plan_id == plan_id)
            )
            async with cls.transaction() as session:
                rows = (await session.execute(existing_names_stmt)).scalars().all()
            existing_names: set = {name for name in rows if name}
            for idx, c in enumerate(cases):
                name = (c.get("case_name") or "").strip()
                if name and name in existing_names:
                    skip_indices.add(idx)

            # 注意 - Excel 内部同名边界 (P1b):
            # 仅与"已在本 plan 关联的"case_name 比对, 不对 Excel 内部做 dedupe.
            # 业务侧约定: 用户上传的 Excel 中如果出现 N 行同名 case_name, 全部入库
            # (N 条 TestCase + N 条 PlanCaseAssociation, case_id 不同), 视为"复制粘贴".
            # 若未来需要"Excel 内部同名仅保留第一条", 在此处追加
            # `seen = set(); if name in seen: skip_indices.add(idx); seen.add(name)` 即可.

        if skip_indices:
            cases = [c for i, c in enumerate(cases) if i not in skip_indices]
        skipped_count = len(skip_indices)
        if skipped_count:
            log.info(
                f"insert_upload_case: skip_duplicate=True 跳过 {skipped_count} 条, "
                f"剩余 {len(cases)} 条待导入"
            )

        # 0) 预查询 plan, 同时拿到 project_id (供后续用例库路径解析使用).
        #    提到事务外是 2 个目的:
        #    a) 用例库路径预解析需要 project_id 调 resolve_group_path
        #    b) 主事务里直接复用同一个 plan, 省一次 round-trip
        #    只读操作, 即便和后续写不在同一事务也无副作用.
        #
        # 注意: project_id 必须在 session 内读取. Mapper.transaction() 退出后会
        # 关闭 session, 实例变 detached, 之后再访问 plan.project_id 会触发
        # DetachedInstanceError (SQLAlchemy 默认在 commit 时 expire 所有属性).
        try:
            async with cls.transaction() as session:
                plan = await PlanMapper.get_by_id(ident=plan_id, session=session)
                if plan is None:
                    raise CommonError(f"plan_id={plan_id} 不存在")
                project_id = plan.project_id
        except CommonError:
            raise
        except Exception as e:
            log.error(f"insert_upload_case: 预查询 plan 失败 plan_id={plan_id}, error={e}")
            raise

        # 1) 预校验 group_path -> module_id (用例库树, module_type=ModuleEnum.CASE=10).
        #      业务约定: Excel 中的"所属分组"必须已存在于用例库 module 树.
        #      本步**只查不建**: 用 find_group_path 拿叶子 id, 缺失即整批拒绝.
        #      计划侧的 plan_module 树不受影响: 它在 1) 步里依旧可以 find-or-create,
        #      视为"从用例库复制"出来, 但源头 (用例库) 必须先存在.
        #      - 同一份 titles 同时复用 cache_key, 减少一次 _split_group_path
        #      - 任一 unique path 缺失, 把对应的原始 raw 字符串收集到 invalid_module_paths
        #        整批 raise, 由 controller 转 400
        from app.exception import CommonError
        case_module_id_map: Dict[int, int] = {}
        unique_module_path_resolved: Dict[str, Optional[int]] = {}
        invalid_module_paths: List[str] = []
        for case_index, case_data in enumerate(cases):
            raw_path = case_data.get("group_path")
            if not raw_path:
                continue
            titles = _split_group_path(raw_path)
            cache_key = "\x1f".join(titles)
            if cache_key not in unique_module_path_resolved:
                unique_module_path_resolved[cache_key] = await find_group_path(
                    project_id=project_id,
                    raw_group_path=raw_path,
                )
            resolved = unique_module_path_resolved[cache_key]
            if resolved is None:
                invalid_module_paths.append(raw_path)
            else:
                case_module_id_map[case_index] = resolved

        if invalid_module_paths:
            # dedupe + sort 让错误输出稳定, 方便用户批量改 Excel
            unique_invalid = sorted(set(invalid_module_paths))
            preview = unique_invalid[:5]
            more = "" if len(unique_invalid) <= 5 else f" (还有 {len(unique_invalid) - 5} 个...)"
            raise CommonError(
                message=(
                    f"用例库分组校验失败, 以下目录不存在: {preview}{more}. "
                    f"请先在用例库中创建对应目录后再导入."
                ),
                data={"invalid_paths": unique_invalid},
            )

        try:
            async with cls.transaction() as session:

                # 1) 根据用例库 module_id 在 plan 中精确复用/创建 PlanModule
                #    收集唯一 module_ids，一次性调用 _resolve_source_to_plan_module_map。
                #    该方法会按 source_module_id 精确匹配，未命中则按 title 路径新建，
                #    并自动写入 source_module_id，保证 plan_module 与 module 的持久化关联。
                case_module_map: Dict[int, int] = {}
                if case_module_id_map:
                    unique_module_ids = list(set(case_module_id_map.values()))
                    source_to_plan = await cls._resolve_source_to_plan_module_map(
                        sess=session,
                        plan_id=plan_id,
                        user=user,
                        module_ids=unique_module_ids,
                    )
                    for idx, mid in case_module_id_map.items():
                        pm_id = source_to_plan.get(mid)
                        if pm_id is not None:
                            case_module_map[idx] = pm_id
                        else:
                            log.warning(
                                f"insert_upload_case: module_id={mid} 未映射到 plan_module, "
                                f"case_index={idx} 将 fallback"
                            )

                # 2) root 兜底查询提到循环外
                root_id: Optional[int] = None
                if plan_module_id is None:
                    root_stmt = select(PlanModule).where(
                        PlanModule.plan_id == plan_id,
                        PlanModule.parent_id.is_(None),
                    ).order_by(PlanModule.order, PlanModule.id)
                    root_modules = (await session.execute(root_stmt)).scalars().all()
                    root_id = root_modules[0].id if root_modules else None

                # 3) 预收集所有目标 plan_module_id，一次性 GROUP BY 查 max(order)
                target_module_ids: set = set(case_module_map.values())
                if plan_module_id is not None:
                    target_module_ids.add(plan_module_id)
                if root_id is not None:
                    target_module_ids.add(root_id)

                max_order_per_module: Dict[int, int] = {}
                if target_module_ids:
                    max_order_stmt = select(
                        PlanCaseAssociation.plan_module_id,
                        func.max(PlanCaseAssociation.order),
                    ).where(
                        and_(
                            PlanCaseAssociation.plan_id == plan_id,
                            PlanCaseAssociation.plan_module_id.in_(target_module_ids),
                        )
                    ).group_by(PlanCaseAssociation.plan_module_id)
                    rows = (await session.execute(max_order_stmt)).all()
                    max_order_per_module = {row[0]: int(row[1] or 0) for row in rows}

                # 游标字典: 存的是"最近一次写出的 order", 第一条新 case 直接 +1.
                module_order_cursor: Dict[int, int] = dict(max_order_per_module)

                # 只打印数量, 避免把用例内容全部写日志 (PII + 性能)
                log.info(
                    f"insert_upload_case: plan_id={plan_id} 入参={len(cases)} 条, "
                    f"module_ids={len(case_module_id_map)}, "
                    f"target_modules={len(target_module_ids)}"
                )

                case_objects = []
                all_steps = []
                case_plan_associations = []

                # 用于诊断: 统计 effective_module_id 的决策来源
                diag_resolved_count = 0
                diag_fallback_plan_module_count = 0
                diag_fallback_root_count = 0

                # 第一阶段: 在内存中构建所有对象 (无数据库交互)
                for case_index, case_data in enumerate(cases):
                    # module_id 来自预解析 (用例库 tree), 与
                    # 后续 effective_module_id (plan tree) 完全独立.
                    # group_path 缺失/解析失败时为 None, 落到用例库"未分组数据".
                    case_library_module_id = case_module_id_map.get(case_index)
                    case_obj = cls._prepare_plan_case_data(
                        case_data=case_data.copy(),
                        project_id=project_id,
                        user=user,
                        module_id=case_library_module_id,
                    )
                    case_objects.append(case_obj)

                    steps = cls._prepare_plan_steps(
                        action=case_data.get("action"),
                        expected_result=case_data.get("expected_result"),
                        case_index=case_index,
                        user=user
                    )
                    all_steps.extend(steps)

                    # 该 case 实际写入的 plan_module_id:
                    # 1) group_path 解析成功 -> 用 _resolve_source_to_plan_module_map 映射出的 id
                    # 2) group_path 缺失/解析失败 -> 用入参 plan_module_id 兜底
                    # 3) 兜底仍为 None -> 退化到 plan 的根 "全部用例" 分组
                    resolved_pm = case_module_map.get(case_index)
                    if resolved_pm is not None:
                        effective_module_id = resolved_pm
                        diag_resolved_count += 1
                    elif plan_module_id is not None:
                        effective_module_id = plan_module_id
                        diag_fallback_plan_module_count += 1
                    else:
                        effective_module_id = root_id
                        diag_fallback_root_count += 1

                    if effective_module_id is None:
                        raise ValueError(
                            f"case_index={case_index} 无法定位 plan_module_id, "
                            f"group_path={case_data.get('group_path')!r}, "
                            f"plan_id={plan_id}"
                        )

                    module_order_cursor[effective_module_id] = (
                        module_order_cursor.get(effective_module_id, 0) + 1
                    )

                    assoc = cls._prepare_plan_associations(
                        case_index=case_index,
                        plan_id=plan_id,
                        plan_module_id=effective_module_id,
                        order=module_order_cursor[effective_module_id],
                        is_review=is_review,
                        first_status=first_status,
                        second_status=second_status
                    )
                    case_plan_associations.append(assoc)

                # 诊断日志: 统计 effective_module_id 的决策分布
                log.info(
                    f"insert_upload_case: plan_id={plan_id} module_id 决策分布: "
                    f"resolved={diag_resolved_count} fallback_plan_module={diag_fallback_plan_module_count} "
                    f"fallback_root={diag_fallback_root_count} "
                    f"case_module_map_keys={list(case_module_map.keys())}"
                )

                # ────────── 阶段 2: 批量写入用例, flush 获取自增 ID ──────────
                session.add_all(case_objects)
                await session.flush()

                # 建立临时索引 -> 真实 ID 的映射, 后续阶段用此替换步骤/关联的占位
                case_id_map = {i: case_obj.id for i, case_obj in enumerate(case_objects)}

                # ────────── 阶段 3: 替换步骤临时索引, 批量写入 ──────────
                step_objects = [
                    TestCaseStep(**cls._map_step_id(step_data, case_id_map))
                    for step_data in all_steps
                ]
                session.add_all(step_objects)

                # ────────── 阶段 4: 替换关联临时索引, 批量写入 ──────────
                if case_plan_associations:
                    for assoc in case_plan_associations:
                        assoc.case_id = case_id_map[assoc.case_id]
                    session.add_all(case_plan_associations)

                log.info(
                    f"insert_upload_case success, "
                    f"imported={len(case_objects)} skipped={skipped_count}"
                )
                return len(case_objects), skipped_count
        except Exception as e:
            # 只记数量与前 3 条 case_name 避免日志爆 (全量 cases 可能很大且含 PII)
            sample_names = [c.get('case_name') for c in cases[:3]]
            log.error(
                f"insert_upload_case error: plan_id={plan_id}, "
                f"case_count={len(cases)}, first_names={sample_names}, error={e}"
            )
            raise

    @classmethod
    async def _resolve_plan_module_to_library_module(
        cls,
        session: AsyncSession,
        plan_module_id: int,
        project_id: int,
    ) -> Optional[int]:
        """
        根据 plan_module_id 反向查找对应的用例库 Module.id。

        优先走 source_module_id（双向同步持久化关联），
        不存在时 fallback 到 title 路径反向匹配（兼容旧数据 & 手动分组）。

        快捷路径（O(1)）：
            plan_module.source_module_id 非 NULL → 直接返回

        Fallback 路径（O(N)）：
            1. 从 plan_module_id 出发，沿 parent_id 走到根，收集完整路径 [root, ..., leaf]
            2. 去掉 plan_root（PlanModule 有而 Module 没有的那层"全部用例"根节点）
            3. 在 Module 表中按 (project_id, module_type=CASE, title_path) 逐层查找
            4. 匹配成功后，懒加载回填 plan_module.source_module_id，供下次直接命中
            5. 返回叶子 Module.id；任一级找不到则返回 None（用例落入未分组）

        边界：
        - plan_module_id 指向 plan_root 本身 → 去掉根后路径为空 → None
        - PlanModule 是用户在计划中手动创建的 → Module 树中无匹配 → None
        - 路径有多级嵌套 → 正常逐级查找

        :param session: 数据库会话（复用外层事务）
        :param plan_module_id: 计划分组ID
        :param project_id: 项目ID（用于 Module 表过滤）
        :return: 用例库 Module.id；找不到返回 None
        """
        from app.model.base.module import Module

        # ── 快捷路径：source_module_id 已持久化 ──
        stmt = select(PlanModule).where(PlanModule.id == plan_module_id)
        start_module = (await session.execute(stmt)).scalars().first()
        if start_module is None:
            return None
        if start_module.source_module_id is not None:
            return start_module.source_module_id

        log.info(
            f"_resolve_plan_module_to_library_module: plan_module_id={plan_module_id} "
            "source_module_id 为空，走 title fallback",
        )

        # ── Fallback：title 路径反向匹配（兼容旧数据 & 手动分组） ──
        # 1) 收集该 plan 下所有 plan_module（用于沿 parent 链查找）
        plan_mod_stmt = select(PlanModule).where(
            PlanModule.plan_id == start_module.plan_id
        )
        plan_modules = (await session.execute(plan_mod_stmt)).scalars().all()
        plan_mod_by_id: Dict[int, PlanModule] = {pm.id: pm for pm in plan_modules}

        # 2) 沿 parent_id 走到根，收集完整路径（从 leaf 到 root）
        path_titles: List[str] = []
        current = start_module
        while current is not None:
            path_titles.append(current.title)
            if current.parent_id is None:
                break
            current = plan_mod_by_id.get(current.parent_id)
            if current is None:
                # parent 链断裂（不应该发生，除非数据不一致）
                break
        path_titles.reverse()  # 现在是从 root 到 leaf

        # 3) 去掉 plan_root：Module 树没有"全部用例"这一层
        #    plan_root 的 parent_id 为 None，它的子节点才是对应 Module 树的根
        if len(path_titles) <= 1:
            # 只有 plan_root 一层，或路径为空 → 无对应 Module
            log.info(
                f"_resolve_plan_module_to_library_module: plan_module_id={plan_module_id} "
                "只有根节点，无对应 Module",
            )
            return None
        module_title_path = path_titles[1:]  # 去掉根节点

        # 4) 在 Module 表中逐层查找
        parent_id: Optional[int] = None
        for title in module_title_path:
            if parent_id is None:
                cond = Module.parent_id.is_(None)
            else:
                cond = Module.parent_id == parent_id
            mod_stmt = select(Module).where(
                Module.project_id == project_id,
                Module.module_type == CASE_MODULE_TYPE,
                cond,
                Module.title == title,
            )
            node = (await session.execute(mod_stmt)).scalars().first()
            if node is None:
                log.info(
                    f"_resolve_plan_module_to_library_module: plan_module_id={plan_module_id} "
                    f"title fallback 在 '{title}' 处中断"
                )
                return None
            parent_id = node.id

        # 5) 懒加载回填：匹配成功后将 source_module_id 写回，下次直接命中
        if parent_id is not None:
            await session.execute(
                update(PlanModule)
                .where(PlanModule.id == plan_module_id)
                .values(source_module_id=parent_id)
            )
            log.info(
                f"_resolve_plan_module_to_library_module: plan_module_id={plan_module_id} "
                f"title fallback 命中 module_id={parent_id}，已回填"
            )
            # 不需要 flush：复用外层事务，由调用方统一提交

        return parent_id

    @classmethod
    async def insert_plan_case(cls, user: User, plan_id: int, plan_module_id: int, **kwargs):
        """
        添加计划关联的用例（含步骤和动态记录）

        创建测试用例及其步骤，关联到指定计划，并记录操作动态。
        适用于单个用例的手动创建场景。

        新增逻辑：自动将用例同步到用例库对应分组。
        - 根据 plan_module_id 反向解析出用例库的 module_id
        - 若 plan_module 在用例库中存在对应路径，则 module_id 设为目标分组
        - 若不存在对应路径（如手动创建的计划分组），则 module_id 为 None，落入未分组

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

            # 根据 plan_module_id 反向查找用例库对应分组
            library_module_id = await cls._resolve_plan_module_to_library_module(
                session=session,
                plan_module_id=plan_module_id,
                project_id=plan.project_id,
            )
            if library_module_id is not None:
                kwargs['module_id'] = library_module_id
                log.info(
                    f"insert_plan_case: plan_module_id={plan_module_id} 映射到用例库 module_id={library_module_id}"
                )
            else:
                log.info(
                    f"insert_plan_case: plan_module_id={plan_module_id} 未找到用例库对应分组，用例落入未分组"
                )

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
        first_status: Optional[str] = None,
        second_status: Optional[str] = None
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
            first_status: 一轮测试状态 
            second_status: 二轮测试状态

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
                f"更新步骤结果失败: plan_id={plan_id}, step_id={step_id}, error={err}",
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
                log.warning(f"步骤不存在: step_id={step_id}")
                return {"test_case_id": None}

            # 4. 收集状态变更并同步到父级用例
            #    仅当状态字段被显式传入（非 None）时才触发同步
            status_changes: Dict[str, str] = {}
            if first_status is not None:
                status_changes["first_status"] = first_status
            if second_status is not None:
                status_changes["second_status"] = second_status

            for status_field in status_changes.keys():
                await cls._sync_single_step_status(
                    session=session,
                    plan_id=plan_id,
                    case_id=test_case_id,
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
            f"记录步骤结果动态成功: plan_id={plan_id}, case_id={test_case_id}, changes={list(new_data.keys())}"
        )

    @classmethod
    async def _sync_single_step_status(
        cls,
        session: AsyncSession,
        plan_id: int,
        case_id: int,
        status_field: str
    ) -> None:
        """
        同步步骤状态到父级用例

        逻辑：case 下所有 steps 的对应 status 全部相同时，
        把这个值同步到 PlanCaseAssociation；否则不修改。

        不硬编码任何 status value，所有值通过 caseConfig 控制。

        Args:
            session: 数据库会话
            plan_id: 计划ID
            case_id: 用例ID
            status_field: 要同步的状态字段名 ('first_status', 'second_status')
        """
        target_column = cls._resolve_status_column(status_field)
        if target_column is None:
            return

        # 单条 SQL 查：总 step 数 / 有结果数 / status 最小值 / 最大值
        # 全部有结果 + 全部相同(非NULL) 才同步
        check_stmt = (
            select(
                func.count(TestCaseStep.id).label("total"),
                func.count(TestCaseStepResult.id).label("has_result"),
                func.min(target_column).label("min_status"),
                func.max(target_column).label("max_status"),
            )
            .select_from(TestCaseStep)
            .outerjoin(
                TestCaseStepResult,
                and_(
                    TestCaseStepResult.step_id == TestCaseStep.id,
                    TestCaseStepResult.plan_id == plan_id,
                ),
            )
            .where(TestCaseStep.test_case_id == case_id)
        )

        result = await session.execute(check_stmt)
        row = result.one()
        total, has_result, min_status, max_status = row

        if total > 0 and has_result == total and min_status is not None and min_status == max_status:
            update_assoc_stmt = update(PlanCaseAssociation).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id == case_id,
                )
            ).values(**{status_field: min_status})
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
        is_review: Optional[str] = None,
        first_status: Optional[str] = None,
        second_status: Optional[str] = None,
    ) -> int:
        """批量更新计划用例关联属性。

        更新流程：
        1. 入参去重 + 校验 case_id_list 全部属于 plan_id（防越权 + 防脏数据）
        2. 一次性查询旧记录（仅 SELECT 一次）
        3. 单次 UPDATE 批量回写
        4. 同步子步骤结果状态
        5. 收集 dynamic 记录，循环结束后统一 flush 一次
           （避免每条 dynamic 触发 flush+refresh=2 次 IO）

        事务边界：所有步骤在同一 ``Mapper.transaction()`` 内，
        任意一步失败将整体回滚，保证 dynamic 记录与状态更新一致。

        Args:
            plan_id: 计划ID
            case_id_list: 用例ID列表（函数内部去重）
            user: 认证用户
            is_review: 审核状态（``"0"`` 未审核 / ``"1"`` 已审核）
            first_status: 一轮测试状态
                （``"0"`` 未开始 / ``"1"`` 通过 / ``"2"`` 失败 / ``"3"`` 阻塞 / ``"4"`` 跳过）
            second_status: 二轮测试状态（取值同上）

        Returns:
            int: 实际更新的关联记录数；所有入参均为 None 时返回 0
        """
        # ---- 1. 入参归一化 ----
        case_id_list = list(dict.fromkeys(case_id_list or []))
        if not case_id_list:
            return 0

        values = cls._build_optional_values(
            is_review=is_review,
            first_status=first_status,
            second_status=second_status,
        )
        if not values:
            return 0
        changed_fields = list(values.keys())

        async with cls.transaction() as session:
            # ---- 2. 越权 / 脏数据校验 ----
            existing_ids = await cls._filter_case_ids_belong_to_plan(
                session=session,
                plan_id=plan_id,
                case_id_list=case_id_list,
            )
            invalid_ids = set(case_id_list) - existing_ids
            if invalid_ids:
                raise CommonError(
                    f"以下用例不属于计划 {plan_id}，已拒绝更新: {sorted(invalid_ids)[:10]}"
                    + (" ..." if len(invalid_ids) > 10 else ""),
                )

            # ---- 3. 查询旧记录（map() 已返回新 dict，无需 deepcopy） ----
            stmt = select(PlanCaseAssociation).where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_id_list),
                )
            )
            result = await session.execute(stmt)
            old_records = {assoc.case_id: assoc.map() for assoc in result.scalars().all()}

            # ---- 4. 单次批量 UPDATE ----
            update_stmt = (
                update(PlanCaseAssociation)
                .where(
                    and_(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_id.in_(case_id_list),
                    )
                )
                .values(values)
            )
            update_result = await session.execute(update_stmt)

            # ---- 5. 同步子步骤结果状态 ----
            # first_status 将不处理子步骤状态 。
            # if first_status is not None:
            #     await cls._sync_step_result_status(
            #         session, plan_id, case_id_list, first_status, "first_status"
            #     )
            if second_status is not None:
                await cls._sync_step_result_status(
                    session, plan_id, case_id_list, second_status, "second_status"
                )

            # ---- 6. 收集 dynamic 记录（循环外统一 flush） ----
            renderer = await CaseDynamicRenderer.from_db(session=session)
            plan_name = await cls._get_plan_name(session=session, plan_id=plan_id)

            pending_dynamics: List[CaseStepDynamic] = []
            for case_id, old_record in old_records.items():
                old_data = {k: old_record[k] for k in changed_fields}

                # 跳过无实际变更的记录（统一用 str 比对，兼容 int/str 历史数据）
                if all(str(old_data.get(k)) == str(values.get(k)) for k in changed_fields):
                    continue

                diff_info = renderer.diff_plan_case_dict(old_data, values)
                if not diff_info:
                    continue

                log.debug(f"用例 {case_id} 变更: {diff_info}")
                pending_dynamics.append(
                    CaseStepDynamic(
                        description=(
                            f"{user.username} 更新了计划【{plan_name}】中的用例 :{diff_info}"
                        ),
                        test_case_id=case_id,
                        plan_id=plan_id,
                        creator=user.id,
                        creatorName=user.username,
                    )
                )

            if pending_dynamics:
                session.add_all(pending_dynamics)
                # 单次 flush：N 条 dynamic 从 N*2 次 IO 降到 1 次
                await session.flush()

            return update_result.rowcount

    # ------------------------------------------------------------------
    #  单 case 拖拽 / 跨 module 移动
    # ------------------------------------------------------------------

    @classmethod
    async def reorder_plan_case(
        cls,
        plan_id: int,
        case_id: int,
        before_id: Optional[int] = None,
        after_id: Optional[int] = None,
        target_module_id: Optional[int] = None,
    ) -> int:
        """单 case 移动 / 跨 module 移动（推荐走 ``reorder_plan_cases_bulk``）。

        实现：开 1 个事务 → 越权前置校验 → 调一次
        ``_apply_single_reorder`` 完成单 case 重排。

        复杂度（单条）
        --------
        - 1 次 SELECT (读 module 全量)
        - 1 次 UPDATE (整组回写 order，可顺带切 module)
        - 1 次越权校验 SELECT
        - IO 共 3 次，与目标 module 的 case 数无关

        Args:
            plan_id: 计划ID
            case_id: 被移动的用例ID
            before_id: 锚点：被移动 case 放在此 case 之前
            after_id: 锚点：被移动 case 放在此 case 之后
            target_module_id: 目标分组；None 表示不切换 module

        Returns:
            int: 实际更新行数；位置无变化且 module 未切换时返回 0（幂等）

        Raises:
            CommonError: 越权 / 用例不存在 / 锚点不在目标 module 等业务错误
        """
        async with cls.transaction() as session:
            # 越权前置：所有 case_id + 锚点都需属于 plan
            await cls._assert_cases_belong_to_plan(
                session=session,
                plan_id=plan_id,
                case_ids=[case_id, before_id, after_id],
            )
            return await cls._apply_single_reorder(
                session=session,
                plan_id=plan_id,
                case_id=case_id,
                before_id=before_id,
                after_id=after_id,
                target_module_id=target_module_id,
            )

    @classmethod
    async def reorder_plan_cases_bulk(
        cls,
        plan_id: int,
        items: List[Dict[str, Any]],
    ) -> List[int]:
        """批量重排序（多选拖拽 / 跨 module 批量调整）。

        行为
        ----
        - 所有 items 在 **同一事务** 内顺序应用；任一失败整体回滚
        - 越权前置：聚合所有 case_id + 锚点去重后一次性校验，
          避免每条都重复一次 SELECT

        复杂度
        --------
        - 1 次越权校验 SELECT（聚合 N 条的所有 case_id + 锚点）
        - N 次 _apply_single_reorder，每次含 1 次 SELECT + 1 次 UPDATE
        - 总 IO = 1 + 2N
        - 相比循环调单条接口：省去 N-1 次事务提交 + N-1 次越权校验
          = 节省 2(N-1) 次 IO + N 次 BEGIN/COMMIT

        Args:
            plan_id: 计划ID
            items: 重排序条目列表，每条形如
                ``{"case_id": int, "before_id"?: int, "after_id"?: int, "target_module_id"?: int}``

        Returns:
            List[int]: 每条 item 的 affected 行数（与 items 等长），
                0 表示该条幂等无变化

        Raises:
            CommonError: items 为空 / 越权 / 用例不存在 / 锚点非法
        """
        if not items:
            raise CommonError("批量重排序 items 不能为空")

        # 1) 聚合所有需要校验的 case_id（去重 + 过滤 None）
        all_ids: set = set()
        for it in items:
            cid = it.get("case_id")
            if cid is None:
                raise CommonError("item.case_id 不能为空")
            all_ids.add(cid)
            for anchor_key in ("before_id", "after_id"):
                v = it.get(anchor_key)
                if v is not None:
                    all_ids.add(v)

        async with cls.transaction() as session:
            # 2) 一次越权前置
            await cls._assert_cases_belong_to_plan(
                session=session,
                plan_id=plan_id,
                case_ids=list(all_ids),
            )

            # 3) 顺序应用每条（同一事务内复用 session）
            results: List[int] = []
            for it in items:
                affected = await cls._apply_single_reorder(
                    session=session,
                    plan_id=plan_id,
                    case_id=it["case_id"],
                    before_id=it.get("before_id"),
                    after_id=it.get("after_id"),
                    target_module_id=it.get("target_module_id"),
                )
                results.append(affected)

            log.info(
                f"reorder_plan_cases_bulk plan={plan_id} items={len(items)} total_affected={sum(results)}"
            )
            return results

    @classmethod
    async def _assert_cases_belong_to_plan(
        cls,
        session: AsyncSession,
        plan_id: int,
        case_ids: List[Optional[int]],
    ) -> None:
        """断言所有非 None 的 case_id 都属于 plan，否则抛 ``CommonError``。

        与 ``_filter_case_ids_belong_to_plan`` 共享同一底层 SELECT，
        但语义更严格：缺失即失败，而非返回子集。
        """
        valid_ids = [cid for cid in case_ids if cid is not None]
        if not valid_ids:
            return
        existing = await cls._filter_case_ids_belong_to_plan(
            session=session,
            plan_id=plan_id,
            case_id_list=valid_ids,
        )
        missing = set(valid_ids) - existing
        if missing:
            raise CommonError(
                f"以下 case 不属于计划 {plan_id}，已拒绝: {sorted(missing)[:5]}"
            )

    @classmethod
    async def _apply_single_reorder(
        cls,
        session: AsyncSession,
        plan_id: int,
        case_id: int,
        before_id: Optional[int],
        after_id: Optional[int],
        target_module_id: Optional[int],
    ) -> int:
        """应用单条重排序（核心执行逻辑）。

        假设：调用方已在事务中持有 ``session``，且 case_id + 锚点已通过越权校验。
        内部不做任何额外 session 开关或权限检查。

        步骤
        ----
        1. 读 case 当前所在 module
        2. 读目标 module 全量 case 序列（按 order）
        3. 按锚点计算新下标
        4. 内存 pop + insert 重排
        5. 单条 ``UPDATE ... CASE`` 一次回写 order；跨 module 顺带改 plan_module_id

        Returns:
            int: affected 行数；幂等时返回 0
        """
        # 1) 当前 module
        origin_stmt = select(PlanCaseAssociation.plan_module_id).where(
            and_(
                PlanCaseAssociation.plan_id == plan_id,
                PlanCaseAssociation.case_id == case_id,
            )
        )
        origin_module_id = (await session.execute(origin_stmt)).scalar_one_or_none()
        if origin_module_id is None:
            raise CommonError(f"用例 {case_id} 不在计划 {plan_id} 中")

        target_module_id = (
            target_module_id if target_module_id is not None else origin_module_id
        )

        # 2) 目标 module 全量
        list_stmt = (
            select(PlanCaseAssociation.case_id)
            .where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.plan_module_id == target_module_id,
                )
            )
            .order_by(PlanCaseAssociation.order.asc(), PlanCaseAssociation.case_id.asc())
        )
        case_ids_in_module: List[int] = [
            row[0] for row in (await session.execute(list_stmt)).all()
        ]

        # 3) 新下标
        new_index = cls._resolve_reorder_index(
            case_ids=case_ids_in_module,
            moved_id=case_id,
            before_id=before_id,
            after_id=after_id,
        )

        # 4) 内存重排：区分同 module / 跨 module 两种场景
        #    - 同 module：case_id 在 list 中 → pop + insert 调位
        #    - 跨 module：case_id 不在 list 中（要搬过来）→ 直接按 new_index 插入
        is_cross_module = target_module_id != origin_module_id
        if case_id in case_ids_in_module:
            old_index = case_ids_in_module.index(case_id)
            if new_index == old_index and not is_cross_module:
                return 0  # 幂等（同 module 且位置未变）
            case_ids_in_module.pop(old_index)
            insert_index = new_index if new_index <= old_index else new_index - 1
        else:
            # 跨 module：当作新成员，按 new_index 插入
            # new_index 已被 _resolve_reorder_index 钳到 [0, len(list)]
            insert_index = min(new_index, len(case_ids_in_module))
        case_ids_in_module.insert(insert_index, case_id)

        # 5) 单条 UPDATE 回写
        order_case = case(
            *[
                (PlanCaseAssociation.case_id == cid, idx)
                for idx, cid in enumerate(case_ids_in_module, start=1)
            ],
            else_=PlanCaseAssociation.order,
        )
        update_values: Dict[str, Any] = {"order": order_case}
        if target_module_id != origin_module_id:
            update_values["plan_module_id"] = target_module_id

        update_stmt = (
            update(PlanCaseAssociation)
            .where(
                and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_ids_in_module),
                )
            )
            .values(update_values)
        )
        result = await session.execute(update_stmt)
        # 日志：跨 module 时 old_index 记为 None（语义上 case 不在原列表中）
        log.debug(
            f"_apply_single_reorder plan={plan_id} case={case_id} "
            f"old={old_index if 'old_index' in locals() else None} new={new_index} "
            f"module={origin_module_id}→{target_module_id} affected={result.rowcount}"
        )
        return result.rowcount

    @staticmethod
    def _resolve_reorder_index(
        case_ids: List[int],
        moved_id: int,
        before_id: Optional[int],
        after_id: Optional[int],
    ) -> int:
        """根据锚点解析被移动 case 的新下标。

        规则
        ----
        - ``before_id`` 优先：返回 ``before_id`` 在当前列表中的下标
        - ``after_id`` 次之：返回 ``after_id`` 在当前列表中下标 + 1
        - 都为空：返回 ``len(case_ids)``（追加到末尾）

        锚点不在列表时（极端 case：刚被删除/换 module），
        一律回退到末尾，避免越界。
        """
        if before_id is not None and before_id in case_ids:
            return case_ids.index(before_id)
        if after_id is not None and after_id in case_ids:
            return case_ids.index(after_id) + 1
        return len(case_ids)

    @classmethod
    async def _filter_case_ids_belong_to_plan(
        cls,
        session: AsyncSession,
        plan_id: int,
        case_id_list: List[int],
    ) -> set:
        """校验并返回 plan 下真实存在的 case_id 集合。

        越权防护：调用方传 ``(plan_id, case_id_list)`` 时，先用一次 SELECT
        过滤出真正属于该计划的 case_id，供调用方与入参做差集。
        """
        if not case_id_list:
            return set()
        stmt = select(PlanCaseAssociation.case_id).where(
            and_(
                PlanCaseAssociation.plan_id == plan_id,
                PlanCaseAssociation.case_id.in_(case_id_list),
            )
        )
        result = await session.execute(stmt)
        return {row[0] for row in result.all()}

    @classmethod
    async def _sync_step_result_status(
        cls,
        session: AsyncSession,
        plan_id: int,
        case_id_list: List[int],
        status: str,
        status_field: str,
    ) -> int:
        """同步 upsert 计划下用例的子步骤结果状态。

        行为：把 ``case_id_list`` 下所有步骤对应的 ``(plan_id, step_id)`` 行
        的 ``status_field`` 列设为 ``status``。

        - 已有 ``TestCaseStepResult`` 行 → 仅更新 ``status_field``，
          **不动** ``actual_result`` / ``bug_url`` / 另一个 status 列
        - 没有 result 行 → 新建一行（其余列 NULL）

        实现：先一次 SELECT 拿到所有 ``step_id``，
        再用 ``INSERT ... ON DUPLICATE KEY UPDATE`` 批量 upsert，
        利用 ``(plan_id, step_id)`` 唯一约束触发冲突分支。

        父级 → 子级的覆盖是单向的：原 status 被新值直接覆盖，无法回退。

        Args:
            session: 数据库会话
            plan_id: 计划ID
            case_id_list: 用例ID列表
            status: 状态值字符串
                （``"0"`` 未开始 / ``"1"`` 通过 / ``"2"`` 失败 / ``"3"`` 阻塞 / ``"4"`` 跳过）
            status_field: 要更新的状态字段名（``"first_status"`` / ``"second_status"``）

        Returns:
            int: 实际 upsert 的步骤数；字段名无效或无步骤时返回 0
        """
        target_column = cls._resolve_status_column(status_field)
        if target_column is None:
            return 0

        # 1) 找到这些 case 下的所有 step_id
        step_id_rows = await session.execute(
            select(TestCaseStep.id).where(TestCaseStep.test_case_id.in_(case_id_list))
        )
        step_ids = [row[0] for row in step_id_rows.all()]
        if not step_ids:
            return 0

        # 2) 批量 upsert：插入时同时写入 target status（满足 NOT NULL 列），
        #    冲突时仅更新 target_column，不覆盖 actual_result / bug_url / 另一 status
        insert_values = [
            {
                "plan_id": plan_id,
                "step_id": step_id,
                target_column.key: status,
            }
            for step_id in step_ids
        ]
        upsert_stmt = mysql_insert(TestCaseStepResult).values(insert_values)
        upsert_stmt = upsert_stmt.on_duplicate_key_update(
            **{target_column.key: status}
        )
        await session.execute(upsert_stmt)

        field_label = cls._STATUS_FIELD_LABEL_MAP.get(status_field, '未知')
        log.info(
            f"同步 upsert 计划{plan_id}下{len(case_id_list)}个用例的{len(step_ids)}个子步骤"
            f"{field_label}为{status}"
        )
        return len(step_ids)

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
            # 1) 查询原用例的排序号
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

            # 2) 复制用例及其子步骤（test_case 主表 + case_sub_step）
            new_cases = await TestCaseMapper.copy_cases(
                case_ids=[case_id],
                user=user,
                session=session
            )
            if not new_cases:
                return 0

            # 3) 创建新关联，排在原用例之后。
            #    排序调整交给 associate_cases 内部处理（整 plan order >= origin+1 全部后移），
            #    避免跨 module 时只 +1 目标 module 的旧实现造成 order 冲突。
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
        is_review: Optional[str] = None
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
            is_review: 是否审核（``"0"`` 未审核 / ``"1"`` 已审核）

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

        # 4) 拉取该 plan 下所有 plan_modules，构建双重索引
        #    - plan_mod_index:        (title, parent_id)   → 兼容旧数据 & 手动分组
        #    - plan_mod_by_source_id: (source_module_id, parent_id) → 精确匹配
        plan_mod_stmt = select(PlanModule).where(PlanModule.plan_id == plan_id)
        plan_modules = (await sess.execute(plan_mod_stmt)).scalars().all()
        plan_mod_index: Dict[tuple, PlanModule] = {
            (pm.title, pm.parent_id): pm for pm in plan_modules
        }
        plan_mod_by_source_id: Dict[tuple, PlanModule] = {
            (pm.source_module_id, pm.parent_id): pm
            for pm in plan_modules
            if pm.source_module_id is not None
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
        #    build_path 自然保证父级先于子级被处理（沿 parent 链上溯）
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
                # 第一层：按 source_module_id + parent_id 精确匹配（双向同步核心）
                exact_key = (node.id, current_parent_id)
                existing = plan_mod_by_source_id.get(exact_key)
                if existing is not None:
                    current_parent_id = existing.id
                    continue

                # 第二层：fallback 到 title + parent_id 兼容匹配（旧数据 & 手动分组）
                fuzzy_key = (node.title, current_parent_id)
                existing = plan_mod_index.get(fuzzy_key)
                if existing is not None:
                    if existing.source_module_id is None:
                        # 回填：老数据没有 source_module_id，现在知道它来自当前 Module
                        existing.source_module_id = node.id
                        await sess.flush()
                        plan_mod_by_source_id[exact_key] = existing
                        log.info(
                            f"_resolve_source_to_plan_module_map: 回填 plan_module_id={existing.id} "
                            f"source_module_id={node.id} title={node.title}"
                        )
                    elif existing.source_module_id != node.id:
                        # 防御：同一 (plan_id, title, parent_id) 对应了不同的 Module
                        # 保留现有 source_module_id，不覆盖，仅告警
                        log.warning(
                            f"_resolve_source_to_plan_module_map: source_module_id 冲突 "
                            f"plan_module_id={existing.id} 现有={existing.source_module_id} 新={node.id} title={node.title}"
                        )
                    current_parent_id = existing.id
                    continue

                # 新建 PlanModule，写入 source_module_id 建立持久化关联
                new_pm = PlanModule(
                    plan_id=plan_id,
                    title=node.title,
                    parent_id=current_parent_id,
                    source_module_id=node.id,
                    order=0,
                )
                if user is not None:
                    new_pm.creator = user.id
                    new_pm.creatorName = user.username
                sess.add(new_pm)
                await sess.flush()
                # 同步到两个索引，避免同批次重复创建
                plan_mod_index[fuzzy_key] = new_pm
                plan_mod_by_source_id[exact_key] = new_pm
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

            # 4) 处理排序：
            #    - 显式传 order：在指定位置插入（后移已有 order >= order 的记录）
            #    - 不传 order：追加到 plan 末尾（max + 1）
            if order is not None:
                # 指定位置插入：后移已有记录，避免 order 冲突
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
                cursor = order
            else:
                # 追加到末尾
                max_order_stmt = select(
                    func.coalesce(func.max(PlanCaseAssociation.order), 0)
                ).where(PlanCaseAssociation.plan_id == plan_id)
                max_result = await sess.execute(max_order_stmt)
                cursor = (max_result.scalar() or 0) + 1

            # 防御性兜底：plan_module_id 为 None 时取 plan 根
            # 避免 mode2 下 case 在 source 树外时插入 NULL 触发 NOT NULL
            fallback_module_id = plan_module_id
            if fallback_module_id is None:
                root = (
                    await sess.execute(
                        select(PlanModule)
                        .where(
                            PlanModule.plan_id == plan_id,
                            PlanModule.parent_id.is_(None),
                        )
                        .limit(1)
                    )
                ).scalars().first()
                if root is not None:
                    fallback_module_id = root.id
                else:
                    log.error(
                        f"associate_cases: plan {plan_id} has no root module, "
                        f"cannot fall back plan_module_id"
                    )
                    return 0

            values = []
            for case_id in new_case_ids:
                pm_id = case_to_plan_module.get(case_id) or fallback_module_id
                values.append(
                    {
                        "plan_id": plan_id,
                        "plan_module_id": pm_id,
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
        except Exception:
            # log.exception 自动带 stacktrace + 函数上下文
            log.exception("associate_cases 异常")
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
    async def delete_plan_cases_permanent(
        cls,
        case_ids: List[int],
        plan_id: int,
    ) -> int:
        """
        彻底删除计划下的用例：解除当前计划关联 + 数据库物理删除用例本体及其子步骤。

        执行顺序（同一事务内）：
        1) 校验所有 case_id 属于该 plan（防越权/无效入参）
        2) 删 plan_case_association（仅当前 plan 的关联）
        3) 删 case_sub_step（先删子表，避免外键悬空）
        4) 删 test_case 本体

        严格模式：如果用例还被其他 plan 引用，test_case 上的 FK CASCADE 触发
        SQLAlchemy IntegrityError，整个事务回滚。提示用户先在其他计划中
        移除/删除该用例，再回到本计划执行彻底删除。
        """
        from sqlalchemy.exc import IntegrityError

        if not case_ids:
            return 0

        async with cls.transaction() as session:
            # 1) 越权前置校验：所有 case_id 必须属于该 plan
            await cls._assert_cases_belong_to_plan(session, plan_id, case_ids)

            # 2) 删当前 plan 的关联（只解除本计划的关联）
            await session.execute(
                delete(PlanCaseAssociation).where(and_(
                    PlanCaseAssociation.plan_id == plan_id,
                    PlanCaseAssociation.case_id.in_(case_ids),
                ))
            )

            # 3) 显式删子步骤（防 SQLAlchemy session 缓存 / 跨库 FK 行为差异）
            await session.execute(
                delete(TestCaseStep).where(
                    TestCaseStep.test_case_id.in_(case_ids)
                )
            )

            # 4) 删用例本体；若仍被其他 plan 引用，触发 FK CASCADE 删除其他
            #    关联；若 FK 报错（如严格模式），IntegrityError 上抛，事务回滚
            result = await session.execute(
                delete(TestCase).where(TestCase.id.in_(case_ids))
            )
            return result.rowcount

    @classmethod
    async def update_case_status(
        cls,
        plan_case_id: int,
        user: User,
        is_review: Optional[str] = None,
        first_status: Optional[str] = None,
        second_status: Optional[str] = None,
        bug_url: Optional[str] = None,
    ) -> PlanCaseAssociation:
        """
        更新单条用例关联状态

        通过计划用例关联ID定位记录，仅更新非 None 的字段。
        更新前后会记录操作动态。

        Args:
            plan_case_id: 计划用例关联ID（作为 update_by_id 的查询条件）
            user: 操作用户
            is_review: 是否审核（``"0"`` 未审核 / ``"1"`` 已审核）
            first_status: 一轮测试状态
                （``"0"`` 未开始 / ``"1"`` 通过 / ``"2"`` 失败 / ``"3"`` 阻塞 / ``"4"`` 跳过）
            second_status: 二轮测试状态（取值同上）
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
    ) -> List[Dict[str, Any]]:
        """获取计划用例列表（含步骤及步骤执行结果）。

        性能策略
        --------
        1. 2 次查询（cases + steps）替代 1 次 JOIN，避免步骤笛卡尔积导致数据膨胀
        2. 步骤用 ``defaultdict`` 按 case_id 聚合，O(N) 合并
        3. 分组筛选用 1 条递归 CTE 一次性展开整棵 plan_module 子树，单 SQL 搞定
        4. 早返回：主查询无结果时直接 ``[]``，避免再发步骤查询

        筛选语义
        --------
        - ``plan_module_id``：包含该分组及其**所有层级**子分组下的用例（递归 CTE）
        - ``case_level``：精确匹配（如 ``"P0"``）
        - ``is_review``：精确匹配（0/1）

        Args:
            plan_id: 计划 ID。
            plan_module_id: 计划分组 ID（含其整棵子树）。
            case_level: 用例等级。
            is_review: 是否审核（0/1）。

        Returns:
            用例字典列表，每项包含用例信息 + 关联属性 + ``case_sub_steps``。
        """
        log.debug(
            f"get_plan_cases start: plan_id={plan_id}, plan_module_id={plan_module_id}, "
            f"case_level={case_level}, is_review={is_review}",
        )

        async with cls.transaction() as session:
            # 1) 拼 WHERE 条件（包含递归 CTE 一次性展开分组子树）
            conditions = cls._build_plan_case_conditions(
                plan_id=plan_id,
                plan_module_id=plan_module_id,
                case_level=case_level,
                is_review=is_review,
            )

            # 2) 拉主表 (关联, 用例) 行
            rows = await cls._fetch_plan_case_rows(session, conditions)
            if not rows:
                # 早返回：主表为空就不发第二步查询，省一次 RTT
                return []

            # 3) 拉这些用例的步骤 + 当前计划下的执行结果，按 case_id 聚合
            case_ids = [case.id for _, case in rows]
            step_map = await cls._fetch_step_map(
                session, plan_id=plan_id, case_ids=case_ids,
            )

            # 4) 拼装返回 payload
            return [cls._build_case_payload(assoc, case, step_map) for assoc, case in rows]

    # ------------------------------------------------------------------
    # 内部 helper：get_plan_cases 的拆解
    # ------------------------------------------------------------------

    @staticmethod
    def _build_plan_case_conditions(
        plan_id: int,
        plan_module_id: Optional[int],
        case_level: Optional[str],
        is_review: Optional[int],
    ) -> List:
        """组装 plan_case 主查询的 WHERE 条件列表。

        关键点：``plan_module_id`` 命中时用**递归 CTE**把整棵子树展平，
        而不是之前 ``parent_id == X OR id == X``（那样只匹配直接子节点，
        会漏掉深层孙子辈的用例）。
        """
        conditions: List = [PlanCaseAssociation.plan_id == plan_id]

        if plan_module_id is not None:
            # 递归 CTE：根节点 ∪ 所有 parent_id 命中的后代
            base = select(PlanModule.id).where(PlanModule.id == plan_module_id)
            subtree = base.cte(name="plan_module_subtree", recursive=True)
            subtree = subtree.union_all(
                select(PlanModule.id).where(PlanModule.parent_id == subtree.c.id)
            )
            conditions.append(
                PlanCaseAssociation.plan_module_id.in_(select(subtree.c.id))
            )

        if case_level is not None:
            conditions.append(TestCase.case_level == case_level)
        if is_review is not None:
            conditions.append(PlanCaseAssociation.is_review == is_review)

        return conditions

    @staticmethod
    async def _fetch_plan_case_rows(
        session: AsyncSession,
        conditions: List,
    ) -> List[Tuple[PlanCaseAssociation, TestCase]]:
        """主查询：拉取 (PlanCaseAssociation, TestCase) 关联行。

        用 ``order_by(PlanCaseAssociation.order)`` 保持原有用例顺序，
        ``result.unique()`` 避免 ORM 重复实例化。
        """
        stmt = (
            select(PlanCaseAssociation, TestCase)
            .join(TestCase, TestCase.id == PlanCaseAssociation.case_id)
            .where(and_(*conditions))
            .order_by(PlanCaseAssociation.order)
        )
        result = await session.execute(stmt)
        return result.unique().all()

    @staticmethod
    async def _fetch_step_map(
        session: AsyncSession,
        plan_id: int,
        case_ids: List[int],
    ) -> Dict[int, List[Dict[str, Any]]]:
        """拉取 (步骤, 步骤执行结果)，按 ``case_id`` 聚合成 ``defaultdict(list)``。

        LEFT JOIN：步骤无执行结果时 ``step_result`` 为 None，由
        ``_step_to_dict`` 兜底填充 ``first_status=0/second_status=0``。
        """
        stmt = (
            select(TestCaseStep, TestCaseStepResult)
            .outerjoin(
                TestCaseStepResult,
                and_(
                    TestCaseStepResult.step_id == TestCaseStep.id,
                    TestCaseStepResult.plan_id == plan_id,
                ),
            )
            .where(TestCaseStep.test_case_id.in_(case_ids))
            .order_by(TestCaseStep.order)
        )
        rows = (await session.execute(stmt)).all()

        step_map: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for step, step_result in rows:
            step_map[step.test_case_id].append(_step_to_dict(step, step_result))
        return step_map

    @staticmethod
    def _build_case_payload(
        assoc: PlanCaseAssociation,
        case: TestCase,
        step_map: Dict[int, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """把 (关联, 用例) + 该用例的步骤列表，合并为最终返回的 dict。"""
        return {
            **case.to_dict(),
            "case_id": assoc.case_id,
            "plan_module_id": assoc.plan_module_id,
            "is_review": assoc.is_review,
            "first_status": assoc.first_status,
            "second_status": assoc.second_status,
            "bug_url": assoc.bug_url,
            "order": assoc.order,
            "case_sub_steps": step_map.get(case.id, []),
        }

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

            # first_status / second_status 在数据库中是 String(255) 类型,
            # 状态值走配置中心 (CaseConfig.value) 统一为字符串 ('1','2','3','4','0'),
            # 用 int 索引 Dict 永远查不到 —— 转 str 后再查
            first_passed = first_status_counts.get("1", 0)
            first_failed = first_status_counts.get("2", 0)
            second_passed = second_status_counts.get("1", 0)
            second_failed = second_status_counts.get("2", 0)

            # 缺陷链接统计
            # 实际业务里 bug_url 写入到「步骤结果」表 (TestCaseStepResult.bug_url)，
            # 不是计划关联表 (PlanCaseAssociation.bug_url)，原 SQL 走错位置导致 bug_total 永远 0。
            # 这里改成从 step_result 取，并 join 步骤 / 用例拿到 case_name + step_order，
            # 前端可以展示成「用例名 · 步骤n · 链接」的形式。
            bug_stmt = (
                select(
                    TestCaseStepResult.bug_url,
                    TestCase.case_name,
                    TestCaseStep.order.label("step_order"),
                    TestCaseStep.id.label("step_id"),
                )
                .join(TestCaseStep, TestCaseStep.id == TestCaseStepResult.step_id)
                .join(TestCase, TestCase.id == TestCaseStep.test_case_id)
                .where(
                    and_(
                        TestCaseStepResult.plan_id == plan_id,
                        TestCaseStepResult.bug_url.isnot(None),
                        TestCaseStepResult.bug_url != "",
                    )
                )
                .order_by(TestCaseStepResult.id.desc())
            )
            bug_result = await session.execute(bug_stmt)
            bug_rows = bug_result.all()
            # 同链接可能在多个步骤上重复提交，去重保留首次出现
            bug_list: List[Dict[str, Any]] = []
            seen_urls: set = set()
            for row in bug_rows:
                url = row.bug_url
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                bug_list.append({
                    "case_name": row.case_name,
                    "step_id": row.step_id,
                    "step_order": row.step_order,
                    "bug_url": url,
                })

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
                "bug_total": len(bug_list),
                "bug_list": bug_list,
                # 兼容字段: 历史前端若仍读 bug_urls 不会爆, 拿到一个去重后的 url 列表
                "bug_urls": [item["bug_url"] for item in bug_list],
                "requirement_total": requirement_total,
                "requirement_completed": requirement_completed,
                "requirement_completion_rate": requirement_completion_rate
            }

    @classmethod
    async def get_statistics(cls, plan_id: int) -> dict:
        """
        获取计划详细统计数据

        按用例等级和多轮测试状态两个维度进行分组统计。
        通过 JOIN TestCase 获取 case_level（PlanCaseAssociation 无此字段）。

        状态文案从配置中心 (CaseConfig.config_key = 'CASE_STATUS') 动态加载,
        与前端 useCaseEnumConfig('CASE_STATUS') 共用同一份数据源, 配置变更即生效.

        Args:
            plan_id: 计划ID

        Returns:
            dict: 统计数据，包含 case_by_level、case_by_first_status、case_by_second_status、daily_trend
        """
        async with cls.transaction() as session:
            # 从 CaseConfig 加载 CASE_STATUS 状态值 -> 标签 映射
            # 失败时降级为 str(value) —— 与 CaseDynamicRenderer 的 fallback 策略一致
            from app.mapper.test_case.caseConfigMapper import CaseConfigMapper
            try:
                cfg_rows = await CaseConfigMapper.query_by_key(
                    config_key="CASE_STATUS",
                    enabled_only=True,
                    session=session,
                )
                status_label_map: Dict[str, str] = {row.value: row.label for row in cfg_rows}
            except Exception as err:
                log.warning(f"get_statistics 加载 CASE_STATUS 配置失败, 降级为原始值: {err}")
                status_label_map = {}

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

            def _label_of(raw: Any) -> str:
                if raw is None:
                    return "未设置"
                key = str(raw)
                return status_label_map.get(key) or key or "未知"

            for row in rows:
                # 按等级统计
                case_by_level[row.case_level] = case_by_level.get(row.case_level, 0) + row.count

                # 按一轮状态统计（文案走配置中心）
                first_key = _label_of(row.first_status)
                case_by_first_status[first_key] = case_by_first_status.get(first_key, 0) + row.count

                # 按二轮状态统计
                second_key = _label_of(row.second_status)
                case_by_second_status[second_key] = case_by_second_status.get(second_key, 0) + row.count

            return {
                "plan_id": plan_id,
                "case_by_level": case_by_level,
                "case_by_first_status": case_by_first_status,
                "case_by_second_status": case_by_second_status,
                "daily_trend": []
            }

    @classmethod
    async def query_plan_cases_for_export(
        cls,
        plan_id: int,
        case_ids: Optional[List[int]] = None,
        plan_module_id: Optional[int] = None,
        recursive: bool = True,
    ):
        """
        拉 plan_case_association 下的用例 + 子步骤 (计划 scope).
        排序 plan_case_association.order asc, 跟 PlanCaseList 页面默认序一致.

        :param case_ids: 显式白名单. 非空时**互斥** plan_module_id 范围, 按 ID 全量查
                         (跨 plan_module 的 case_ids 仍全返回, 前提是这些 case 都属于本 plan;
                          PR-3 commit 端按 _meta 做 plan 范围严格防御).
        :param plan_module_id: 限制到某个 plan_module. case_ids 为空时生效.
        :param recursive: case_ids + plan_module_id 都为空时无效; plan_module_id 有值时:
                          - True  = plan_module_id + 所有子 plan_module (走 CTE, 避免 N+1)
                          - False = 精确 plan_module_id (旧行为, 兼容不走 recursive 的调用方)
                          默认 True, 符合"选目录 = 整个子树" 的用户直觉.
                          plan_module_id=None 时无论 recursive 真假, 都查整个 plan (旧默认).
        """
        try:
            async with cls.session_scope() as session:
                if case_ids:
                    # 白名单语义: 不限制 plan_module_id, 信任前端的 ID 选择.
                    # case_ids 限定在当前 plan 内 (base where), 跨 plan_module 全返回.
                    stmt = (
                        select(TestCase, cls.__model__.order, cls.__model__.plan_module_id)
                        .join(cls.__model__, cls.__model__.case_id == TestCase.id)
                        .where(
                            cls.__model__.plan_id == plan_id,
                            cls.__model__.case_id.in_(case_ids),
                        )
                        .order_by(cls.__model__.order.asc())
                    )
                elif plan_module_id is not None and recursive:
                    # 选目录语义: scope = plan_module_id 及其所有子 plan_module.
                    all_module_ids = await get_plan_module_subtree_ids(
                        session=session,
                        plan_id=plan_id,
                        plan_module_id=plan_module_id,
                    )
                    stmt = (
                        select(TestCase, cls.__model__.order, cls.__model__.plan_module_id)
                        .join(cls.__model__, cls.__model__.case_id == TestCase.id)
                        .where(
                            cls.__model__.plan_id == plan_id,
                            cls.__model__.plan_module_id.in_(all_module_ids),
                        )
                        .order_by(cls.__model__.order.asc())
                    )
                elif plan_module_id is not None:
                    # 精确 plan_module_id (兼容不走 recursive 的调用方)
                    stmt = (
                        select(TestCase, cls.__model__.order, cls.__model__.plan_module_id)
                        .join(cls.__model__, cls.__model__.case_id == TestCase.id)
                        .where(
                            cls.__model__.plan_id == plan_id,
                            cls.__model__.plan_module_id == plan_module_id,
                        )
                        .order_by(cls.__model__.order.asc())
                    )
                else:
                    # plan_module_id=None: 拉整个 plan 下全部用例 (旧默认行为, controller 当前走这个)
                    stmt = (
                        select(TestCase, cls.__model__.order, cls.__model__.plan_module_id)
                        .join(cls.__model__, cls.__model__.case_id == TestCase.id)
                        .where(cls.__model__.plan_id == plan_id)
                        .order_by(cls.__model__.order.asc())
                    )
                rows = (await session.execute(stmt)).all()
                if not rows:
                    return []
                ids = [case.id for case, _, _ in rows]
                step_rows = (await session.scalars(
                    select(TestCaseStep)
                    .where(TestCaseStep.test_case_id.in_(ids))
                    .order_by(TestCaseStep.test_case_id, TestCaseStep.order)
                )).all()
                steps_by_case = {}
                for s in step_rows:
                    steps_by_case.setdefault(s.test_case_id, []).append(s.to_dict())
                return [
                    {
                        **case.to_dict(),
                        "case_sub_steps": steps_by_case.get(case.id, []),
                        "plan_order": order,
                        "plan_module_id": plan_module_id,
                    }
                    for case, order, plan_module_id in rows
                ]
        except Exception as e:
            log.error(
                f"query_plan_cases_for_export error: plan_id={plan_id}, "
                f"plan_module_id={plan_module_id}, error={e}"
            )
            raise

    @classmethod
    async def build_plan_module_path_map(
        cls,
        session: AsyncSession,
        plan_id: int,
        plan_module_ids: list,
    ) -> dict:
        """plan_module_id -> 'root/.../leaf' 路径. 复用调用方 session, 一次拉全内存回溯."""
        from app.service.exportCaseService import _walk_paths
        if not plan_module_ids:
            return {}
        rows = (await session.execute(
            select(PlanModule.id, PlanModule.title, PlanModule.parent_id)
            .where(PlanModule.plan_id == plan_id)
        )).all()
        id_to_node = {r.id: (r.title, r.parent_id) for r in rows}
        return _walk_paths(id_to_node, list(plan_module_ids))

    @staticmethod
    def _map_step_id(step_data: Dict[str, Any], case_id_map: Dict[int, int]) -> Dict[str, Any]:
        """将步骤的临时索引替换为实际用例ID（flush 后调用）"""
        case_index = step_data.pop("test_case_index")
        step_data["test_case_id"] = case_id_map[case_index]
        return step_data
