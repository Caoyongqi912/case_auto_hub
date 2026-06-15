#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/14
# @Author : cyq
# @File : m2PlanImportService
# @Software: PyCharm
# @Desc: M2 导回 plan 路径 commit service (PR-3 plan 扩展).
#
# 业务约定 (跟用户拍板):
# - 输入: file_md5 (preview 阶段写入 Redis 的指纹) + plan_id
# - 流程:
#     1) 加载 Redis 预览缓存, 校验 template_type=M2
#     2) 拆 valid_cases -> known (有 case_id) / new (无 case_id)
#     3) known:
#        a) 改 library TestCase 字段 + 步骤覆盖 + 写 case_dynamic (M2 协议,
#           改了字段 -> library 同步, plan_id 透传让 dynamic 标"计划关联变更")
#        b) **自动补建 PlanCaseAssociation**: 如果 case 还不在本 plan,
#           拿 case 的 library module_id -> find-or-create plan_module (写
#           source_module_id) -> 建 association (append 到 plan_module 末尾).
#           这一步对应 M2 协议在 plan 场景的额外要求: "在 plan 导入就进行关联".
#           已存在的 association 不动, 不动 plan_module_id (M2 协议不动 module_id).
#     4) new:
#        a) 校验 group_path 在 library module 树存在 (缺失整批 raise)
#        b) 拿 leaf module_id -> 调 _resolve_source_to_plan_module_map
#           find-or-create 计划侧 plan_module (写入 source_module_id)
#        c) 写 TestCase (library, module_id=leaf module_id) + TestCaseStep
#        d) 写 PlanCaseAssociation (plan_id, plan_module_id, case_id, order)
#        e) 写 case_dynamic 创建审计
#     5) 标记 Redis committed
# - 单事务, 失败整批回滚
# - 返回: {inserted, updated, dynamic_count}
#
# 跟 M2ImportService 的区别:
# - M2ImportService 写 library TestCase + Step + dynamic
# - M2PlanImportService 写 library TestCase + Step + PlanCaseAssociation + dynamic
#   且 new 路径额外做 plan_module find-or-create (跟 M1 plan insert_upload_case 走同一套
#   _resolve_source_to_plan_module_map, 复用 source_module_id 持久化关联)

from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.exception import CommonError
from app.mapper.test_case.planCaseMapper import PlanCaseMapper
from app.mapper.test_case.planModuleMapper import PlanModuleMapper
from app.model.base import User
from app.model.caseHub.association import PlanCaseAssociation
from app.model.caseHub.case_step_dynamic import CaseStepDynamic
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.test_case_step import TestCaseStep
from app.model import async_session
from app.service.m2ImportService import (
    M2ImportService,
    _build_new_test_case,
    _parse_steps_from_m2,
)
from app.service.uploadCacheService import UploadCacheService
from common import rc
from utils import log


