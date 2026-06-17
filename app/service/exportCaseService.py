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
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.base.module import Module
from app.model.caseHub.plan_module import PlanModule

# 导出 Excel 下拉框枚举. 业务上**不**写死:
# - 等级/类型/适用端的下拉项均由 controller 从 case_enum_config 加载后传入 ExportCaseService,
#   反映 admin 在配置中心的最新增删.
# - 这里的 EXPORT_LEVEL_OPTIONS / EXPORT_TYPE_OPTIONS / EXPORT_PLATFORM_OPTIONS 仅作
#   controller 拉取失败时的兜底空列表 (Excel 下拉拿空列表就跳过该列 dv, 不报错).
# 历史保留这段注释, 提醒不要在 service 里再写死业务枚举.
# EXPORT_LEVEL_OPTIONS = ["P0-最高", "P1-高", "P2-中", "P3-低"]   # 已废弃
# EXPORT_TYPE_OPTIONS = ["功能测试", "冒烟", "回归", "其他"]      # 已废弃
# EXPORT_PLATFORM_OPTIONS = ["PC", "H5"]                          # 已废弃

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

1. 数据列 (标题 / 前置条件 / 步骤描述 / 预期结果 / 适用端 / 用例等级 / 用例类型 / 备注) 与上传模板一致
2. 多步骤: 在 步骤描述 / 预期结果 单元格里用 换行 分隔, 一行一步, 不加 "【x】" 序号 (与上传解析对称)
3. 用例ID 列 (最后一列):
   - 空 = 新增用例
   - 填值 = 按 ID 更新 (ID 不存在会被拒绝)
