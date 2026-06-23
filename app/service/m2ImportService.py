#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/12
# @Author : cyq
# @File : m2ImportService
# @Software: PyCharm
# @Desc: PR-3 Step 3 - M2 导回 commit service.

import re
from typing import Any, Dict, List, Optional, Tuple

# 预编译 M2 步骤清洗正则，避免每次解析都重新编译
_STEP_BRACKET_RE = re.compile(r"【\d+】")
_STEP_PREFIX_RE = re.compile(r"^\s*\d+[\.、)）]\s*")

from sqlalchemy import  select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exception import CommonError
from app.mapper.test_case.caseDynamicMapper import (
    CaseDynamicRenderer,
    M2CaseDynamicWriter,
)
from app.mapper.test_case.testcaseMapper import TestCaseMapper
from app.model.base import User
from app.model.caseHub.case_step_dynamic import CaseStepDynamic
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.test_case_step import TestCaseStep
from app.model import async_session
from app.service.uploadCacheService import UploadCacheService
from common import rc
from utils import log


# 跟 M1 老 insert_upload_case 保持一致. 步骤拼 cell (PR-1 写出格式) 按
# \n 拆, 配对生成 N 个 step dict.
def _parse_steps_from_m2(action: Optional[str], expected_result: Optional[str]) -> List[Dict[str, Optional[str]]]:
    """
    把 M2 拼 cell 步骤拆成 step list. 跟 _parse_steps (M1 用的) 逻辑一致,
    单独抽出来避免 M2 路径的隐式依赖.

    :param action: 步骤描述 cell 文本 (可能含 \\n)
    :param expected_result: 预期结果 cell 文本 (可能含 \\n)
    :return: [{action, expected_result}, ...]
    """
    if action is None and expected_result is None:
        # 0 步骤合法 (跟 M1 一致)
        return []

    def _clean_line(line: str) -> str:
        """
        移除行首/行中的序号标记, 跟 M1 _parse_steps 等价:
        - 【xx】 (老的中文方括号序号, DB 清洗后剥离)
        - 行首 数字+.+ (1. / 2. 等, 导回时用户手输的英文点序号)
        - 行首 数字+、+ (1、 / 2、 等, 中文顿号序号)
        - 行首 数字+)+ / 数字+)+ (1) / 2) 等, 英文/中文右括号序号)
        只剥 **行首** 序号, 避免误伤文本中的 "1.0.1" 这种版本号.
        """
        # 中文/英文方括号 (行中行首都可能, 都剥)
        line = _STEP_BRACKET_RE.sub("", line)
        # 行首数字+点/顿号/右括号 (中文右括号 ）, 英文 \))
        line = _STEP_PREFIX_RE.sub("", line)
        return line.strip()

    act_lines = [_clean_line(l) for l in str(action).strip().split("\n")] if action else None
    exp_lines = [_clean_line(l) for l in str(expected_result).strip().split("\n")] if expected_result else None
    max_steps = max(len(act_lines) if act_lines else 0, len(exp_lines) if exp_lines else 0)
    return [
        {
            "action": act_lines[i] if act_lines and i < len(act_lines) else None,
            "expected_result": exp_lines[i] if exp_lines and i < len(exp_lines) else None,
        }
        for i in range(max_steps)
    ]


