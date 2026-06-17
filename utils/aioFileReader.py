#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/9/9
# @Author : cyq
# @File : aioFileReader
# @Software: PyCharm
# @Desc: Excel 文件读取工具类

import asyncio
import hashlib
from typing import List, Dict, Any, Optional, Mapping
from dataclasses import dataclass, field

import pandas as pd
from fastapi import UploadFile
from io import BytesIO
from utils import log

from utils.threadPool import ThreadPoolHelper

# openpyxl 5.x 兼容性补丁
# 现象: 部分 Excel 文件 (例如旧版 WPS 导出 / 业务侧手工改过样式) 反序列化到样式
#       阶段时, 会用位置参数调用基类 openpyxl.styles.fills.Fill.__init__,
#       但 Fill 是 Serialisable 子类, 没有自定义 __init__, type 默认 __init__
#       不接受位置参数, 抛 `TypeError: Fill() takes no arguments`.
# 影响: aioFileReader 整条 pd.read_excel 链路直接挂掉, 用户无法导入.
# 修复: 给 Fill.__init__ 包一层, 吃掉位置参数, 走默认 Serialisable __init__.
#       业务侧只关心数据, 不读 fill 字段, 这个 fallback 不影响功能.
import openpyxl.styles.fills as _openpyxl_fills
if not getattr(_openpyxl_fills.Fill, "_ch_safe_init_patched", False):
    _orig_fill_init = _openpyxl_fills.Fill.__init__

    def _safe_fill_init(self, *args, **kwargs):
        if args and not kwargs:
            # 仅忽略纯位置参数, 保留关键字参数 (例如 PatternFill 派生的 from_tree 路径)
            args = ()
        return _orig_fill_init(self, *args, **kwargs)

    _openpyxl_fills.Fill.__init__ = _safe_fill_init
    _openpyxl_fills.Fill._ch_safe_init_patched = True

FIELD_MAPPING = {
    "标题*": "case_name",
    "前置条件": "case_setup",
    "步骤描述": "action",
    "预期结果": "expected_result",
    "用例等级*": "case_level",
    "用例类型": "case_type",
    "适用端": "case_platform",
    "备注": "case_mark",
    "所属分组": "group_path",
    "用例ID": "case_id",
}

# 必填字段 (对应 FIELD_MAPPING 的 value)
REQUIRED_FIELDS = {"case_name"}

# 用例等级空值时的默认 value. 调用方可在 CaseEnumConfig 中覆盖.
DEFAULT_LEVEL_VALUE = "P2"

# 表头搜索范围 (行数) 与示例行判定关键字
HEADER_SCAN_ROWS = 5
EXAMPLE_KEYWORD = "示例"

UPLOAD_CACHE_EXPIRES = 1800
MAX_FILE_SIZE = 10 * 1024 * 1024


@dataclass
class CaseEnumConfig:
    """
    用例枚举配置 (由调用方从 case_config 表加载后注入)

    :param level_map:    用例等级 label -> value, 例如 {"P1":"P1", "P2":"P2", ...}
    :param type_map:     用例类型 label -> value, 例如 {"功能":"GN", "冒烟":"MY", ...}
    :param platform_map: 适用端 label -> value, 例如 {"PC":"PC", "H5":"H5", ...}
    :param default_level:    用例等级空值时的默认 value
    :param default_type:     用例类型空值时的默认 value (None=不填, 留空入库)
    :param default_platform: 适用端空值时的默认 value (None=不填, 留空入库)
    """
    level_map: Dict[str, str] = field(default_factory=dict)
    type_map: Dict[str, str] = field(default_factory=dict)
    platform_map: Dict[str, str] = field(default_factory=dict)
    default_level: str = DEFAULT_LEVEL_VALUE
    default_type: Optional[str] = None
    default_platform: Optional[str] = None


@dataclass
class ParseResult:
    """解析结果"""

    valid_cases: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    file_md5: str = ""

    @property
    def valid_count(self) -> int:
        return len(self.valid_cases)

    @property
    def invalid_count(self) -> int:
        return len(self.errors)


def _normalize_col_name(name: Any) -> str:
    """归一化列名: 去除 BOM、首尾空白"""
    if name is None:
        return ""
    s = str(name)
    s = s.replace("\ufeff", "")
    return s.strip()


def _strip_asterisk(name: str) -> str:
    """去除列名末尾的 '*' (必填标识) 与空白, 用于宽松匹配"""
    return name.rstrip("*").strip()


def _display_field_name(excel_col: str) -> str:
    """用于错误信息展示: 去除末尾 '*'"""
    return excel_col.rstrip("*").strip()


