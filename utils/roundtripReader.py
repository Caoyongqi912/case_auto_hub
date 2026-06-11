#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/11
# @Author : cyq
# @File : roundtripReader
# @Software: PyCharm
# @Desc: 导出-编辑-导回 圆桌专用的 Excel 解析 (PR-2)
#
# 跟 utils/aioFileReader.py 的关系:
#   - 老 aioFileReader 解析老模板 (标题*/用例等级*/步骤描述) 走 /upload 增量导入
#   - 本解析器解析 3-Sheet 新模板 (用例数据/编辑指引/_meta) 走 /import/preview
#   - 共用 openpyxl + pandas 读盘, 业务字段定义各自独立
#
# 输入文件结构 (PR-1 export 出的):
#   Sheet 1  "用例数据"  — 14 列主表, 一个用例多步 = 多行
#   Sheet 2  "编辑指引"  — 可见, 解析器跳过
#   Sheet 3  "_meta"     — 隐藏, scope_type / scope_id / case_ids_at_export / version
import asyncio
import hashlib
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import UploadFile
from utils import log
from utils.threadPool import ThreadPoolHelper

# 14 列协议 (与 exportCaseService.DATA_COLUMNS 对齐). 顺序即列顺序, 改了就破坏两端
EXPECTED_DATA_COLUMNS: List[str] = [
    "排序", "用例ID", "UID", "用例名称", "用例等级", "用例类型", "用例标签",
    "所属分组", "前置条件", "备注", "步骤序号", "操作步骤", "预期结果", "更新时间",
]
# 必填列 (其余列可空)
REQUIRED_DATA_COLUMNS = {"用例名称"}

META_SHEET_NAME = "_meta"
DATA_SHEET_NAME = "用例数据"

# 协议版本. _meta.version 不一致视为不兼容.
SUPPORTED_META_VERSION = 1
MAX_FILE_SIZE = 10 * 1024 * 1024


@dataclass
class RoundtripParseResult:
    file_md5: str = ""
    total_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    # 每行解析后的 dict, key 是 EXPECTED_DATA_COLUMNS. _row 是 Excel 物理行号.
    valid_rows: List[Dict[str, Any]] = field(default_factory=list)
    # _meta Sheet 解析结果. 缺失或字段缺失时为 None
    meta: Optional[Dict[str, str]] = None
    # scope 校验结果. 失败时 errors 也会带一项.
    scope_check: Dict[str, Any] = field(default_factory=dict)


