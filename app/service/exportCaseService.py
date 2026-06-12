"""
用例导出服务: 基于 file/用例模版.xlsx 模板生成导出文件.

复用上传模板的 3 行结构 (标题引导 + 标头 + demo) 保证视觉一致, 增量写入:
  - 第 10 列 "用例ID" (下载模板没有, 导出才有)
  - 第 4 行起的真实数据 (下载模板无数据)
  - 隐藏的 _meta Sheet (跨 scope 防御 / 变更检测 / 版本号)

行布局 (基于 file/用例模版.xlsx 复用样式, 不是逐行复制):
  Row 1   - A1 单元格里嵌标题 + 编辑引导 (覆盖原 "导入模板" 标题)
  Row 2   - 10 列表头 (前 9 列沿用模板, 第 10 列 "用例ID" 新增)
  Row 3+  - 真实数据 (10 列, 1 用例 1 行, 多步拼到同一 cell).
             原模板 row 3 的 demo 行被删除, 避免再导入时被当成 INSERT 假数据.
"""

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.base.module import Module
from app.model.caseHub.plan_module import PlanModule

# 单次导出硬上限. 超量走二期异步任务.
EXPORT_HARD_LIMIT = 10_000

# 导出文件协议版本. 与下载模板 (version=N/A) 区分, 解析端可据此拒绝老格式.
META_VERSION = 2

# 导出 Sheet 名. 模板里原叫 "template", 导出改名让用户更直观.
SHEET_DATA = "用例数据"
SHEET_META = "_meta"

# 编辑引导. 行 1 的 A1 cell 全文, 包含标题 + 5 条规则. 规则从用户立场写, 不说后端实现.
_EXPORT_GUIDE = """\
CASE  HUB 用例导出

1. 数据列 (标题 / 前置条件 / 步骤描述 / 预期结果 / 标签 / 用例等级 / 用例类型 / 备注) 与上传模板一致
2. 多步骤: 在 步骤描述 / 预期结果 单元格里用 【1】xxx\\n【2】xxx 换行 (与上传一致)
3. 用例ID 列 (最后一列):
   - 空 = 新增用例
   - 填值 = 按 ID 更新 (ID 不存在会被拒绝)
4. 不删除任何用例; Excel 中没有的行 (DB 中有) = DB 保留原状
5. 所属分组: 用 | 分隔路径, 例 登录|账号|邮箱登录
6. 不要删除 / 重排 Sheet, 不要改 _meta (隐藏)"""