class M2PlanImportService:
    """
    PR-3 plan 扩展: M2 协议下, 测试计划导入 (导回) 的 commit 入口.
    跟 M2ImportService 平级, 不复用 commit 主体 (事务/路径差异较大, 拆开清晰).
    """

    @staticmethod
    async def _get_max_orders_per_module(
        session: AsyncSession,
        plan_id: int,
        module_ids: Set[int],
    ) -> Dict[int, int]:
        """
        按 plan_module_id 分组查当前最大 order.
        供 known auto-associate / MOVE / new 三条路径复用, 统一 SQL 结构.
        """
        if not module_ids:
            return {}
        stmt = select(
            PlanCaseAssociation.plan_module_id,
            func.max(PlanCaseAssociation.order),
        ).where(
            and_(
                PlanCaseAssociation.plan_id == plan_id,
                PlanCaseAssociation.plan_module_id.in_(module_ids),
            )
        ).group_by(PlanCaseAssociation.plan_module_id)
        rows = (await session.execute(stmt)).all()
        return {row[0]: int(row[1] or 0) for row in rows}

    def __init__(self, cache_service: Optional[UploadCacheService] = None):
        self.cache = cache_service or UploadCacheService(rc)

    async def commit(
        self,
        file_md5: str,
        plan_id: int,
        user: User,
    ) -> Dict[str, int]:
        """
        :param file_md5: preview 阶段写入 Redis 的 MD5
        :param plan_id: 目标计划 ID
        :param user: 操作用户
        :return: {inserted: N, updated: N, auto_associated: N, dynamic_count: N}
                        - auto_associated: known 路径自动补建的本 plan 关联数
                          (跨 plan 上传 / 新 plan 复用已知 case 时累加, 0 表示无新增关联)
        :raises CommonError: 缓存缺失/已提交/template_type != M2/必填失败/目录不存在
        """
        # 0/1) 加载 + 校验 (复用 M2ImportService helper, 错误信息带 plan 端点提示)
        preview = await M2ImportService._load_preview(file_md5, user, self.cache)
        valid_cases = M2ImportService._validate_m2_template(
            preview, endpoint_label=", 请走 /hub/plan/upload/commit",
        )

        # 1) 拆 known / new (复用 helper)
        known_cases, new_cases = M2ImportService._split_known_new(valid_cases)

        log.info(
            f"M2 plan commit: file_md5={file_md5}, plan_id={plan_id}, "
            f"known={len(known_cases)}, new={len(new_cases)}"
        )

        # 2) 事务外预解析: project_id + group_path -> library module_id.
        # 原因跟 M2ImportService.commit 同款 (见那里 L139-152 的注释):
        # M2ImportService._resolve_module_ids 内部会调 ModuleMapper.find_path,
        # 它用 `async with cls.session_scope() as session` (不带 session 入参)
        # 间接创建 `async with async_session() as s: yield s`. async_session 是
        # async_scoped_session (scope=current_task), 在同一 task 里返回的是同一个
        # session. 退出该上下文时会调 session.close(), 而 AsyncSession.close() 在
        # 有未提交事务时会**先 ROLLBACK 再 close** — known 路径已经 flush 的
        # UPDATE/DELETE/INSERT 会被无声回滚 (这是 #4 报告 "修改的数据没有进行
        # 更新, 新增的数据都更新了" 的根因在 plan 端的对称 bug: known 的写被回滚,
        # new 的写在 ROLLBACK 之后的新事务里 INSERT + COMMIT).
        #
        # 解决: 把 _resolve_module_ids (跟它依赖的 project_id 读取) 整个挪到
        # 事务外. 解析 + project_id 读取都是只读, 提到事务外安全.
        # case_library_module_map / known_module_id_map 此时是普通 dict, 进入
        # 事务后用即可.
        case_library_module_map: Dict[int, int] = {}
        known_module_id_map: Dict[int, int] = {}  # case_id -> 新 library module_id
        project_id: Optional[int] = None
        # known_cases 也要解析 group_path: M2 plan 路径允许 known case 改 group_path,
        # 需要同步到 case 主表 module_id + PlanCaseAssociation.plan_module_id.
        if new_cases or known_cases:
            # 2.1) 拿 plan.project_id (短 session, 读不写, 不会触发 ROLLBACK)
            from app.mapper.test_case.planMapper import PlanMapper
            async with async_session() as pre_session:
                plan = await PlanMapper.get_by_id(
                    ident=plan_id, session=pre_session,
                )
                if plan is None:
                    raise CommonError(
                        message=f"plan_id={plan_id} 不存在",
                        data={"plan_id": plan_id},
                    )
                project_id = plan.project_id

        if new_cases:
            # 2.2) new 路径: group_path -> library module_id (整批校验, 失败整批 raise)
            case_library_module_map = await M2ImportService._resolve_module_ids(
                cases=new_cases, project_id=project_id,
            )

        if known_cases:
            # 2.2b) known 路径: group_path -> library module_id.
            # 校验失败同样整批 raise (跟 new 路径同款, 不允许 Excel 里写不存在的目录).
            known_resolved_idx = await M2ImportService._resolve_module_ids(
                cases=known_cases, project_id=project_id,
            )
            for idx, c in enumerate(known_cases):
                if idx in known_resolved_idx:
                    cid = int(c["case_id"])
                    known_module_id_map[cid] = known_resolved_idx[idx]

        # 3) 单事务锚点. 失败整批回滚.
        # 跟 M2ImportService 同款: 显式 begin/commit/rollback, 绕开
        # TransactionalContext.__exit__ 状态机, 避免 "closed transaction" 报错.
        async with async_session() as session:
            try:
                await session.begin()

                # 3.0) 只有当 new_cases 为空时, project_id 还在事务内拿
                # (new 路径的 _build_new_test_case 需要它)
                if project_id is None:
                    from app.mapper.test_case.planMapper import PlanMapper
                    plan = await PlanMapper.get_by_id(
                        ident=plan_id, session=session,
                    )
                    if plan is None:
                        raise CommonError(
                            message=f"plan_id={plan_id} 不存在",
                            data={"plan_id": plan_id},
                        )
                    project_id = plan.project_id

                # 3.1) plan_root 提前拿: known 路径 auto-associate 跟 new 路径
                # 兜底都需要. 委托 PlanModuleMapper.get_or_create_root (R3 抽取,
                # 跟 init_module / find_or_create_path 共享 root 兜底逻辑).
                plan_root = await PlanModuleMapper.get_or_create_root(
                    plan_id=plan_id, user=user, session=session,
                )

                # 2.3) known: 复用 M2ImportService._apply_known_cases
                #       - 该方法只动 library TestCase + TestCaseStep + case_dynamic
                #       - 已存在的 PlanCaseAssociation 不动, 跟 M2 library 行为一致
                #       - **不存在的 PlanCaseAssociation 自动补建** (M2 plan 扩展)
                updated_count = 0
                dynamic_count = 0
                auto_assoc_count = 0
                if known_cases:
                    # _apply_known_cases 拿 old_map + 校验 missing + 逐 case UPDATE
                    # (R1 抽取, library / plan 两端共用). old_map 返回给本函数
                    # 用于 auto-associate 按 module_id 反查 plan_module, 不能再 fetch 一次.
                    uc, dc, old_map = await M2ImportService._apply_known_cases(
                        known_cases=known_cases,
                        user=user,
                        session=session,
                        file_md5=file_md5,
                        plan_id=plan_id,
                        # 透传 plan 路径解析出的 group_path -> module_id, 让
                        # _apply_known_case 把 module_id 加进 update_payload,
                        # diff_dict 自动渲染"所属目录: old -> new".
                        module_id_map=known_module_id_map,
                    )
                    updated_count += uc
                    dynamic_count += dc

                    # M2 plan 扩展: batch 查已有 PlanCaseAssociation, 区分
                    # "in plan" (跳过 auto-associate) vs "not in plan" (建关联).
                    known_ids = [int(c["case_id"]) for c in known_cases]
                    existing_assoc_stmt = select(PlanCaseAssociation.case_id).where(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_id.in_(known_ids),
                    )
                    existing_assoc_rows = (await session.execute(existing_assoc_stmt)).all()
                    existing_assoc_case_ids = {row[0] for row in existing_assoc_rows}
                    missing_assoc_ids = [
                        cid for cid in known_ids if cid not in existing_assoc_case_ids
                    ]

                    # 辅助: 拿 case 的 "有效 library module_id". 优先用 known_cases
                    # 解析出的新 module_id (group_path 改了), 兜底用 old.
                    def _effective_module_id(cid: int) -> Optional[int]:
                        if cid in known_module_id_map:
                            return known_module_id_map[cid]
                        return old_map[cid].module_id

                    # 缺失关联的 case 按 effective module_id 分组, 一次性
                    # _resolve_source_to_plan_module_map 拿 plan_module_id.
                    # 排除 module_id=None 的 case (未分组数据, 走 plan root).
                    missing_module_ids = list({
                        _effective_module_id(cid)
                        for cid in missing_assoc_ids
                        if _effective_module_id(cid) is not None
                    })
                    if missing_module_ids:
                        source_to_plan = await PlanCaseMapper._resolve_source_to_plan_module_map(
                            sess=session, plan_id=plan_id, user=user,
                            module_ids=missing_module_ids,
                        )
                    else:
                        source_to_plan = {}

                    # 按目标 plan_module_id 算 max order, 维护 per-module 游标
                    # (跟 new 路径同款, 避免重复 SQL 拼接代码)
                    target_module_ids: set = set(source_to_plan.values())
                    target_module_ids.add(plan_root.id)
                    max_order_per_module = await M2PlanImportService._get_max_orders_per_module(
                        session=session,
                        plan_id=plan_id,
                        module_ids=target_module_ids,
                    )
                    module_order_cursor: Dict[int, int] = dict(max_order_per_module)

                    # 已知 case: 仅缺失关联的补建
                    for c in known_cases:
                        cid = int(c["case_id"])
                        if cid not in missing_assoc_ids:
                            continue
                        # M2 plan 扩展: auto-associate 本 plan 没有的 case.
                        # 用 effective module_id (新解析优先) 反向定位 plan_module,
                        # 缺失或没匹配走 plan root.
                        lib_module_id = _effective_module_id(cid)
                        if lib_module_id is not None and lib_module_id in source_to_plan:
                            plan_module_id_for_case = source_to_plan[lib_module_id]
                        else:
                            plan_module_id_for_case = plan_root.id

                        module_order_cursor[plan_module_id_for_case] = (
                            module_order_cursor.get(plan_module_id_for_case, 0) + 1
                        )

                        session.add(PlanCaseAssociation(
                            plan_id=plan_id,
                            plan_module_id=plan_module_id_for_case,
                            case_id=cid,
                            order=module_order_cursor[plan_module_id_for_case],
                        ))
                        auto_assoc_count += 1
                        log.info(
                            f"M2 plan known auto-associate: case_id={cid}, "
                            f"lib_module_id={lib_module_id}, "
                            f"plan_module_id={plan_module_id_for_case}"
                        )

                    # === M2 plan MOVE: 已知 + 在 plan + group_path 改了 ===
                    # 业务: 用户在 Excel 改 known case 的 group_path, 期望:
                    #   - case 主表 module_id 跟 plan 关联都同步到新 module
                    #   - 目标 plan_module 存在 -> 更新 PlanCaseAssociation.plan_module_id
                    #   - 目标 plan_module 不存在 -> 沿源路径 find-or-create, 再更新
                    # _apply_known_case 已经把 module_id 写进 case 主表 (Patch 1 透传),
                    # 这段只负责 plan 侧: 改 association.plan_module_id + 维持 order.
                    moved_count = 0
                    moved_case_ids: Set[int] = set()
                    for c in known_cases:
                        cid = int(c["case_id"])
                        if cid not in existing_assoc_case_ids:
                            continue  # 不在 plan, auto-associate 已处理
                        new_mid = known_module_id_map.get(cid)
                        old_mid = old_map[cid].module_id
                        if new_mid is not None and new_mid != old_mid:
                            moved_case_ids.add(cid)

                    if moved_case_ids:
                        # 一次性解析所有目标 library module_id -> plan_module_id
                        # (find-or-create 复用 _resolve_source_to_plan_module_map)
                        target_mids_for_move = list({
                            known_module_id_map[cid] for cid in moved_case_ids
                        })
                        source_to_plan_move = (
                            await PlanCaseMapper._resolve_source_to_plan_module_map(
                                sess=session, plan_id=plan_id, user=user,
                                module_ids=target_mids_for_move,
                            )
                        )

                        # 算每个目标 plan_module 的 max order, 维持 per-module 游标
                        target_pmids_for_move: set = set(source_to_plan_move.values())
                        target_pmids_for_move.add(plan_root.id)
                        max_order_move = await M2PlanImportService._get_max_orders_per_module(
                            session=session,
                            plan_id=plan_id,
                            module_ids=target_pmids_for_move,
                        )
                        move_cursor: Dict[int, int] = dict(max_order_move)

                        # 拉一次这些 case 的现有 association, 内存里改 plan_module_id
                        move_assoc_stmt = select(PlanCaseAssociation).where(
                            PlanCaseAssociation.plan_id == plan_id,
                            PlanCaseAssociation.case_id.in_(list(moved_case_ids)),
                        )
                        existing_assocs = (await session.execute(move_assoc_stmt)).scalars().all()
                        assoc_by_cid: Dict[int, PlanCaseAssociation] = {
                            a.case_id: a for a in existing_assocs
                        }

                        for cid in moved_case_ids:
                            new_mid = known_module_id_map[cid]
                            new_plan_mid = source_to_plan_move.get(new_mid, plan_root.id)
                            assoc = assoc_by_cid.get(cid)
                            if assoc is None:
                                # 防御: 不该发生, 上面已确认 in existing_assoc_case_ids
                                log.warning(
                                    f"M2 plan MOVE: case_id={cid} 标在 moved 但查不到 "
                                    f"PlanCaseAssociation, 跳过"
                                )
                                continue
                            old_plan_mid = assoc.plan_module_id
                            if old_plan_mid == new_plan_mid:
                                # 目标 plan_module 跟当前一致, 不需要移动
                                log.info(
                                    f"M2 plan MOVE skip: case_id={cid}, "
                                    f"plan_module_id={new_plan_mid} (no change)"
                                )
                                continue
                            move_cursor[new_plan_mid] = (
                                move_cursor.get(new_plan_mid, 0) + 1
                            )
                            assoc.plan_module_id = new_plan_mid
                            assoc.order = move_cursor[new_plan_mid]
                            moved_count += 1
                            log.info(
                                f"M2 plan MOVE: case_id={cid}, "
                                f"lib_module_id {old_map[cid].module_id} -> {new_mid}, "
                                f"plan_module_id {old_plan_mid} -> {new_plan_mid}"
                            )

                    if moved_count:
                        log.info(
                            f"M2 plan commit: file_md5={file_md5}, plan_id={plan_id}, "
                            f"moved_count={moved_count}"
                        )

                # 2.4) new: 校验 group_path + find-or-create plan_module + 写 4 张表
                inserted_count = 0
                if new_cases:
                    # 3.3.1) case_library_module_map 已经在事务外解析 (见 2.2)
                    #        plan_root 已在 3.1 提前拿, 跳过

                    # 2.4.3) 拿 unique library module_ids, 调 _resolve_source_to_plan_module_map
                    #         一次性 find-or-create 计划侧 plan_module 树 (写 source_module_id).
                    #         跟 M1 insert_upload_case 走完全同一套逻辑, 复用最稳.
                    unique_module_ids = list(set(case_library_module_map.values()))
                    if unique_module_ids:
                        source_to_plan = await PlanCaseMapper._resolve_source_to_plan_module_map(
                            sess=session,
                            plan_id=plan_id,
                            user=user,
                            module_ids=unique_module_ids,
                        )
                    else:
                        source_to_plan = {}

                    # 2.4.4) 按 plan_module_id 分组, 各自查询最大 order, 维护 per-module 游标
                    target_module_ids: Set[int] = set(source_to_plan.values())
                    target_module_ids.add(plan_root.id)
                    max_order_per_module = await M2PlanImportService._get_max_orders_per_module(
                        session=session,
                        plan_id=plan_id,
                        module_ids=target_module_ids,
                    )
                    module_order_cursor: Dict[int, int] = dict(max_order_per_module)

                    # 2.4.5) 在内存中构造所有对象
                    case_objects: List[TestCase] = []
                    step_objects: List[TestCaseStep] = []
                    assoc_objects: List[PlanCaseAssociation] = []

                    for case_index, c in enumerate(new_cases):
                        # 优先级: group_path 解析成功 -> 用 source_to_plan 映射出的 plan_module_id
                        #         兜底 -> plan root (跟 M1 行为一致)
                        library_module_id = case_library_module_map.get(case_index)
                        if library_module_id is not None and library_module_id in source_to_plan:
                            plan_module_id_for_case = source_to_plan[library_module_id]
                        else:
                            plan_module_id_for_case = plan_root.id

                        # 写 library TestCase
                        case_obj = _build_new_test_case(
                            case_data=c,
                            project_id=project_id,
                            module_id=library_module_id,  # library 侧 module_id
                            user=user,
                        )
                        case_objects.append(case_obj)

                        # 步骤
                        steps = _parse_steps_from_m2(
                            c.get("action"), c.get("expected_result"),
                        )
                        for order, sd in enumerate(steps):
                            step = TestCaseStep(
                                order=order,
                                action=sd.get("action"),
                                expected_result=sd.get("expected_result"),
                                creator=user.id,
                                creatorName=user.username,
                                updater=user.id,
                                updaterName=user.username,
                            )
                            setattr(step, "_case_index", case_index)
                            step_objects.append(step)

                        # 游标
                        module_order_cursor[plan_module_id_for_case] = (
                            module_order_cursor.get(plan_module_id_for_case, 0) + 1
                        )

                        # PlanCaseAssociation (先占位 case_id, flush 后由 caller 替换)
                        assoc = PlanCaseAssociation(
                            plan_id=plan_id,
                            plan_module_id=plan_module_id_for_case,
                            case_id=0,  # 占位
                            order=module_order_cursor[plan_module_id_for_case],
                        )
                        setattr(assoc, "_case_index", case_index)
                        assoc_objects.append(assoc)

                    # 2.4.6) 批量 flush TestCase 拿 id
                    session.add_all(case_objects)
                    await session.flush()
                    case_id_map = {i: obj.id for i, obj in enumerate(case_objects)}

                    # 2.4.7) 绑步骤 case_id
                    for step in step_objects:
                        step.test_case_id = case_id_map[step._case_index]
                        step._case_index = None
                    session.add_all(step_objects)

                    # 2.4.8) 绑 assoc case_id
                    for assoc in assoc_objects:
                        assoc.case_id = case_id_map[assoc._case_index]
                        delattr(assoc, "_case_index")
                    session.add_all(assoc_objects)

                    # 2.4.9) 写创建动态 (跟 M1/M2 library 路径走 new_dynamic 一致)
                    # 批量构造后 add_all, 避免 N 条 new case 产生 N 次 flush.
                    dynamic_records = [
                        CaseStepDynamic(
                            description=f"{user.username} 创建了测试用例。 {case_obj.case_name}",
                            test_case_id=case_obj.id,
                            creator=user.id,
                            creatorName=user.username,
                        )
                        for case_obj in case_objects
                    ]
                    session.add_all(dynamic_records)

                    inserted_count = len(case_objects)
                    dynamic_count += len(case_objects)
                    for i, case_obj in enumerate(case_objects):
                        log.info(
                            f"M2 plan new insert: idx={i}, case_id={case_obj.id}, "
                            f'case_name={case_obj.case_name!r}, '
                            f'module_id={case_obj.module_id}'
                        )

                # 2.5) 显式 commit
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        # 3) 标记 Redis committed (事务外, 失败不影响 DB 落库)
        await self.cache.mark_committed(file_md5, user.id)

        log.info(
            f"M2 plan commit ok: file_md5={file_md5}, plan_id={plan_id}, "
            f"inserted={inserted_count}, updated={updated_count}, "
            f"dynamic_count={dynamic_count}"
        )
        return {
            "inserted": inserted_count,
            "updated": updated_count,
            "auto_associated": auto_assoc_count,
            "dynamic_count": dynamic_count,
        }

    # ---------- private helpers ----------

