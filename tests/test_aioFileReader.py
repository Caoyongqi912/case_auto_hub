#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/5/25
# @Author : cyq
# @File : test_aioFileReader
# @Software: PyCharm
# @Desc: 测试 Excel 文件读取（独立版本）

import asyncio
import hashlib
import os
from io import BytesIO
from dataclasses import dataclass, field
from typing import List, Dict, Any

import pandas as pd

VALID_CASE_LEVELS = {"P0", "P1", "P2", "P3", "P4"}

EXCEL_COLUMNS = [
    "标题*", "用例状态", "前置条件", "步骤描述*", "预期结果*", "标签", "用例等级*", "用例类型", "备注"
]

FIELD_MAPPING = {
    "标题*": "case_name",
    "用例状态": "case_status",
    "前置条件": "case_setup",
    "步骤描述*": "action",
    "预期结果*": "expected_result",
    "标签": "case_tag",
    "用例等级*": "case_level",
    "用例类型": "case_type",
    "备注": "case_mark"
}


@dataclass
class ParseResult:
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


def _calculate_md5(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def read_excel(file_path: str) -> ParseResult:
    result = ParseResult()
    start_row_num = 4

    with open(file_path, 'rb') as f:
        content = f.read()
        result.file_md5 = _calculate_md5(content)
        file = BytesIO(content)

    try:
        excel_file = pd.ExcelFile(file, engine='openpyxl')
        available_sheets = excel_file.sheet_names
        print(f"📋 可用工作表: {available_sheets}")

        sheet_name = "用例" if "用例" in available_sheets else "template"
        print(f"📑 使用工作表: {sheet_name}")

        df = pd.read_excel(
            file,
            header=1,
            keep_default_na=False,
            na_values=['', 'nan'],
            sheet_name=sheet_name,
            engine='openpyxl'
        )
        df = df.where(pd.notnull(df), None)

        print(f"\n📊 Excel 列名: {list(df.columns)}")
        print(f"📊 总行数: {len(df)}")

        result.total_count = len(df)

        for df_index, row in df.iterrows():
            row_dict = dict(row)
            current_row = df_index + start_row_num

            is_valid = True
            errors = []

            case_tag = row_dict.get("标签")
            case_name = row_dict.get("标题*")

            if not case_tag:
                is_valid = False
                errors.append({"field": "标签", "message": "用例标签不能为空"})

            if not case_name:
                is_valid = False
                errors.append({"field": "标题*", "message": "用例名称不能为空"})

            mapped_case = {}
            for excel_col, field_name in FIELD_MAPPING.items():
                value = row_dict.get(excel_col)
                if pd.isna(value) or value == '':
                    value = None
                mapped_case[field_name] = value

            if not mapped_case.get("case_level") or mapped_case.get("case_level") not in VALID_CASE_LEVELS:
                mapped_case["case_level"] = "P2"

            if not mapped_case.get("case_type"):
                mapped_case["case_type"] = 1

            if is_valid:
                result.valid_cases.append(mapped_case)
                print(f"\n✅ 第 {current_row} 行有效用例:")
                for k, v in mapped_case.items():
                    if v:
                        print(f"   {k}: {str(v)[:50]}")
            else:
                result.errors.append({
                    "row": current_row,
                    "errors": errors
                })
                print(f"\n❌ 第 {current_row} 行错误: {errors}")

    except Exception as e:
        import traceback
        result.errors.append({
            "row": 0,
            "errors": [f"读取Excel时发生错误: {str(e)}\n{traceback.format_exc()}"]
        })

    return result


async def main():
    file_path = "/Users/cyq/Downloads/经纪-产品需求池_执行用例_导入模板 (1).xlsx"

    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return

    print(f"📂 测试文件: {file_path}")
    print("=" * 60)

    result = read_excel(file_path)

    print(f"\n\n{'=' * 60}")
    print(f"📊 解析结果汇总:")
    print(f"   文件 MD5: {result.file_md5}")
    print(f"   总行数: {result.total_count}")
    print(f"   有效用例: {result.valid_count}")
    print(f"   无效行数: {result.invalid_count}")

    if result.errors:
        print(f"\n❌ 错误汇总:")
        for i, err in enumerate(result.errors, 1):
            print(f"   {i}. 行 {err.get('row')}: {err.get('errors')}")

    print("\n" + "=" * 60)
    print(f"✅ 测试完成!")


if __name__ == "__main__":
    asyncio.run(main())