4. 不删除任何用例; Excel 中没有的行 (DB 中有) = DB 保留原状
5. 所属分组: 用 | 分隔路径, 例 登录|账号|邮箱登录
6. 不要删除 / 重排 Sheet, 不要改 _meta (隐藏)"""


# 隐藏列: 存放 DataValidation 的 list 源. 用 Z/AA/AB/AC 避开 9/10 个数据列, 不污染用户视图.
# 模块级常量: 既被本类 _add_*_dropdowns 方法用, 也被模块级 add_dropdowns_to_workbook 用
# (后者被 downloadCaseDemo 控制器直接调用).
_DV_LEVEL_COL = 26    # Z   - 用例等级
_DV_TYPE_COL = 27     # AA  - 用例类型
_DV_GROUP_COL = 28    # AB  - 所属分组
_DV_PLATFORM_COL = 29  # AC  - 适用端 (取代已弃用的 case_tag, 与 PLATFORM 枚举对齐)

def add_dropdowns_to_workbook(
    wb: openpyxl.Workbook,
    sheet_name: str,
    all_group_paths: Optional[List[str]] = None,
    level_labels: Optional[List[str]] = None,
    type_labels: Optional[List[str]] = None,
    platform_labels: Optional[List[str]] = None,
    max_row: int = 10000,
) -> None:
    """
    给已存在的 workbook / sheet 加 B/G/H/F 列下拉框 (DataValidation).
    复用逻辑: 导出 (build_workbook) 和 下载模板 (download_case_template) 都调这个.

    参数:
      wb              openpyxl Workbook (已加载, 即将被 .save() / 序列化)
      sheet_name      主表 sheet 名 (导出叫 "用例数据", 模板叫 "template" / 默认)
      all_group_paths B 列下拉源 (全量目录路径, 形如 "根|登录|账号|邮箱登录")
                      None / 空 时跳过 B 列 dv
      level_labels    G 列下拉源 (用例等级 label, 来自 case_enum_config CASE_LEVEL)
      type_labels     H 列下拉源 (用例类型 label, 来自 case_enum_config CASE_TYPE)
      platform_labels F 列下拉源 (适用端 label, 来自 case_enum_config PLATFORM)
                      任一为 None / 空 时, 对应列不挂 dv (等同老 hardcode 缺失行为)
      max_row         dv 作用的最大行 (预留大值让用户继续追加新行也能用下拉)
    """
    if sheet_name not in wb.sheetnames:
        # 兜底: 用第一个 sheet
        sheet_name = wb.sheetnames[0]
    ws = wb[sheet_name]

    level_end = len(level_labels or [])
    type_end = len(type_labels or [])
    platform_end = len(platform_labels or [])

    # 1) G 列: 用例等级
    for i, v in enumerate(level_labels or [], start=1):
        ws.cell(row=i, column=_DV_LEVEL_COL, value=v)
    ws.column_dimensions["Z"].hidden = True
    ws.column_dimensions["Z"].width = 0
    if level_end:
        dv_level = DataValidation(
            type="list",
            formula1=f"=Z$1:Z${level_end}",
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            errorTitle="非法值",
            error="请从下拉框中选择用例等级",
            promptTitle="用例等级",
            prompt=" / ".join(level_labels or []) or "请在配置中心维护用例等级",
        )
        ws.add_data_validation(dv_level)
        dv_level.add("G3:G{max_row}".format(max_row=max_row))

    # 2) H 列: 用例类型
    for i, v in enumerate(type_labels or [], start=1):
        ws.cell(row=i, column=_DV_TYPE_COL, value=v)
    ws.column_dimensions["AA"].hidden = True
    ws.column_dimensions["AA"].width = 0
    if type_end:
        dv_type = DataValidation(
            type="list",
            formula1=f"=AA$1:AA${type_end}",
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            errorTitle="非法值",
            error="请从下拉框中选择用例类型",
            promptTitle="用例类型",
            prompt=" / ".join(type_labels or []) or "请在配置中心维护用例类型",
        )
        ws.add_data_validation(dv_type)
        dv_type.add("H3:H{max_row}".format(max_row=max_row))

    # 3) F 列: 适用端 (适用端在 DATA_COLUMNS 是 index 5, Excel 列号 6 = F)
    for i, v in enumerate(platform_labels or [], start=1):
        ws.cell(row=i, column=_DV_PLATFORM_COL, value=v)
    ws.column_dimensions["AC"].hidden = True
    ws.column_dimensions["AC"].width = 0
    if platform_end:
        dv_platform = DataValidation(
            type="list",
            formula1=f"=AC$1:AC${platform_end}",
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            errorTitle="非法值",
            error="请从下拉框中选择适用端",
            promptTitle="适用端",
            prompt=" / ".join(platform_labels or []) or "请在配置中心维护适用端",
        )
        ws.add_data_validation(dv_platform)
        dv_platform.add("F3:F{max_row}".format(max_row=max_row))

    # 3) B 列: 所属分组 (可选, 依赖调用方传 all_group_paths)
    if all_group_paths:
        all_group_paths = sorted(set(all_group_paths))
        for i, p in enumerate(all_group_paths, start=1):
            ws.cell(row=i, column=_DV_GROUP_COL, value=p)
        ws.column_dimensions["AB"].hidden = True
        ws.column_dimensions["AB"].width = 0
        dv_group = DataValidation(
            type="list",
            formula1=f"=AB$1:AB${len(all_group_paths)}",
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=False,
            promptTitle="所属分组",
            prompt="从下拉选择目录路径 (多级用 | 分隔)",
        )
        ws.add_data_validation(dv_group)
        dv_group.add(f"B3:B{max_row}")


class ExportCaseService:
    """
    buf = ExportCaseService(
        scope_type, scope_id, case_dicts, group_path_map,
        label_map=None, all_group_paths=None,
        level_labels=None, type_labels=None, platform_labels=None,
    ).build_workbook()

    等级/类型/适用端的下拉项均由 controller 从 case_enum_config 加载后传入, 不写死.
    这样 admin 在配置中心增删枚举时, 导出的 Excel 下拉自动同步.
    """

    # 顺序固定, "用例ID" 放最后一列 (导出独有, 下载模板没有).
    DATA_COLUMNS: List[Tuple[str, str]] = [
        ("标题*", "case_name"),
        ("所属分组", "group_path"),
        ("前置条件", "case_setup"),
        ("步骤描述*", "action_cell"),
        ("预期结果*", "expected_result_cell"),
        ("适用端", "case_platform"),
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
        all_group_paths: Optional[List[str]] = None,
        # 下拉项数据源: 业务枚举**不**写死, 由 controller 从 case_enum_config 加载后传入.
        # 顺序: case_config.sort asc. None / 空 时该列不挂 dv (等同老 hardcode 缺失行为).
        level_labels: Optional[List[str]] = None,
        type_labels: Optional[List[str]] = None,
        platform_labels: Optional[List[str]] = None,
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
        # 全量目录路径列表 (平铺, 含根), 给 B 列 "所属分组" 做下拉选项.
        # None / 空 时不挂 B 列 dv, 用户继续手填.
        self.all_group_paths = sorted(set(all_group_paths or []))
        self.level_labels = list(level_labels or [])
        self.type_labels = list(type_labels or [])
        self.platform_labels = list(platform_labels or [])

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

        # 给 "所属分组" (B 列, 2) 加目录路径下拉 (全量平铺)
        # 给 "适用端" (F 列, 6) / "用例等级" (G 列, 7) / "用例类型" (H 列, 8) 加下拉框.
        # 范围预留到 row 10000, 让用户在导出文件里继续追加新用例时也能用下拉选枚举.
        self._add_group_dropdowns(ws, max_row=10000)
        self._add_enum_dropdowns(ws, max_row=10000)

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
        group_path = self.group_path_map.get(group_key, "") if group_key is not None else ""

        steps = case.get("case_sub_steps") or []
        action_cell = format_steps_cell(steps, "action")
        expected_result_cell = format_steps_cell(steps, "expected_result")

        case_level = case.get("case_level")
        case_type = case.get("case_type")
        case_platform = case.get("case_platform")

        values = [
            case.get("case_name"),
            group_path,
            case.get("case_setup"),
            action_cell,
            expected_result_cell,
            self.label_map.get(case_platform, case_platform),
            self.label_map.get(case_level, case_level),
            self.label_map.get(case_type, case_type),
            case.get("case_mark"),
            case.get("id"),
        ]
        for col_idx, v in enumerate(values, start=1):
            ws.cell(row=row_idx, column=col_idx, value=v)

    def _add_group_dropdowns(self, ws, max_row: int = 10000) -> None:
        """
        给 B 列 (所属分组) 加目录路径下拉框.
        数据源: self.all_group_paths (平铺的全量目录路径, 形如 "根|登录|账号|邮箱登录").
        Excel/WPS 不支持真正的多级树形下拉, 改用平铺完整路径方案: 用户从下拉里选
        完整路径, 不需要手敲 | 分隔符.
        """
        if not self.all_group_paths:
            return
        for i, p in enumerate(self.all_group_paths, start=1):
            ws.cell(row=i, column=_DV_GROUP_COL, value=p)
        # 隐藏 AB 列
        ws.column_dimensions["AB"].hidden = True
        ws.column_dimensions["AB"].width = 0
        end = len(self.all_group_paths)
        dv = DataValidation(
            type="list",
            formula1=f"=AB$1:AB${end}",
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=False,
            promptTitle="所属分组",
            prompt="从下拉选择目录路径 (多级用 | 分隔)",
        )
        ws.add_data_validation(dv)
        dv.add(f"B3:B{max_row}")

    def _add_enum_dropdowns(self, ws, max_row: int = 10000) -> None:
        """
        给 G 列 (用例等级) / H 列 (用例类型) / 适用端所在列 (按 DATA_COLUMNS 顺序动态)
        加 Excel 下拉框 DataValidation.
        范围从 row 3 (数据起点) 到 max_row, 既覆盖已写入数据, 也允许用户在导出文件里
        继续追加新用例时直接用下拉选枚举, 不需要复制粘贴.

        实现细节: WPS / Kingsoft 对 inline list 公式 (formula1='"a,b,c"') 兼容性差,
        实际打开不显示下拉. 改用 "list 引用 sheet range" 模式:
          1. 在 Z/AA/AC 列 (隐藏) 写枚举值
          2. dv.formula1 指向 Z$1:Z$N / AA$1:AA$N / AC$1:AC$N
          3. 列宽设为 0 隐藏
        这样 WPS / Excel / LibreOffice 都能正常显示下拉箭头.

        下拉项数据源: 实例字段 self.level_labels / self.type_labels / self.platform_labels,
        由 controller 从 case_enum_config 加载后传入; 业务枚举不在 service 里写死.
        """
        level_end = len(self.level_labels)
        type_end = len(self.type_labels)
        platform_end = len(self.platform_labels)

        # 1) 写枚举值到隐藏列 (空列表也写, 留 dv.formula1 引用, 让 WPS 兼容)
        for i, v in enumerate(self.level_labels, start=1):
            ws.cell(row=i, column=_DV_LEVEL_COL, value=v)
        for i, v in enumerate(self.type_labels, start=1):
            ws.cell(row=i, column=_DV_TYPE_COL, value=v)
        for i, v in enumerate(self.platform_labels, start=1):
            ws.cell(row=i, column=_DV_PLATFORM_COL, value=v)
        # 隐藏 Z / AA / AC 列
        for col_letter, hidden_col in (("Z", _DV_LEVEL_COL), ("AA", _DV_TYPE_COL), ("AC", _DV_PLATFORM_COL)):
            ws.column_dimensions[col_letter].hidden = True
            ws.column_dimensions[col_letter].width = 0

        # 2) DataValidation 引用 sheet range (WPS 兼容写法)
        # showDropDown=False 才是显示下拉箭头 (openpyxl 字段语义反直觉)
        #
        # level_end=0 / type_end=0 / platform_end=0 时, 仍创建 dv 但 formula1 指向 0 行,
        # WPS / Excel 此时直接视为 "无限制", 不会挂. 等价于 "该列不挂下拉" 的旧行为.
        if level_end:
            dv_level = DataValidation(
                type="list",
                formula1=f"=Z$1:Z${level_end}",
                allow_blank=True,
                showDropDown=False,
                showErrorMessage=True,
                errorTitle="非法值",
                error="请从下拉框中选择用例等级",
                promptTitle="用例等级",
                prompt=" / ".join(self.level_labels) or "请在配置中心维护用例等级",
            )
            ws.add_data_validation(dv_level)
            dv_level.add("G3:G{max_row}".format(max_row=max_row))
        if type_end:
            dv_type = DataValidation(
                type="list",
                formula1=f"=AA$1:AA${type_end}",
                allow_blank=True,
                showDropDown=False,
                showErrorMessage=True,
                errorTitle="非法值",
                error="请从下拉框中选择用例类型",
                promptTitle="用例类型",
                prompt=" / ".join(self.type_labels) or "请在配置中心维护用例类型",
            )
            ws.add_data_validation(dv_type)
            dv_type.add("H3:H{max_row}".format(max_row=max_row))
        if platform_end:
            # 适用端列: 在 DATA_COLUMNS 里是 index 5, Excel 列号 6 = F 列
            dv_platform = DataValidation(
                type="list",
                formula1=f"=AC$1:AC${platform_end}",
                allow_blank=True,
                showDropDown=False,
                showErrorMessage=True,
                errorTitle="非法值",
                error="请从下拉框中选择适用端",
                promptTitle="适用端",
                prompt=" / ".join(self.platform_labels) or "请在配置中心维护适用端",
            )
            ws.add_data_validation(dv_platform)
            dv_platform.add("F3:F{max_row}".format(max_row=max_row))

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