def _match_column(actual_columns, target_key: str) -> Optional[str]:
    """
    在 actual_columns 中查找 target_key 对应的列.
    匹配策略 (按优先级):
      1) 完全相等
      2) 归一化后相等 (去 BOM / 空白)
      3) 双方都去掉末尾 '*' 后相等 (兼容 '用例等级' vs '用例等级*')
    返回实际列名, 未命中返回 None.
    """
    if target_key in actual_columns:
        return target_key

    target_norm = _normalize_col_name(target_key)
    target_no_star = _strip_asterisk(target_norm)

    for col in actual_columns:
        col_norm = _normalize_col_name(col)
        if col_norm == target_norm:
            return col
        if _strip_asterisk(col_norm) == target_no_star:
            return col
    return None


class AsyncFilesReader:
    def __init__(
        self,
        workers: int = 4,
        enum_config: Optional[CaseEnumConfig] = None,
    ):
        """
        :param workers: 线程池大小
        :param enum_config: 用例等级 / 类型 配置. None 时不做 label→value 转换,
                            仅做"非空"校验, 落原始字符串 (兼容老调用方).
        """
        self.tph = ThreadPoolHelper(workers=workers)
        self.enum_config = enum_config or CaseEnumConfig()

    async def async_read_excel_for_case(self, file: UploadFile) -> ParseResult:
        file_content = await file.read()
        return await self.async_read_from_bytes(file_content)

    async def async_read_from_bytes(self, content: bytes) -> ParseResult:
        """
        从原始 bytes 读 M1 老格式. 给 /upload 入口做模板探测后直接传 bytes,
        避免 controller 读一次 stream 再让本类读第二次时空读.

        跟 async_read_excel_for_case 的差别: 不接 UploadFile, 不用 seek(0).
        """
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"文件大小超过限制，最大支持 {MAX_FILE_SIZE // 1024 // 1024}MB")
        file_bytes = BytesIO(content)
        file_md5 = self._calculate_md5(content)
        loop = asyncio.get_event_loop()
        return await self.tph.run_in_exe(
            loop,
            self._read,
            file_bytes,
            file_md5,
            self.enum_config,
        )

    @staticmethod
    def _calculate_md5(content: bytes) -> str:
        return hashlib.md5(content).hexdigest()

    @staticmethod
    def _is_empty_row(row_dict: Dict[str, Any]) -> bool:
        for value in row_dict.values():
            if value is not None and not pd.isna(value) and str(value).strip():
                return False
        return True

    @staticmethod
    def _read(
        file: BytesIO,
        file_md5: str,
        enum_config: CaseEnumConfig,
    ) -> ParseResult:
        result = ParseResult(file_md5=file_md5)

        try:
            # 1) 默认读取第一个 sheet, 不论其名称
            excel_file = pd.ExcelFile(file, engine="openpyxl")
            if not excel_file.sheet_names:
                raise ValueError("Excel文件不包含任何工作表")
            sheet_name = excel_file.sheet_names[0]

            # 2) 探测表头所在行: 在前 HEADER_SCAN_ROWS 行中找包含 '标题*' 的行
            file.seek(0)
            df_peek = pd.read_excel(
                file,
                sheet_name=sheet_name,
                header=None,
                nrows=HEADER_SCAN_ROWS,
                engine="openpyxl",
            )
            header_row: Optional[int] = None
            for i, row in df_peek.iterrows():
                normalized = [_normalize_col_name(v) for v in row.values]
                if "标题*" in normalized:
                    header_row = int(i)
                    break

            if header_row is None:
                result.errors.append({
                    "row": 0,
                    "errors": [{
                        "field": "file",
                        "message": "未在表头中找到必填列 '标题*'，请检查模板格式",
                    }],
                })
                return result

            # 3) 探测示例行
            skip_rows: List[int] = []
            if header_row + 1 < len(df_peek):
                first_cell = df_peek.iloc[header_row + 1, 0]
                if first_cell is not None and not pd.isna(first_cell) and EXAMPLE_KEYWORD in str(first_cell):
                    skip_rows = [header_row + 1]

            # 4) 读取数据
            file.seek(0)
            df = pd.read_excel(
                file,
                header=header_row,
                keep_default_na=False,
                na_values=["", "nan"],
                sheet_name=sheet_name,
                skiprows=skip_rows,
                engine="openpyxl",
            )

            log.info(
                f"[Excel解析] sheet={sheet_name}, header_row={header_row + 1}, "
                f"skip={skip_rows}, 数据行数={len(df)}, 列={list(df.columns)}"
            )

            if len(df) == 0:
                result.errors.append({
                    "row": 0,
                    "errors": [{"field": "file", "message": "模板无有效数据"}],
                })
                return result

            # 5) 构建 field_name -> 实际列名 映射, 让 FIELD_MAPPING 顺序无关
            actual_columns = list(df.columns)
            field_to_actual: Dict[str, Optional[str]] = {}
            missing_required: List[str] = []
            for excel_col, field_name in FIELD_MAPPING.items():
                matched = _match_column(actual_columns, excel_col)
                field_to_actual[field_name] = matched
                if field_name in REQUIRED_FIELDS and matched is None:
                    missing_required.append(excel_col)

            if missing_required:
                result.errors.append({
                    "row": 0,
                    "errors": [{
                        "field": ",".join(missing_required),
                        "message": f"模板缺少必填列: {','.join(missing_required)}",
                    }],
                })
                return result

            result.total_count = len(df)

            # 6) 计算原始 Excel 行号: header_row(0-idx) + 1 行表头 + 跳过的示例行
            base_excel_row = header_row + 2 + len(skip_rows)

            level_map = enum_config.level_map
            type_map = enum_config.type_map

            for df_idx, row in df.iterrows():
                row_dict = {
                    col: (None if pd.isna(val) or val == "" else val)
                    for col, val in row.items()
                }

                if AsyncFilesReader._is_empty_row(row_dict):
                    continue

                current_row = base_excel_row + int(df_idx)
                is_valid = True
                errors: List[Dict[str, Any]] = []

                # 按 FIELD_MAPPING 提取 (顺序无关)
                mapped_case: Dict[str, Any] = {}
                for excel_col, field_name in FIELD_MAPPING.items():
                    actual_col = field_to_actual.get(field_name)
                    mapped_case[field_name] = row_dict.get(actual_col) if actual_col else None

                # 标题
                case_name = mapped_case.get("case_name")
                if not case_name or (isinstance(case_name, str) and not case_name.strip()):
                    is_valid = False
                    errors.append({"field": _display_field_name("标题*"), "message": "用例名称不能为空"})

                # 用例等级: label → value; 空值用 default; 非法值打回.
                # enum_map 空时 (preview-only 场景) 跳过校验, 原样保留 label, commit 阶段再校.
                if level_map:
                    mapped_case["case_level"], level_err = _resolve_enum(
                        raw=mapped_case.get("case_level"),
                        enum_map=level_map,
                        default=enum_config.default_level,
                        display_name=_display_field_name("用例等级*"),
                    )
                    if level_err:
                        is_valid = False
                        errors.append(level_err)
                else:
                    v = mapped_case.get("case_level")
                    mapped_case["case_level"] = (str(v).strip() if v is not None and not pd.isna(v) else None) or enum_config.default_level

                # 用例类型: 同上
                if type_map:
                    mapped_case["case_type"], type_err = _resolve_enum(
                        raw=mapped_case.get("case_type"),
                        enum_map=type_map,
                        default=enum_config.default_type,
                        display_name=_display_field_name("用例类型"),
                    )
                    if type_err:
                        is_valid = False
                        errors.append(type_err)
                else:
                    v = mapped_case.get("case_type")
                    mapped_case["case_type"] = (str(v).strip() if v is not None and not pd.isna(v) else None) or enum_config.default_type

                # 适用端 (PLATFORM 枚举): 旧模板无此列, mapped_case["case_platform"] 默认 None,
                # 走不到 _resolve_enum, 留空入库 (DB case_platform 允许 NULL).
                platform_map = enum_config.platform_map
                if platform_map and mapped_case.get("case_platform") is not None:
                    mapped_case["case_platform"], platform_err = _resolve_enum(
                        raw=mapped_case.get("case_platform"),
                        enum_map=platform_map,
                        default=enum_config.default_platform,
                        display_name=_display_field_name("适用端"),
                    )
                    if platform_err:
                        is_valid = False
                        errors.append(platform_err)
                else:
                    v = mapped_case.get("case_platform")
                    if v is not None and not pd.isna(v):
                        mapped_case["case_platform"] = str(v).strip() or None
                    else:
                        mapped_case["case_platform"] = None

                if is_valid:
                    # _row: 仅做预览阶段"行号级"错误提示用, 提交入库前由 controller 剥掉,
                    # 避免作为字段传到 TestCase 模型. 前端不需要这个字段.
                    mapped_case["_row"] = current_row
                    result.valid_cases.append(mapped_case)
                else:
                    result.errors.append({
                        "row": current_row,
                        "errors": errors,
                    })

        except Exception as e:
            log.exception(f"读取Excel时发生错误: {e}")
            raise ValueError(f"读取Excel时发生错误")

        return result


def _resolve_enum(
    raw: Any,
    enum_map: Mapping[str, str],
    default: Optional[str],
    display_name: str,
) -> tuple:
    """
    把 Excel 单元格中的枚举 label 解析为配置的 value.

    返回 (resolved, error_dict_or_None):
      - 空值:  返回 (default, None)  — 默认值可以为 None (即留空入库)
      - 命中:  返回 (enum_map[label], None)
      - 未命中: 返回 (raw 或 None, error_dict) — 报告具体非法值
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return default, None

    s = str(raw).strip()
    if s in enum_map:
        return enum_map[s], None

    valid = ", ".join(sorted(enum_map.keys())) if enum_map else "(未配置)"
    return None, {
        "field": display_name,
        "message": f"{display_name} '{s}' 不在可选范围内: {valid}",
    }


async def read_excel_async(file: UploadFile) -> ParseResult:
    reader = AsyncFilesReader()
    return await reader.async_read_excel_for_case(file)