class ExportCaseService:
    """
    buf = ExportCaseService(...).build_workbook()
    """

    # 协议列: 表头中文名 = 解析端识别 key. 改了就破坏 PR-2 解析.
    # 顺序固定, "用例ID" 放最后一列 (导出独有, 下载模板没有).
    DATA_COLUMNS: List[Tuple[str, str]] = [
        ("标题*", "case_name"),
        ("所属分组", "group_path"),
        ("前置条件", "case_setup"),
        ("步骤描述*", "action_cell"),
        ("预期结果*", "expected_result_cell"),
        ("标签", "case_tag"),
        ("用例等级*", "case_level"),
        ("用例类型", "case_type"),
        ("备注", "case_mark"),
        ("用例ID", "case_id"),
    ]

    def __init__(
        self,
        scope_type: str,
        scope_id: int,
        case_dicts: List[Dict[str, Any]],
        group_path_map: Dict[int, str],
        label_map: Optional[Dict[str, str]] = None,
    ):
        if scope_type not in ("library", "plan"):
            raise ValueError(f"scope_type 必须是 library 或 plan, 收到: {scope_type!r}")
        if len(case_dicts) > EXPORT_HARD_LIMIT:
            raise ValueError(
                f"导出量 {len(case_dicts)} 超过单次上限 {EXPORT_HARD_LIMIT}, "
                f"请先在页面用筛选缩小范围"
            )
        self.scope_type = scope_type
        self.scope_id = scope_id
        self.case_dicts = case_dicts
        self.group_path_map = group_path_map
        # case_config.value -> label. 缺 key 时回退到原 value (label_map.get(v, v)).
        self.label_map = label_map or {}

    def build_workbook(self) -> BytesIO:
        # 以 file/用例模版.xlsx 为基底, 复用其样式/字体/排版, 改动量最小
        from file import TestCaseDemoFile
        wb = openpyxl.load_workbook(TestCaseDemoFile)
        ws = wb["template"]
        ws.title = SHEET_DATA

        # 替换 row 1: 标题 + 编辑引导 (覆盖原模板 A1 的 "导入模板" 标题)
        ws.cell(1, 1, _EXPORT_GUIDE)

        # 把模板 J2 原占位 "备注" 覆盖为 "用例ID". 导出独有的协议列, 解析端按此识别.
        ws.cell(2, len(self.DATA_COLUMNS), self.DATA_COLUMNS[-1][0])

        # 删 row 3 demo 行: 导出是真实数据, 留 demo 会被 PR-2 当成 INSERT 假数据.
        # 删完后真实数据从 row 3 开始写, 与 aioFileReader 默认 header_row+1 数据起点对齐.
        ws.delete_rows(3, 1)

        for row_idx, case in enumerate(self.case_dicts, start=3):
            self._write_data_row(ws, row_idx, case)

        # 隐藏的 _meta Sheet: 跨 scope 防御 / 变更检测 / 版本号
        self._write_meta_sheet(wb)

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def _write_data_row(self, ws, row_idx: int, case: Dict[str, Any]) -> None:
        from utils.stepCellFormatter import format_steps_cell

        # scope 不同, 取的 id 字段不同; group_path_map 由 controller 按 scope 填好
        group_key = (
            case.get("plan_module_id") if self.scope_type == "plan" else case.get("module_id")
        )
        group_path = self.group_path_map.get(group_key or -1, "")

        steps = case.get("case_sub_steps") or []
        action_cell = format_steps_cell(steps, "action")
        expected_result_cell = format_steps_cell(steps, "expected_result")

        case_level = case.get("case_level")
        case_type = case.get("case_type")

        values = [
            case.get("case_name"),
            group_path,
            case.get("case_setup"),
            action_cell,
            expected_result_cell,
            case.get("case_tag"),
            self.label_map.get(case_level, case_level),
            self.label_map.get(case_type, case_type),
            case.get("case_mark"),
            case.get("id"),
        ]
        for col_idx, v in enumerate(values, start=1):
            ws.cell(row=row_idx, column=col_idx, value=v)

    def _write_meta_sheet(self, wb) -> None:
        """
        隐藏的 _meta Sheet: scope / 导出快照 / 时间 / 版本号.

        - scope_type / scope_id: PR-3 commit 阶段做跨 scope 防御 (导出 plan:123, 不能上传到 plan:456)
        - case_ids_at_export: 解析端比对, 检测"导出后增删" 给前端做 warning
        - version: 协议版本号, 未来改格式时升级并 reject 老文件
        """
        case_ids = [c.get("id") for c in self.case_dicts if c.get("id") is not None]
        meta_ws = wb.create_sheet(SHEET_META)
        meta_ws["A1"], meta_ws["B1"] = "key", "value"
        rows = [
            ("scope_type", self.scope_type),
            ("scope_id", str(self.scope_id)),
            ("case_ids_at_export", ",".join(str(i) for i in case_ids)),
            ("exported_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("version", str(META_VERSION)),
        ]
        for i, (k, v) in enumerate(rows, start=2):
            meta_ws.cell(i, 1, k)
            meta_ws.cell(i, 2, v)
        meta_ws.column_dimensions["A"].width = 24
        meta_ws.column_dimensions["B"].width = 60
        meta_ws.sheet_state = "hidden"

    @property
    def case_count(self) -> int:
        return len(self.case_dicts)


def _walk_paths(
    id_to_node: Dict[int, Tuple[str, Optional[int]]],
    targets: List[int],
    max_depth: int = 50,
) -> Dict[int, str]:
    """
    通过 parent_id 链回溯构造 "A|B|C" 形式路径.

    用 "|" 而非 "/" 分隔, 跟 file/用例模版.xlsx 上传模板一致.
    mapper 层 (TestCaseMapper.build_module_path_map / PlanCaseMapper.build_plan_module_path_map)
    通过 from-import 复用本函数, 不在本服务内二次包装.
    """
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
            paths[nid] = "|".join(reversed(parts))
    return paths