class M2ImportService:
    """
    PR-3 Step 3 入口. 跟 RoundtripReader (解析) 配套: preview 阶段把 valid_cases
    写 Redis, commit 阶段从这里取出来落库.

    设计要点:
    - 不重解析 (跟 M1 insert_upload_case 一致, 复用 preview 解析结果)
    - 单事务锚点 (TestCaseMapper.transaction), 失败整批回滚
    - 不删除 (删行 = 无操作, 业务约定)
    - 写动态 (每个 known case UPDATE 后写 1 条; 每个 new case 落库后写 1 条创建动态)
    """

    def __init__(self, cache_service: Optional[UploadCacheService] = None):
        # 默认走跟 controller 同一份 redis 配置; 测试时允许注入 mock
        self.cache = cache_service or UploadCacheService(rc)

    async def commit(
        self,
        file_md5: str,
        project_id: int,
        user: User,
        module_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        入口方法. 加载 Redis 缓存 -> 校验 M2 -> 单事务落库.

        :param file_md5: preview 阶段写入 Redis 的 MD5
        :param project_id: 目标项目 ID
        :param user: 操作用户
        :param module_id: 兜底 module_id (new case 在 group_path 缺失时用,
                         跟 M1 insert_upload_case 的 module_id 兜底语义一致)
        :return: {inserted: N, updated: N, dynamic_count: N}
                       (dynamic_count = known 变更条数 + new 创建条数, 每条入库写 1 条)
        :raises CommonError: 缓存缺失/已提交/template_type != M2/必填失败/目录不存在
        """
        # 0/1) 加载 + 校验 (复用 helper, 跟 M2PlanImportService 一致)
        preview = await self._load_preview(file_md5, user, self.cache)
        valid_cases = self._validate_m2_template(
            preview, endpoint_label="",
        )
        

        # 2) 拆 known / new
        known_cases, new_cases = self._split_known_new(valid_cases)

        log.info(
            f"M2 commit: file_md5={file_md5}, project_id={project_id}, "
            f"known={len(known_cases)}, new={len(new_cases)}, "
            f"module_id={module_id}"
        )

        # 3) new 路径的准备工作 (group_path -> module_id 解析 + ORM 对象构造) 必须在
        # 事务外完成. 原因: find_group_path -> ModuleMapper.find_path 用
        # `async with cls.session_scope() as session` (不带 session 入参) 间接创建
        # `async with async_session() as s: yield s` 上下文. async_session 是
        # async_scoped_session (scope=current_task), 在同一 task 里返回的是同一个
        # session. 退出该上下文时会调 session.close(), 而 AsyncSession.close() 在有
        # 未提交事务时会**先 ROLLBACK 再 close** — known 路径已经 flush 的
        # UPDATE/DELETE/INSERT 会被无声回滚 (这是 #4 报告 "修改的数据没有进行更新,
        # 新增的数据都更新了" 的根因: known 的写被回滚, new 的写在 ROLLBACK 之后
        # 的新事务里 INSERT + COMMIT).
        #
        # 解析 + 构造都是只读 / 纯 Python, 不依赖事务状态, 提到事务外安全.
        # new_objects / new_step_objects 此时是游离 ORM 对象, 进入事务后
        # session.add_all(...) 接管即可.
        new_objects: List[TestCase] = []
        new_step_objects: List[TestCaseStep] = []
        # 业务约定 (PR-R3+ 跟 plan 对齐): group_path 改到合法目录 -> 改 module_id.
        #   - 校验: _resolve_module_ids 内部用 find_group_path (只查不建), 路径缺失
        #     整批 raise, 走不到 commit. _upload_m2_path 阶段的 validate_group_paths
        #     也已经拦截一次.
        #   - 应用: caller 拿到 module_id_map 后透传 _apply_known_cases, 跟 plan
        #     路径同款 (M2PlanImportService.commit 的 Patch 2 段).
        #   - 兜底: known case 的 group_path 缺失/空 -> 不传 module_id, _apply_known_case
        #     内部 `if new_module_id is not None and new_module_id != old` 判断会跳过,
        #     module_id 保持不变 (跟 new 路径 "group_path 空 -> 走 default_module_id" 语义对齐).
        known_module_id_map: Dict[int, int] = {}  # case_id -> 新 module_id
        if known_cases:
            known_resolved_idx = await self._resolve_module_ids(
                cases=known_cases, project_id=project_id,
            )
            for idx, c in enumerate(known_cases):
                if idx in known_resolved_idx:
                    cid = int(c["case_id"])
                    known_module_id_map[cid] = known_resolved_idx[idx]

        if new_cases:
            case_module_map = await self._resolve_module_ids(
                new_cases, project_id,
            )
            new_objects, new_step_objects = await self._prepare_new_objects(
                new_cases=new_cases,
                case_module_map=case_module_map,
                default_module_id=module_id,
                project_id=project_id,
                user=user,
            )

        # 4) 单事务锚点. 失败整批回滚.
        # 改用显式 await session.begin() / commit() / rollback(), 绕开
        # Mapper.transaction() 内部 `async with session.begin():` 走
        # TransactionalContext.__exit__ 的 commit-then-close 状态机.
        # SQLAlchemy 2.x 异步 session 在 known 路径多次 await execute/flush/add
        # 之后, 那个状态机会让 session._trans_context_manager 指向已 CLOSED 的
        # SessionTransaction, 后续 add_all(new_objects) 触发 _autobegin_t 报
        # "Can't operate on closed transaction inside context manager".
        # 显式 begin/commit/rollback 不走 __exit__, 状态机干净.
        async with async_session() as session:
            try:
                await session.begin()
                # 4.1) known: 逐 case UPDATE + 步骤覆盖 + 写动态
                # 透传 module_id_map (PR-R3+ 跟 plan 对齐: 改了 group_path -> 改 module_id).
                # _apply_known_case 内部 `if new_module_id is not None and new != old`
                # 判 None + 差异, 同 module_id 不动, group_path 缺失的 case 不传
                # module_id, 走 None 分支跳过. diff_dict 自动渲染"所属目录" 变更文案.
                updated_count, dynamic_count, _ = await self._apply_known_cases(
                    known_cases=known_cases,
                    user=user,
                    session=session,
                    file_md5=file_md5,
                    module_id_map=known_module_id_map,
                )

                # 4.2) new: 已经在事务外构造好 ORM 对象, 事务内只做 add_all + flush + 动态
                inserted_count = 0
                if new_objects:
                    session.add_all(new_objects)
                    await session.flush()
                    # 拿新 case 的 id, 绑给 step
                    case_id_map = {i: obj.id for i, obj in enumerate(new_objects)}
                    for step in new_step_objects:
                        step.test_case_id = case_id_map[step._case_index]
                        step._case_index = None  # type: ignore[attr-defined]
                    session.add_all(new_step_objects)
                    # 写创建动态 (跟 M1 走 CaseDynamicMapper.new_dynamic 一致)
                    # case_obj 此时在 session 里, case_name 直接读不触发 lazy load
                    # 批量构造后 add_all, 避免 N 条 new case 产生 N 次 flush.
                    dynamic_records = [
                        CaseStepDynamic(
                            description=f"{user.username} 创建了测试用例。 {case_obj.case_name}",
                            test_case_id=case_obj.id,
                            creator=user.id,
                            creatorName=user.username,
                        )
                        for case_obj in new_objects
                    ]
                    session.add_all(dynamic_records)
                    inserted_count = len(new_objects)
                    dynamic_count += len(new_objects)
                    for i, case_obj in enumerate(new_objects):
                        log.info(
                            f'M2 new insert: idx={i}, case_id={case_obj.id}, '
                            f'case_name={case_obj.case_name!r}, '
                            f'module_id={case_obj.module_id}'
                        )

                # 4.3) 显式 commit (不走 TransactionalContext.__exit__ 状态机)
                await session.commit()
            except Exception:
                # 显式 rollback (同上, 不走 __exit__ 兜底)
                await session.rollback()
                raise

        # 4) 标记 Redis committed (事务外, 失败不影响 DB 落库)
        await self.cache.mark_committed(file_md5, user.id)

        log.info(
            f"M2 commit ok: file_md5={file_md5}, project_id={project_id}, "
            f"inserted={inserted_count}, updated={updated_count}, "
            f"dynamic_count={dynamic_count}"
        )
        return {
            "inserted": inserted_count,
            "updated": updated_count,
            "dynamic_count": dynamic_count,
        }

    # ---------- private helpers ----------

    # ---------- 共享 helper (R1 抽取, library / plan 两端复用) ----------

    @staticmethod
    async def _load_preview(
        file_md5: str, user: User, cache: UploadCacheService,
    ) -> Dict[str, Any]:
        """加载 Redis 预览缓存 + 校验 committed 状态.

        :param cache: 调用方注入的 cache service (M2ImportService / M2PlanImportService
                       各自的 self.cache), 避免 helper 内部 new 出新实例导致
                       跟外层 mock 状态脱钩.
        """
        preview = await cache.get_preview(file_md5, user.id)
        log.debug(f"load_preview: preview={preview}")
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
        return preview

    @staticmethod
    def _validate_m2_template(
        preview: Dict[str, Any],
        endpoint_label: str,
    ) -> List[Dict[str, Any]]:
        """校验 template_type=M2, 拿非空 valid_cases.

        :param endpoint_label: 端点描述后缀, library 端传 "" (默认 /upload/commit),
                                plan 端传 ", 请走 /hub/plan/upload/commit" 之类提示.
        """
        if preview.get("template_type") != "M2":
            raise CommonError(
                message=(
                    f"本端点仅处理 M2 导回, 当前缓存 template_type="
                    f"{preview.get('template_type')!r}{endpoint_label}"
                ),
                data={"file_md5": preview.get("file_md5")},
            )
        valid_cases: List[Dict[str, Any]] = preview.get("valid_cases") or []
        if not valid_cases:
            raise CommonError(
                message="没有可入库的有效用例",
                data={"file_md5": preview.get("file_md5")},
            )
        return valid_cases

    @staticmethod
    def _split_known_new(
        valid_cases: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """拆 known / new. 业务约定: case_id 非空 (int, 非 0) = known;
        缺/None/0/空字符串 = new.
        """
        known_cases: List[Dict[str, Any]] = []
        new_cases: List[Dict[str, Any]] = []
        for c in valid_cases:
            cid = c.get("case_id")
            if cid is None or cid == "" or cid == 0:
                new_cases.append(c)
            else:
                known_cases.append(c)
        return known_cases, new_cases

    @staticmethod
    async def _apply_known_cases(
        known_cases: List[Dict[str, Any]],
        user: User,
        session: AsyncSession,
        file_md5: str,
        plan_id: Optional[int] = None,
        module_id_map: Optional[Dict[int, int]] = None,
    ) -> Tuple[int, int, Dict[int, TestCase]]:
        """known 路径主体: 拿 old_map + 校验 missing + 逐 case UPDATE.

        :param module_id_map: M2 plan 路径专用 — {case_id: 新 library module_id}.
                              来自 caller (m2PlanImportService) 解析 group_path.
                              透传给 _apply_known_case 让 case 主表 module_id 同步.
                              library 路径不传, 行为不变.
        :return: (updated_count, dynamic_count, old_map).
                  old_map 返回给 caller, plan 路径要在 known 之后做
                  auto-associate + MOVE (按 case 的 library module_id 反查 plan_module),
                  不能再 fetch 一次.
        """
        if not known_cases:
            return 0, 0, {}
        # 一次 SELECT 拿所有 old, 减少 round-trip
        known_ids = [int(c["case_id"]) for c in known_cases]
        old_map = await M2ImportService._fetch_old_cases(known_ids, session)
        # 拿不到对应的 case (DB 里被删了) -> 整批回滚
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
        updated_count = 0
        dynamic_count = 0
        for c in known_cases:
            cid = int(c["case_id"])
            case_obj = old_map[cid]
            old_case = case_obj.map
            new_mid = module_id_map.get(cid) if module_id_map else None
            # _apply_known_case 现在只在有实际变更时才写 dynamic (字段 diff 或步骤 diff).
            # 计数跟着 truthy 判断, 避免 M2 导回后每次已知 case 都 +1
            # "更新了用例步骤" 的无效审计
            new_diff_desc = await M2ImportService._apply_known_case(
                case_obj=case_obj, new_case=c, user=user, session=session,
                plan_id=plan_id,
                new_module_id=new_mid,
            )
            updated_count += 1
            if new_diff_desc is not None:
                dynamic_count += 1
            log.info(
                f"M2 known update: case_id={cid}, "
                f'old_case_name={old_case.get("case_name")!r}, '
                f'new_case_name={c.get("case_name")!r}, '
                f"new_diff_desc={new_diff_desc!r}"
            )
        return updated_count, dynamic_count, old_map

    @staticmethod
    async def _fetch_old_cases(
        case_ids: List[int], session: AsyncSession,
    ) -> Dict[int, TestCase]:
        """
        一次 SELECT 拿所有 old case ORM 对象, 用 id 做 key. M2 路径 commit 阶段
        必拿 old (用于 diff 渲染 + UPDATE), 拿不到的视为 "DB 里被删了", 整批回滚.

        :param case_ids: known case 的 id 列表
        :param session: 数据库会话
        :return: {case_id: TestCase ORM 对象}
        """
        if not case_ids:
            return {}
        stmt = select(TestCase).where(TestCase.id.in_(case_ids))
        rows = (await session.scalars(stmt)).all()
        return {row.id: row for row in rows}

    @staticmethod
    async def _apply_known_case(
        case_obj: TestCase,
        new_case: Dict[str, Any],
        user: User,
        session: AsyncSession,
        plan_id: Optional[int] = None,
        new_module_id: Optional[int] = None,
    ) -> Optional[str]:
        """
        单条 known case 的 UPDATE 流程:
        1) diff_dict 渲染 description
        2) UPDATE 字段
        3) 步骤按 order 对齐 diff 覆盖
        4) 有实际变更时写 1 条 case_dynamic

        :param case_obj: 已加载到 session 的 old case ORM 对象
        :param plan_id: 计划 ID. M2 library 路径传 None (用例自身变更);
                        M2 plan 路径传 plan_id (case_dynamic.plan_id 非空
                        标记 "计划关联变更", 跟 CaseStepDynamic.plan_id 注释对齐)
        :param new_module_id: M2 plan 路径专用 — caller 解析 group_path 得到的
                              新 library module_id, 跟 old.module_id 不一致时塞
                              update_payload, 让 diff_dict 自动产出"所属目录" 变更
                              文案, library 路径不传, 行为不变.
        :return: 渲染好的 diff 描述 (没变更返回 None, 仅用于日志/测试断言)
        """
        case_id = case_obj.id
        old_case = case_obj.map

        # 1) 准备要 UPDATE 的字段 (剔除 _row / group_path / action / expected_result / case_id)
        update_payload = _extract_case_update_payload(new_case)
        # 强制保留必要字段 (跟 update_cls 配合, 见 testcaseMapper.update_case)
        update_payload["updater"] = user.id
        update_payload["updaterName"] = user.username
        # M2 plan 路径: 用户改了 group_path, 把解析出的新 module_id 塞进 update_payload,
        # diff_dict 会自动渲染"所属目录: old -> new" 的 dynamic 文案.
        # library 路径不传 new_module_id, module_id 不进 update_payload, 行为不变.
        if new_module_id is not None and new_module_id != old_case.get("module_id"):
            update_payload["module_id"] = new_module_id

        # 2) diff 渲染 (用 old 拿 case_obj.map 代替, 跟 update_dynamic 一致)
        renderer = await CaseDynamicRenderer.from_db(session=session)
        new_diff = renderer.diff_dict(old_case, update_payload)

        # 3) UPDATE 字段 (update_cls 内部会 flush)
        # M2 路径必须 expunge=False: 同一事务内还要 add(TestCaseStep) + add(CaseStepDynamic)
        # + 可能 add_all(new_objects), 异步 session 在 expunge + 后续 add 之间偶尔会
        # 触发 _trans_context_manager 状态机异常 ("Can't operate on closed transaction").
        # 显式 begin/commit/rollback 已经绕开了一部分, 加上 expunge=False 双保险.
        await TestCaseMapper.update_cls(
            case_obj, session, expunge=False, **update_payload,
        )

        # 4) 步骤按 (order, action, expected_result) 三元组 diff 覆盖
        # 解决: 之前 DELETE+INSERT 全量覆盖导致 step_id 全变, TestCaseStepResult
        # 的 step_id FK 引用断裂 -> 一二轮测试状态丢失. 现在按 order 对齐:
        #   - 同 order + 同内容: 跳过 (id 保留, FK 不变, 一二轮状态保留)
        #   - 同 order + 不同内容: UPDATE 该行 (id 保留, FK 不变, 状态保留)
        #   - 新顺序多出来的: INSERT (拿新 id)
        #   - 老顺序多出来的: DELETE (ON DELETE CASCADE 清 result, 业务上合理)
        steps_changed = await M2ImportService._apply_known_steps(
            case_id=case_id,
            new_case=new_case,
            user=user,
            session=session,
        )

        # 5) 写动态 (有变更才写, 避免审计噪音)
        # 字段 diff 优先; 字段没变但步骤改了用 "更新了用例步骤" 兜底
        # 字段 + 步骤都没变 -> 不写 (跟 M1 老路径行为对齐, 避免 M2 导回后
        # 每次已知 case 都产生一条 "更新了用例步骤" 的无效审计)
        # plan_id: M2 library 传 None (自身变更); M2 plan 透传 plan_id (计划关联变更).
        # CaseStepDynamic.plan_id 模型字段明确语义: 空=自身变更, 非空=计划关联变更.
        if new_diff or steps_changed:
            await M2CaseDynamicWriter.write_case_dynamic(
                cr=user, case_id=case_id,
                description=new_diff or "更新了用例步骤",
                session=session,
                plan_id=plan_id,
            )
        return new_diff if new_diff else (None if not steps_changed else "更新了用例步骤")

    @staticmethod
    async def _apply_known_steps(
        case_id: int,
        new_case: Dict[str, Any],
        user: User,
        session: AsyncSession,
    ) -> bool:
        """
        按 (order, action, expected_result) 三元组对齐 diff 步骤.

        行为:
          - 同 order + 同内容: 跳过 (id 保留, TestCaseStepResult FK 不变)
          - 同 order + 不同内容: UPDATE 该行 (id 保留, FK 不变, 状态保留)
          - 新顺序多出来的: INSERT (拿新 id, 老 result 不动)
          - 老步骤多出来的: DELETE (ON DELETE CASCADE 清掉 result, 业务上合理;
                                 用户主动减少步骤 -> 一二轮状态跟着消失)

        :return: True 表示有任意步骤变更 (新增/修改/删除), False 表示完全没动.
                 caller 用它配合字段 diff 决定是否写 case_dynamic.
        """
        # 1) 拿老步骤 (按 order 排序锁定顺序, 后续按 index 对齐)
        old_steps_stmt = (
            select(TestCaseStep)
            .where(TestCaseStep.test_case_id == case_id)
            .order_by(TestCaseStep.order)
        )
        old_steps = list((await session.scalars(old_steps_stmt)).all())

        # 2) 解析新步骤 (跟原 _parse_steps_from_m2 路径一致, 拼 cell -> 拆行)
        new_steps = _parse_steps_from_m2(
            new_case.get("action"),
            new_case.get("expected_result"),
        )

        changed = False
        common_len = min(len(old_steps), len(new_steps))

        # 3) 共同 order 段: 内容相等跳过, 不等 UPDATE 该行 (id 保留)
        for order in range(common_len):
            old_step = old_steps[order]
            new_step = new_steps[order]
            new_action = new_step.get("action")
            new_expected = new_step.get("expected_result")
            if (
                old_step.action == new_action
                and old_step.expected_result == new_expected
            ):
                # 内容没变, id 保留, FK 不变, 一二轮状态保留
                continue
            # 内容变了, 原地改 ORM 对象 (id 保留, update_time 走 ORM onupdate)
            old_step.action = new_action
            old_step.expected_result = new_expected
            old_step.updater = user.id
            old_step.updaterName = user.username
            changed = True

        # 4) 新增的 order 段: INSERT (拿新 id)
        for order in range(common_len, len(new_steps)):
            new_step = new_steps[order]
            session.add(
                TestCaseStep(
                    test_case_id=case_id,
                    order=order,
                    action=new_step.get("action"),
                    expected_result=new_step.get("expected_result"),
                    creator=user.id,
                    creatorName=user.username,
                    updater=user.id,
                    updaterName=user.username,
                )
            )
            changed = True

        # 5) 老步骤多出来的: DELETE (ON DELETE CASCADE 清掉 result, 合理)
        # session.delete 不立即发 SQL, 跟前面的 add/改属性一起 flush
        for old_step in old_steps[len(new_steps):]:
            await session.delete(old_step)
            changed = True

        return changed

    @staticmethod
    async def _resolve_module_ids(
        cases: List[Dict[str, Any]], project_id: int,
    ) -> Dict[int, int]:
        """
        把 new_cases 里的 group_path 解析成 module_id. 解析失败 -> 整批 raise.
        跟 M1 insert_upload_case 的 group_path 校验逻辑保持一致.

        :param cases: new cases (case_index -> dict)
        :param project_id: 目标项目 ID
        :return: {case_index: module_id}
        """
        from utils.caseEnumResolver import find_group_path, _split_group_path

        case_module_map: Dict[int, int] = {}
        unique_path_resolved: Dict[str, Optional[int]] = {}
        invalid_paths: List[str] = []
        for idx, c in enumerate(cases):
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

        if invalid_paths:
            unique_invalid = sorted(set(invalid_paths))
            preview = unique_invalid[:5]
            more = "" if len(unique_invalid) <= 5 else f" (还有 {len(unique_invalid) - 5} 个...)"
            raise CommonError(
                message=(
                    f"用例库分组校验失败, 以下目录不存在: {preview}{more}. "
                    f"请先在用例库中创建对应目录后再导入."
                ),
                data={"invalid_paths": unique_invalid},
            )
        return case_module_map

    @staticmethod
    async def _prepare_new_objects(
        new_cases: List[Dict[str, Any]],
        case_module_map: Dict[int, int],
        default_module_id: Optional[int],
        project_id: int,
        user: User,
    ) -> Tuple[List[TestCase], List[TestCaseStep]]:
        """
        准备 new cases 的 ORM 对象 (跟 M1 _prepare_case_data / _prepare_steps 同形).
        返回 case_objects + step_objects (step 暂用 _case_index 占位, flush 后由
        调用方绑真实 test_case_id).
        """
        case_objects: List[TestCase] = []
        step_objects: List[TestCaseStep] = []

        for case_index, c in enumerate(new_cases):
            effective_module_id = case_module_map.get(case_index, default_module_id)
            case_obj = _build_new_test_case(
                case_data=c,
                project_id=project_id,
                module_id=effective_module_id,
                user=user,
            )
            case_objects.append(case_obj)

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
                # 用一个内部属性占位 case 索引, flush 后由 caller 替换成真实 id
                setattr(step, "_case_index", case_index)
                step_objects.append(step)

        return case_objects, step_objects


# ---------- module-level helpers (避免 inner function, 便于测试) ----------

def _extract_case_update_payload(new_case: Dict[str, Any]) -> Dict[str, Any]:
    """
    从 M2 解析后的 valid_case 里抽 UPDATE 字段.

    业务约定 (PR-R3+): **M2 导回能改 Excel 9 列字段** (case_name / case_setup /
    action / expected_result / case_tag / case_level / case_type / case_mark /
    group_path; 其中 action / expected_result 走 TestCaseStep 子表, 不进主表).
    加上 caller 强加的 updater / updaterName, 一共 9 个字段进 TestCase UPDATE.
    这里的"group_path 改动"会被 caller 解析成 module_id 单独加进 update_payload
    (见 _apply_known_case 的 new_module_id 分支), 不通过本函数进.

    剔除:
    - case_id (主键, 不更新)
    - _row (Excel 行号, 物理存储不需要)
    - group_path (Excel 字符串, 不进主表; 改成 module_id 走 caller 单独注入)
    - action / expected_result (拼 cell 步骤, 落库时拆, 不进 case 主表)
    - project_id / module_id (is_common 保留, 走 caller 单独注入; module_id 见上)
    - id / uid / create_time / update_time / creator / creatorName (元数据)

    跟 CaseDynamicRenderer.IGNORE_KEYS 对齐: 这里剔除的 (is_common / module_id /
    project_id) 在 diff_dict 里也走 IGNORE_KEYS, 双保险.
    """
    payload = dict(new_case)  # shallow copy
    for k in (
        # 主键 / 行号
        "case_id", "_row",
        # 步骤拼 cell 字段 (落库时拆, 不进 case 主表)
        "action", "expected_result",
        # 业务关系字段 (M2 协议不动)
        "group_path", "module_id", "project_id", "is_common",
        # 元数据
        "id", "uid", "create_time", "update_time",
        "creator", "creatorName",
    ):
        payload.pop(k, None)
    return payload


def _build_new_test_case(
    case_data: Dict[str, Any],
    project_id: int,
    module_id: Optional[int],
    user: User,
) -> TestCase:
    """
    跟 M1 _prepare_case_data 等价, 但不依赖 TestCaseMapper (避免循环引用).
    跟 _extract_case_update_payload 镜像: 同样的剔除字段, 同样的 project_id/module_id/creator 注入.
    """
    payload = _extract_case_update_payload(case_data)
    # module_id 已由 _extract_case_update_payload 剔, 走单独传参
    return TestCase(
        **payload,
        project_id=project_id,
        module_id=module_id,
        creator=user.id,
        creatorName=user.username,
        is_common=True,  # M2 库场景默认 is_common=True (跟 _upload_m2_path 一致)
    )