class RoundtripReader:
    """
    解析 3-Sheet xlsx (PR-1 导出格式) -> RoundtripParseResult.

    不做 DB 校验, 不写 Redis. scope 校验只比 _meta 与 form 参数的一致性,
    真实"case_id 是否在范围内 / 乐观锁" 留给 PR-3 commit 阶段.
    """

    def __init__(self, scope_type: str, scope_id: int, workers: int = 4):
        if scope_type not in ("library", "plan"):
            raise ValueError(f"scope_type 必须是 library 或 plan, 收到: {scope_type!r}")
        self.scope_type = scope_type
        self.scope_id = scope_id
        self.tph = ThreadPoolHelper(workers=workers)

    async def async_read(self, file: UploadFile) -> RoundtripParseResult:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"文件大小超过限制, 最大支持 {MAX_FILE_SIZE // 1024 // 1024}MB")
        file_bytes = BytesIO(content)
        file_md5 = hashlib.md5(content).hexdigest()
        await file.seek(0)
        loop = asyncio.get_event_loop()
        return await self.tph.run_in_exe(loop, self._read, file_bytes, file_md5)

    def _read(self, file: BytesIO, file_md5: str) -> RoundtripParseResult:
        result = RoundtripParseResult(file_md5=file_md5)
        try:
            excel = pd.ExcelFile(file, engine="openpyxl")
            sheet_names = excel.sheet_names
            if DATA_SHEET_NAME not in sheet_names:
                result.errors.append({
                    "row": 0,
                    "errors": [{
                        "field": "file",
                        "message": f"找不到主表 Sheet '{DATA_SHEET_NAME}', 该文件不是导出-编辑-导回 圆桌格式",
                    }],
                })
                return result

            # 1) 解析 _meta (隐藏 sheet, 某些 lib 不列出 hidden 的)
            result.meta = self._read_meta(excel)
            if result.meta is not None:
                self._validate_meta(result)
            else:
                result.errors.append({
                    "row": 0,
                    "errors": [{
                        "field": "_meta",
                        "message": "找不到 _meta Sheet, 该文件可能不是圆桌导出的格式",
                    }],
                })
                return result

            # scope 校验: 提前失败, 不浪费后续解析
            if result.scope_check.get("scope_type_matches") is False:
                result.errors.append({
                    "row": 0,
                    "errors": [{
                        "field": "scope_type",
                        "message": (
                            f"文件导出于 {result.meta.get('scope_type')}:{result.meta.get('scope_id')}, "
                            f"与当前选择的 {self.scope_type}:{self.scope_id} 不一致, 请使用正确的导出文件"
                        ),
                    }],
                })
                return result
            if result.scope_check.get("scope_id_matches") is False:
                result.errors.append({
                    "row": 0,
                    "errors": [{
                        "field": "scope_id",
                        "message": (
                            f"文件导出于 {result.meta.get('scope_type')}:{result.meta.get('scope_id')}, "
                            f"与当前选择的 {self.scope_type}:{self.scope_id} 不一致, 请使用正确的导出文件"
                        ),
                    }],
                })
                return result
            if result.scope_check.get("version_supported") is False:
                result.errors.append({
                    "row": 0,
                    "errors": [{
                        "field": "version",
                        "message": f"文件版本 {result.meta.get('version')} 不受支持, 期望 {SUPPORTED_META_VERSION}",
                    }],
                })
                return result

            # 2) 解析主表
            df = pd.read_excel(
                excel,
                sheet_name=DATA_SHEET_NAME,
                keep_default_na=False,
                na_values=["", "nan"],
                engine="openpyxl",
            )
            actual_cols = list(df.columns)
            missing = [c for c in EXPECTED_DATA_COLUMNS if c not in actual_cols]
            if missing:
                result.errors.append({
                    "row": 0,
                    "errors": [{
                        "field": ",".join(missing),
                        "message": f"主表缺少列: {','.join(missing)}",
                    }],
                })
                return result

            # 兼容: 老导出如果列顺序不同也接受, 后面按列名取就行
            result.total_count = len(df)
            excel_row_base = 2  # 1 是表头

            sort_values: List[Tuple[int, int]] = []  # (sort, excel_row)

            for df_idx, row in df.iterrows():
                excel_row = excel_row_base + int(df_idx)
                row_dict = self._row_to_dict(row, actual_cols)
                if self._is_empty_row(row_dict):
                    continue

                is_valid, errors, parsed = self._validate_row(row_dict, excel_row)
                if is_valid:
                    parsed["_row"] = excel_row
                    result.valid_rows.append(parsed)
                    if parsed.get("排序") is not None:
                        sort_values.append((int(parsed["排序"]), excel_row))
                else:
                    result.errors.append({"row": excel_row, "errors": errors})

            # 3) 排序 warning (不阻断)
            self._check_sort_warnings(sort_values, result)

            # 4) 补 scope_check 里的数量统计
            result.scope_check.update(self._compute_scope_check(result))
            result.valid_count = len(result.valid_rows)
            result.invalid_count = len(result.errors)
        except ValueError:
            raise
        except Exception as e:
            log.error(f"roundtrip 解析失败: {e}")
            raise ValueError(f"读取 Excel 时发生错误: {e}")
        return result

    def _read_meta(self, excel: pd.ExcelFile) -> Optional[Dict[str, str]]:
        # pandas 默认读 hidden sheet, 这里靠 sheet_name 找
        if META_SHEET_NAME not in excel.sheet_names:
            return None
        try:
            df = pd.read_excel(
                excel, sheet_name=META_SHEET_NAME, header=None,
                engine="openpyxl", keep_default_na=False,
            )
        except Exception as e:
            log.warning(f"读 _meta 失败: {e}")
            return None
        meta: Dict[str, str] = {}
        for _, row in df.iterrows():
            if len(row) < 2:
                continue
            k = str(row.iloc[0]).strip() if row.iloc[0] is not None else ""
            v = str(row.iloc[1]).strip() if row.iloc[1] is not None else ""
            if k:
                meta[k] = v
        return meta or None

    def _validate_meta(self, result: RoundtripParseResult) -> None:
        meta = result.meta or {}
        file_scope_type = meta.get("scope_type")
        file_scope_id = meta.get("scope_id")
        version = meta.get("version")

        result.scope_check = {
            "scope_type_matches": file_scope_type == self.scope_type,
            "scope_id_matches": str(file_scope_id) == str(self.scope_id) if file_scope_id is not None else False,
            "version_supported": (int(version) == SUPPORTED_META_VERSION) if version and version.isdigit() else False,
            "meta_scope_type": file_scope_type,
            "meta_scope_id": file_scope_id,
        }

    def _row_to_dict(self, row: pd.Series, actual_cols: List[str]) -> Dict[str, Any]:
        return {
            c: (None if pd.isna(row[c]) or row[c] == "" else row[c])
            for c in EXPECTED_DATA_COLUMNS
            if c in actual_cols
        }

    def _is_empty_row(self, row: Dict[str, Any]) -> bool:
        for v in row.values():
            if v is not None and not pd.isna(v) and str(v).strip():
                return False
        return True

    def _validate_row(self, row: Dict[str, Any], excel_row: int) -> Tuple[bool, List[Dict[str, str]], Dict[str, Any]]:
        errors: List[Dict[str, str]] = []
        parsed: Dict[str, Any] = {}

        # 必填: 用例名称
        case_name = row.get("用例名称")
        if not case_name or (isinstance(case_name, str) and not case_name.strip()):
            errors.append({"field": "用例名称", "message": "用例名称不能为空"})
        parsed["case_name"] = case_name

        # 用例ID: 整数或空
        raw_id = row.get("用例ID")
        if raw_id is None or (isinstance(raw_id, str) and not raw_id.strip()):
            parsed["case_id"] = None
        else:
            try:
                parsed["case_id"] = int(raw_id)
            except (ValueError, TypeError):
                # 占位, 防止后续 _is_empty_row / warning 读 KeyError
                parsed["case_id"] = None
                errors.append({"field": "用例ID", "message": f"用例ID 必须是整数, 收到: {raw_id!r}"})

        # 排序: 整数或空
        raw_sort = row.get("排序")
        if raw_sort is None or (isinstance(raw_sort, str) and not raw_sort.strip()):
            parsed["排序"] = None
        else:
            try:
                parsed["排序"] = int(raw_sort)
            except (ValueError, TypeError):
                parsed["排序"] = None
                errors.append({"field": "排序", "message": f"排序 必须是整数, 收到: {raw_sort!r}"})

        # UID: 字符串
        parsed["uid"] = str(row.get("UID") or "").strip() or None

        # 等级 / 类型 / 标签: 原样保留 (commit 阶段再做枚举校验)
        for k in ("用例等级", "用例类型", "用例标签", "所属分组", "前置条件", "备注"):
            v = row.get(k)
            parsed[k] = str(v).strip() if v is not None and not pd.isna(v) else None

        # 步骤序号: 整数或空
        raw_step = row.get("步骤序号")
        if raw_step is None or (isinstance(raw_step, str) and not str(raw_step).strip()):
            parsed["step_order"] = None
        else:
            try:
                parsed["step_order"] = int(raw_step)
            except (ValueError, TypeError):
                parsed["step_order"] = None
                errors.append({"field": "步骤序号", "message": f"步骤序号 必须是整数, 收到: {raw_step!r}"})

        # 步骤描述 / 预期结果
        parsed["action"] = str(row.get("操作步骤") or "").strip() or None
        parsed["expected_result"] = str(row.get("预期结果") or "").strip() or None

        # 更新时间: 字符串原样, commit 阶段再 parse + 比对乐观锁
        parsed["update_time"] = str(row.get("更新时间") or "").strip() or None

        # warning: 步骤行内 action + expected_result 双空
        if parsed["step_order"] is not None and not parsed["action"] and not parsed["expected_result"]:
            # 不阻断, 留作 warning
            pass

        return (len(errors) == 0, errors, parsed)

    def _check_sort_warnings(self, sort_values: List[Tuple[int, int]], result: RoundtripParseResult) -> None:
        if not sort_values:
            return
        seen: Dict[int, int] = {}
        duplicates: List[int] = []
        for s, _ in sort_values:
            seen[s] = seen.get(s, 0) + 1
            if seen[s] == 2:
                duplicates.append(s)
        if duplicates:
            result.warnings.append({
                "field": "排序",
                "message": f"排序列出现重复值: {duplicates}, commit 时会 normalize 为 1..N 连续",
            })
        # 跳号不警告 (normalize 时填), 但首次出现不连续时提一下
        nums = sorted(seen.keys())
        if nums and nums != list(range(1, len(nums) + 1)):
            result.warnings.append({
                "field": "排序",
                "message": f"排序列有跳号 (现有 {nums[:10]}{'...' if len(nums) > 10 else ''}), commit 时会 normalize",
            })

    def _compute_scope_check(self, result: RoundtripParseResult) -> Dict[str, Any]:
        # known / new 都按"用例组"算, 不按行. 组标识 = (排序, 用例名称)
        # 同一组 (同一用例的多步) 全 case_id=None 才算"新用例"
        # 这样新增用例 + 多个步骤 = 算 1 个 new, 不会膨胀
        from collections import defaultdict
        groups: Dict[Tuple[Any, Any], List[Dict[str, Any]]] = defaultdict(list)
        for r in result.valid_rows:
            key = (r.get("排序"), r.get("case_name"))
            groups[key].append(r)

        known_ids = {r["case_id"] for r in result.valid_rows if r.get("case_id") is not None}
        new_count = sum(
            1 for rows in groups.values()
            if rows and all(r.get("case_id") is None for r in rows)
        )

        # 解析 meta.case_ids_at_export
        meta_ids: List[int] = []
        raw = (result.meta or {}).get("case_ids_at_export", "")
        for x in raw.split(","):
            x = x.strip()
            if x.isdigit():
                meta_ids.append(int(x))
        intersect = sum(1 for cid in known_ids if cid in set(meta_ids))
        return {
            "case_ids_in_excel_known": len(known_ids),
            "case_ids_in_excel_new": new_count,
            "case_ids_at_export_total": len(meta_ids),
            "case_ids_intersect_with_at_export": intersect,
        }
