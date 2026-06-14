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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exception import CommonError
from app.mapper.test_case.caseDynamicMapper import CaseDynamicMapper
from app.mapper.test_case.planCaseMapper import PlanCaseMapper
from app.model.base import User
from app.model.caseHub.association import PlanCaseAssociation
from app.model.caseHub.plan_module import PlanModule
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
        # 0) 加载 Redis 预览缓存
        preview = await self.cache.get_preview(file_md5, user.id)
        if not preview:
            raise CommonError(
                message="预览数据已过期, 请重新上传文件",
                data={"file_md5": file_md5},
            )
        if preview.get("committed"):
            raise CommonError(
                message="该文件已提交过, 不能重复提交",
                data={"file_md5": file_md5},
            )
        if preview.get("template_type") != "M2":
            raise CommonError(
                message=(
                    f"本端点仅处理 M2 导回, 当前缓存 template_type="
                    f"{preview.get('template_type')!r}, 请走 /hub/plan/upload/commit"
                ),
                data={"file_md5": file_md5},
            )

        valid_cases: List[Dict[str, Any]] = preview.get("valid_cases") or []
        if not valid_cases:
            raise CommonError(
                message="没有可入库的有效用例",
                data={"file_md5": file_md5},
            )

        # 1) 拆 known / new (跟 M2ImportService 一致)
        known_cases: List[Dict[str, Any]] = []
        new_cases: List[Dict[str, Any]] = []
        for c in valid_cases:
            cid = c.get("case_id")
            if cid is None or cid == "" or cid == 0:
                new_cases.append(c)
            else:
                known_cases.append(c)

        log.info(
            f"M2 plan commit: file_md5={file_md5}, plan_id={plan_id}, "
            f"known={len(known_cases)}, new={len(new_cases)}"
        )

        # 2) 单事务锚点. 跟 M2ImportService 同款: 显式 begin/commit/rollback
        # 绕开 TransactionalContext.__exit__ 状态机, 避免 "closed transaction" 报错.
        async with async_session() as session:
            try:
                await session.begin()

                # 2.1) 拿 plan + project_id (new 路径要 project_id 解析 group_path)
                from app.mapper.test_case.planMapper import PlanMapper
                plan = await PlanMapper.get_by_id(ident=plan_id, session=session)
                if plan is None:
                    raise CommonError(
                        message=f"plan_id={plan_id} 不存在",
                        data={"plan_id": plan_id},
                    )
                project_id = plan.project_id

                # 2.2) plan_root 提前拿: known 路径 auto-associate 跟 new 路径
                # 兜底都需要. _get_or_create_plan_root 内部会兜底新建
                # (init_module 理论上已在 plan 创建时建好, 但防御性兜底).
                plan_root = await self._get_or_create_plan_root(
                    plan_id=plan_id, user=user, session=session,
                )

                # 2.3) known: 复用 M2ImportService._apply_known_case
                #       - 该方法只动 library TestCase + TestCaseStep + case_dynamic
                #       - 已存在的 PlanCaseAssociation 不动, 跟 M2 library 行为一致
                #       - **不存在的 PlanCaseAssociation 自动补建** (M2 plan 扩展)
                updated_count = 0
                dynamic_count = 0
                auto_assoc_count = 0
                if known_cases:
                    known_ids = [int(c["case_id"]) for c in known_cases]
                    old_map = await M2ImportService._fetch_old_cases(known_ids, session)
                    missing = [cid for cid in known_ids if cid not in old_map]
                    if missing:
                        raise CommonError(
                            message=(
                                f"以下 用例ID 在数据库中不存在 (可能被删除): {missing[:5]}"
                                f"{' ...' if len(missing) > 5 else ''}. "
                                f"导回协议要求 用例ID 必须存在, 请修正 Excel 后重传"
                            ),
                            data={"missing_case_ids": missing, "file_md5": file_md5},
                        )

                    # M2 plan 扩展: batch 查已有 PlanCaseAssociation, 区分
                    # "in plan" (跳过 auto-associate) vs "not in plan" (建关联).
                    existing_assoc_stmt = select(PlanCaseAssociation.case_id).where(
                        PlanCaseAssociation.plan_id == plan_id,
                        PlanCaseAssociation.case_id.in_(known_ids),
                    )
                    existing_assoc_rows = (await session.execute(existing_assoc_stmt)).all()
                    existing_assoc_case_ids = {row[0] for row in existing_assoc_rows}
                    missing_assoc_ids = [
                        cid for cid in known_ids if cid not in existing_assoc_case_ids
                    ]

                    # 缺失关联的 case 按 library module_id 分组, 一次性
                    # _resolve_source_to_plan_module_map 拿 plan_module_id.
                    # 排除 module_id=None 的 case (未分组数据, 走 plan root).
                    missing_module_ids = list({
                        old_map[cid].get("module_id")
                        for cid in missing_assoc_ids
                        if old_map[cid].get("module_id") is not None
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
                    max_order_per_module: Dict[int, int] = {}
                    if target_module_ids and missing_assoc_ids:
                        from sqlalchemy import and_, func
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
                        max_order_per_module = {
                            row[0]: int(row[1] or 0) for row in rows
                        }
                    module_order_cursor: Dict[int, int] = dict(max_order_per_module)

                    for c in known_cases:
                        cid = int(c["case_id"])
                        old_case = old_map[cid]
                        new_diff_desc = await M2ImportService._apply_known_case(
                            old_case=old_case, new_case=c, user=user, session=session,
                            # PR-3 plan 扩展: plan 路径透传 plan_id, 写 case_dynamic 时
                            # 标记"计划关联变更" (CaseStepDynamic.plan_id 非空),
                            # 区分 library 自身变更. 不传则按 library 行为, plan_id=None.
                            plan_id=plan_id,
                        )
                        updated_count += 1
                        dynamic_count += 1
                        log.info(
                            f"M2 plan known update: case_id={cid}, "
                            f'old_case_name={old_case.get("case_name")!r}, '
                            f'new_case_name={c.get("case_name")!r}, '
                            f"new_diff_desc={new_diff_desc!r}"
                        )

                        # M2 plan 扩展: auto-associate 本 plan 没有的 case.
                        # 用 case 的 library module_id 反向定位 plan_module,
                        # 没有 module_id 或 plan_module 不存在则走 plan root.
                        if cid in missing_assoc_ids:
                            lib_module_id = old_case.get("module_id")
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

                # 2.4) new: 校验 group_path + find-or-create plan_module + 写 4 张表
                inserted_count = 0
                if new_cases:
                    # 2.4.1) 解析 group_path -> library module_id (整批校验)
                    case_library_module_map, invalid_paths = await self._resolve_new_case_library_modules(
                        new_cases=new_cases, project_id=project_id, session=session,
                    )
                    if invalid_paths:
                        unique_invalid = sorted(set(invalid_paths))
                        preview_list = unique_invalid[:5]
                        more = "" if len(unique_invalid) <= 5 else (
                            f" (还有 {len(unique_invalid) - 5} 个...)"
                        )
                        raise CommonError(
                            message=(
                                f"用例库分组校验失败, 以下目录不存在: {preview_list}{more}. "
                                f"请先在用例库中创建对应目录后再导入."
                            ),
                            data={"invalid_paths": unique_invalid},
                        )

                    # 2.4.2) plan_root 已在 2.2 提前拿, 跳过

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
                    max_order_per_module: Dict[int, int] = {}
                    if target_module_ids:
                        from sqlalchemy import and_, func
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
                        max_order_per_module = {
                            row[0]: int(row[1] or 0) for row in rows
                        }
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
                    for case_obj in case_objects:
                        await CaseDynamicMapper.new_dynamic(
                            cr=user, test_case=case_obj, session=session,
                        )

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

    @staticmethod
    async def _resolve_new_case_library_modules(
        new_cases: List[Dict[str, Any]],
        project_id: int,
        session: AsyncSession,
    ) -> Tuple[Dict[int, int], List[str]]:
        """
        解析 new_cases 里的 group_path -> library module.id.

        跟 M2 library _resolve_module_ids 逻辑一致:
        - 缺失 / 空字符串: 不校验, 落到 plan root + library 未分组 (module_id=None)
        - 非空且在 library 找不到: 整批拒 (invalid_paths)
        - 命中: 返回 {case_index: module_id}

        :return: (case_index -> module_id, invalid_paths)
        """
        from utils.caseEnumResolver import find_group_path, _split_group_path

        case_module_map: Dict[int, int] = {}
        unique_path_resolved: Dict[str, Optional[int]] = {}
        invalid_paths: List[str] = []
        for idx, c in enumerate(new_cases):
            raw_path = c.get("group_path")
            if not raw_path:
                continue
            titles = _split_group_path(raw_path)
            cache_key = "\x1f".join(titles)
            if cache_key not in unique_path_resolved:
                unique_path_resolved[cache_key] = await find_group_path(
                    project_id=project_id, raw_group_path=raw_path,
                )
            resolved = unique_path_resolved[cache_key]
            if resolved is None:
                invalid_paths.append(raw_path)
            else:
                case_module_map[idx] = resolved
        return case_module_map, invalid_paths

    @staticmethod
    async def _get_or_create_plan_root(
        plan_id: int,
        user: User,
        session: AsyncSession,
    ) -> PlanModule:
        """
        拿 plan 根 (parent_id IS NULL). 理论上 init_module 在 plan 创建时已建,
        防御性兜底: 没有则当场建一个名为"全部用例"的根.

        跟 M1 _resolve_source_to_plan_module_map 的兜底逻辑一致.
        """
        stmt = select(PlanModule).where(
            PlanModule.plan_id == plan_id,
            PlanModule.parent_id.is_(None),
        ).order_by(PlanModule.order, PlanModule.id)
        roots = (await session.execute(stmt)).scalars().all()
        if roots:
            return roots[0]
        # 兜底新建
        root = PlanModule(
            plan_id=plan_id,
            title="全部用例",
            parent_id=None,
            order=0,
            creator=user.id,
            creatorName=user.username,
        )
        session.add(root)
        await session.flush()
        log.warning(
            f"M2 plan commit: plan_id={plan_id} 没有根分组, 兜底新建 '全部用例' (id={root.id})"
        )
        return root
