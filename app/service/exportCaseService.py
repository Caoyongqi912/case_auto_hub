#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/11
# @Author : cyq
# @File : exportCaseService
# @Software: PyCharm
# @Desc: 导出-编辑-导回 圆桌: 3-Sheet xlsx 生成 (PR-1)
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.base.module import Module
from app.model.caseHub.plan_module import PlanModule
from file import ExportGuideFile
from utils import log

# 单次导出硬上限. 超过这个量级先走二期异步任务, 别让一个 HTTP 请求挂死 worker.
EXPORT_HARD_LIMIT = 10_000


class ExportCaseService:
    """
    buf = ExportCaseService(...).build_workbook()
    """

    SHEET_DATA = "用例数据"
    SHEET_GUIDE = "编辑指引"
    SHEET_META = "_meta"
    META_VERSION = 1

    # 协议列: 表头中文名 = 解析端识别 key, 改了就破坏 PR-2 解析
    DATA_COLUMNS: List[Tuple[str, str]] = [
        ("排序", "sort"),
        ("用例ID", "case_id"),
        ("UID", "uid"),
        ("用例名称", "case_name"),
        ("用例等级", "case_level"),
        ("用例类型", "case_type"),
        ("用例标签", "case_tag"),
        ("所属分组", "group_path"),
        ("前置条件", "case_setup"),
        ("备注", "case_mark"),
        ("步骤序号", "step_order"),
        ("操作步骤", "action"),
        ("预期结果", "expected_result"),
        ("更新时间", "update_time"),
    ]

    def __init__(
        self,
        scope_type: str,
        scope_id: int,
        case_dicts: List[Dict[str, Any]],
        group_path_map: Dict[int, str],
        include_steps: bool = True,
    ):
        if scope_type not in ("library", "plan"):
            raise ValueError(f"scope_type 必须是 library 或 plan, 收到: {scope_type!r}")
        if len(case_dicts) > EXPORT_HARD_LIMIT:
            raise ValueError(
                f"导出量 {len(case_dicts)} 超过单次上限 {EXPORT_HARD_LIMIT}, "
                f"请先在页面用筛选缩小范围 (TODO: 二期支持异步任务)"
            )
        self.scope_type = scope_type
        self.scope_id = scope_id
        self.case_dicts = case_dicts
        self.group_path_map = group_path_map
        self.include_steps = include_steps

    def build_workbook(self) -> BytesIO:
        wb = openpyxl.Workbook()
        self._write_data_sheet(wb.active)
        self._write_guide_sheet(wb.create_sheet(self.SHEET_GUIDE))
        self._write_meta_sheet(wb.create_sheet(self.SHEET_META))
        wb[self.SHEET_META].sheet_state = "hidden"
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def _write_data_sheet(self, ws) -> None:
        ws.title = self.SHEET_DATA
        for col_idx, (header, _) in enumerate(self.DATA_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"

        row_idx = 2
        for sort_no, case in enumerate(self.case_dicts, start=1):
            steps = case.get("case_sub_steps") or []
            if not self.include_steps or not steps:
                self._write_data_row(ws, row_idx, sort_no, case, step=None)
                row_idx += 1
                continue
            for step in steps:
                self._write_data_row(ws, row_idx, sort_no, case, step=step)
                row_idx += 1

        # 列宽按表头估算, 用户内容长了自己拉宽
        for col_idx, (header, _) in enumerate(self.DATA_COLUMNS, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = max(12, len(header) * 2 + 4)

    def _write_data_row(
        self,
        ws,
        row_idx: int,
        sort_no: int,
        case: Dict[str, Any],
        step: Optional[Dict[str, Any]],
    ) -> None:
        # scope 不同, 取的是不同 id (plan_module_id vs module_id); group_path_map 调用方已按 scope 填好
        group_key = case.get("plan_module_id") if self.scope_type == "plan" else case.get("module_id")
        group_path = self.group_path_map.get(group_key or -1, "")

        update_time = case.get("update_time")
        if isinstance(update_time, datetime):
            update_time = update_time.strftime("%Y-%m-%d %H:%M:%S")

        values = [
            sort_no,
            case.get("id"),
            case.get("uid"),
            case.get("case_name"),
            case.get("case_level"),
            case.get("case_type"),
            case.get("case_tag"),
            group_path,
            case.get("case_setup"),
            case.get("case_mark"),
            step.get("order") if step else None,
            step.get("action") if step else None,
            step.get("expected_result") if step else None,
            update_time,
        ]
        for col_idx, v in enumerate(values, start=1):
            ws.cell(row=row_idx, column=col_idx, value=v)

    def _write_guide_sheet(self, ws) -> None:
        text = _read_guide_text()
        for i, line in enumerate(text.splitlines(), start=1):
            ws.cell(row=i, column=1, value=line)
        ws.column_dimensions["A"].width = 100

    def _write_meta_sheet(self, ws) -> None:
        case_ids_at_export = [c.get("id") for c in self.case_dicts if c.get("id") is not None]
        meta_rows = [
            ("scope_type", self.scope_type),
            ("scope_id", str(self.scope_id)),
            ("case_ids_at_export", ",".join(str(i) for i in case_ids_at_export)),
            ("exported_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("version", str(self.META_VERSION)),
        ]
        ws.cell(row=1, column=1, value="key")
        ws.cell(row=1, column=2, value="value")
        for i, (k, v) in enumerate(meta_rows, start=2):
            ws.cell(row=i, column=1, value=k)
            ws.cell(row=i, column=2, value=v)
        ws.column_dimensions["A"].width = 24
        ws.column_dimensions["B"].width = 60

    # 缓存本次导出的元信息, 供 controller 拼文件名 / 写日志
    @property
    def case_count(self) -> int:
        return len(self.case_dicts)


def _read_guide_text() -> str:
    try:
        with open(ExportGuideFile, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        log.warning(f"编辑指引文件缺失: {ExportGuideFile}, 写出空 sheet")
        return "(编辑指引文件缺失, 请联系管理员)"


async def build_library_group_path_map(
    session: AsyncSession,
    module_ids: List[int],
    project_id: int,
    module_type: int,
) -> Dict[int, str]:
    """
    用例库 scope: 给定 module_id 列表, 构造 'root/.../leaf' 形式的路径字典.
    一次拉整个 project + module_type 下的所有 module, 在内存里回溯, 避免 N+1.
    没找到的 id 不在结果里 (PR-2 那边会按空字符串处理).
    """
    if not module_ids:
        return {}
    rows = (await session.execute(
        select(Module.id, Module.title, Module.parent_id)
        .where(
            Module.project_id == project_id,
            Module.module_type == module_type,
        )
    )).all()
    id_to_node = {r.id: (r.title, r.parent_id) for r in rows}
    return _walk_paths(id_to_node, module_ids)


async def build_plan_group_path_map(
    session: AsyncSession,
    plan_module_ids: List[int],
    plan_id: int,
) -> Dict[int, str]:
    """plan_module_id -> 'root/.../leaf' 路径."""
    if not plan_module_ids:
        return {}
    rows = (await session.execute(
        select(PlanModule.id, PlanModule.title, PlanModule.parent_id)
        .where(PlanModule.plan_id == plan_id)
    )).all()
    id_to_node = {r.id: (r.title, r.parent_id) for r in rows}
    return _walk_paths(id_to_node, plan_module_ids)


def _walk_paths(
    id_to_node: Dict[int, Tuple[str, Optional[int]]],
    targets: List[int],
    max_depth: int = 50,
) -> Dict[int, str]:
    paths: Dict[int, str] = {}
    for nid in targets:
        parts: List[str] = []
        cur_id: Optional[int] = nid
        for _ in range(max_depth):
            node = id_to_node.get(cur_id) if cur_id is not None else None
            if node is None:
                break
            title, parent_id = node
            parts.append(title)
            if parent_id is None or parent_id == 0:
                break
            cur_id = parent_id
        if parts:
            paths[nid] = "/".join(reversed(parts))
    return paths
