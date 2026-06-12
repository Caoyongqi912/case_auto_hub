#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/12
# @Author : cyq
# @File : m2ImportService
# @Software: PyCharm
# @Desc: PR-3 Step 3 - M2 导回 commit service.
#
# 业务约定 (跟用户拍板):
# - 输入: file_md5 (preview 阶段写入 Redis 的指纹) + project_id + module_id (可选)
# - 流程:
#     1) 加载 Redis 预览缓存, 校验 template_type=M2
#     2) 拆 valid_cases -> known (有 case_id) / new (无 case_id)
#     3) known 逐 case: SELECT 拿 old_data -> diff_dict 渲染 -> UPDATE 字段
#        + 步骤全量覆盖 (DELETE+INSERT) + 写 1 条 case_dynamic
#     4) new 逐 case: 跟老 insert_upload_case 走同一条 prepare 路径 (group_path
#        解析 -> _prepare_case_data -> _prepare_steps), 不走 on_duplicate
#     5) 删行: 无操作 (DB 中对应 case 不删, 这是 M2 协议约定)
#     6) 标记 Redis committed
# - 单事务, 失败整批回滚
# - 返回: (inserted_count, updated_count, dynamic_count)
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exception import CommonError
from app.mapper.test_case.caseDynamicMapper import (
    CaseDynamicRenderer,
    M2CaseDynamicWriter,
)
from app.mapper.test_case.testcaseMapper import TestCaseMapper
from app.mapper.test_case.testCaseStepMapper import TestCaseStepMapper
from app.model.base import User
from app.model.caseHub.case_step_dynamic import CaseStepDynamic
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.test_case_step import TestCaseStep
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

    act_lines = action.strip().split("\n") if action else None
    exp_lines = expected_result.strip().split("\n") if expected_result else None
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
    - 写动态 (每个 known case UPDATE 后写 1 条 case_dynamic)
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

        # 1) 校验 template_type == M2 (防御性, FE 走 /upload/commit 不会到这里)
        if preview.get("template_type") != "M2":
            raise CommonError(
                message=(
                    f"本端点仅处理 M2 导回, 当前缓存 template_type="
                    f"{preview.get('template_type')!r}, 请走 /upload/commit"
                ),
                data={"file_md5": file_md5},
            )

        valid_cases: List[Dict[str, Any]] = preview.get("valid_cases") or []
        if not valid_cases:
            raise CommonError(
                message="没有可入库的有效用例",
                data={"file_md5": file_md5},
            )

        # 2) 拆 known / new. 业务约定: case_id 非空 (int, 非 0) = known;
        # 缺/None/0/空字符串 = new
        known_cases: List[Dict[str, Any]] = []
        new_cases: List[Dict[str, Any]] = []
        for c in valid_cases:
            cid = c.get("case_id")
            if cid is None or cid == "" or cid == 0:
                new_cases.append(c)
            else:
                known_cases.append(c)

        log.info(
            f"M2 commit: file_md5={file_md5}, project_id={project_id}, "
            f"known={len(known_cases)}, new={len(new_cases)}, "
            f"module_id={module_id}"
        )

        # 3) 单事务锚点. 失败整批回滚.
        async with TestCaseMapper.transaction() as session:
            # 3.1) known: 逐 case UPDATE + 步骤覆盖 + 写动态
            updated_count = 0
            dynamic_count = 0
            if known_cases:
                # 一次 SELECT 拿所有 old, 减少 round-trip
                known_ids = [int(c["case_id"]) for c in known_cases]
                old_map = await self._fetch_old_cases(known_ids, session)
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
                for c in known_cases:
                    cid = int(c["case_id"])
                    old_case = old_map[cid]
                    new_diff_desc = await self._apply_known_case(
                        old_case=old_case, new_case=c, user=user, session=session,
                    )
                    updated_count += 1
                    if new_diff_desc:
                        dynamic_count += 1

            # 3.2) new: 跟老 insert_upload_case 走同一套 prepare 路径
            # 包含 group_path -> module_id 校验 (在事务内, 失败整批回滚)
            inserted_count = 0
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
                if new_objects:
                    session.add_all(new_objects)
                    await session.flush()
                    # 拿新 case 的 id, 绑给 step
                    case_id_map = {i: obj.id for i, obj in enumerate(new_objects)}
                    for step in new_step_objects:
                        step.test_case_id = case_id_map[step._case_index]
                        step._case_index = None  # type: ignore[attr-defined]
                    session.add_all(new_step_objects)
                    inserted_count = len(new_objects)

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

    @staticmethod
    async def _fetch_old_cases(
        case_ids: List[int], session: AsyncSession,
    ) -> Dict[int, Dict[str, Any]]:
        """
        一次 SELECT 拿所有 old case dicts, 用 id 做 key. M2 路径 commit 阶段
        必拿 old (用于 diff 渲染), 拿不到的视为 "DB 里被删了", 整批回滚.

        :param case_ids: known case 的 id 列表
        :param session: 数据库会话
        :return: {case_id: dict_from_map_property}
        """
        if not case_ids:
            return {}
        stmt = select(TestCase).where(TestCase.id.in_(case_ids))
        rows = (await session.scalars(stmt)).all()
        return {row.id: row.map for row in rows}

    @staticmethod
    async def _apply_known_case(
        old_case: Dict[str, Any],
        new_case: Dict[str, Any],
        user: User,
        session: AsyncSession,
    ) -> Optional[str]:
        """
        单条 known case 的 UPDATE 流程:
        1) 拿 case 对象 (get_by_id)
        2) diff_dict 渲染 description
        3) UPDATE 字段
        4) 步骤全量覆盖 (DELETE + INSERT)
        5) 写 1 条 case_dynamic (有 diff 才写)

        :return: 渲染好的 diff 描述 (没变更返回 None, 用于上层 dynamic_count 计数)
        """
        case_id = int(new_case["case_id"])
        case_obj = await TestCaseMapper.get_by_id(ident=case_id, session=session)
        if case_obj is None:
            # 防御性: 上面 _fetch_old_cases 已经查过, 这里不应该 None
            raise CommonError(
                message=f"用例 {case_id} 在 commit 时被并发删除, 整批回滚",
                data={"case_id": case_id},
            )

        # 1) 准备要 UPDATE 的字段 (剔除 _row / group_path / action / expected_result / case_id)
        update_payload = _extract_case_update_payload(new_case)
        # 强制保留必要字段 (跟 update_cls 配合, 见 testcaseMapper.update_case)
        update_payload["updater"] = user.id
        update_payload["updaterName"] = user.username

        # 2) diff 渲染 (用 old 拿 case_obj.map 代替, 跟 update_dynamic 一致)
        renderer = await CaseDynamicRenderer.from_db(session=session)
        new_diff = renderer.diff_dict(old_case, update_payload)

        # 3) UPDATE 字段 (update_cls 内部会 flush)
        await TestCaseMapper.update_cls(case_obj, session, **update_payload)

        # 4) 步骤全量覆盖 (DELETE 老 + INSERT 新)
        # 注意: 这里删的仅是 case_sub_step 物理行, 跟 case_dynamic / case_plan_association
        # 无关 (FK CASCADE 不触发); 不会污染 case_dynamic 审计
        await session.execute(
            delete(TestCaseStep).where(TestCaseStep.test_case_id == case_id)
        )
        steps = _parse_steps_from_m2(
            new_case.get("action"),
            new_case.get("expected_result"),
        )
        for order, step_data in enumerate(steps):
            session.add(
                TestCaseStep(
                    test_case_id=case_id,
                    order=order,
                    action=step_data.get("action"),
                    expected_result=step_data.get("expected_result"),
                    creator=user.id,
                    creatorName=user.username,
                    updater=user.id,
                    updaterName=user.username,
                )
            )

        # 5) 写动态 (有 diff 才写)
        if new_diff:
            await M2CaseDynamicWriter.write_case_dynamic(
                cr=user, case_id=case_id,
                description=new_diff, session=session,
            )
        return new_diff

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
    从 M2 解析后的 valid_case 里抽 UPDATE 字段. 剔除:
    - case_id (主键, 不更新)
    - _row (Excel 行号, 物理存储不需要)
    - group_path (M2 库场景不更新 module_id, 跟 M2 协议一致; 用户改了分组则 case_id 命中 + 分组冲突
                  暂时按"不更新"处理, 业务约定: M2 导回只更新字段, 不动 module_id)
    - action / expected_result (拼 cell 步骤, 落库时拆, 不进 case 主表)
    - project_id (不动, 跟 update_case 语义一致)
    - id / uid / create_time / update_time / creator / creatorName (系统字段)
    """
    payload = dict(new_case)  # shallow copy
    # 业务约定: M2 导回不动 module_id (改 group_path 不会改 module_id),
    # 跟 update_cls 配合. 若用户在 Excel 里改了 group_path 不会触发
    # module_id 重新解析, 避免"导回后用例飘到别的目录"的体验陷阱.
    # 落库时 group_path 仍是原 module 里的, 用户需手动挪目录.
    for k in (
        "case_id", "_row", "group_path", "action", "expected_result",
        "project_id", "module_id", "id", "uid", "create_time",
        "update_time", "creator", "creatorName",
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
