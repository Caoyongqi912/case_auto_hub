#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/9/9
# @Author : cyq
# @File : aioFileReader
# @Software: PyCharm
# @Desc: Excel 文件读取工具类

import asyncio
import hashlib
from typing import List, Dict, Any
from dataclasses import dataclass, field

import pandas as pd
from fastapi import UploadFile
from io import BytesIO

from utils.threadPool import ThreadPoolHelper

FIELD_MAPPING = {
    "标题*": "case_name",
    "前置条件": "case_setup",
    "步骤描述*": "action",
    "预期结果*": "expected_result",
    "标签": "case_tag",
    "用例等级*": "case_level",
    "用例类型": "case_type",
    "备注": "case_mark"
}

VALID_CASE_LEVELS = {"P0", "P1", "P2", "P3", "P4"}
UPLOAD_CACHE_EXPIRES = 1800
MAX_FILE_SIZE = 10 * 1024 * 1024


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


class AsyncFilesReader:
    def __init__(self, workers: int = 4):
        self.tph = ThreadPoolHelper(workers=workers)

    async def async_read_excel_for_case(self, file: UploadFile) -> ParseResult:
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise ValueError(f"文件大小超过限制，最大支持 {MAX_FILE_SIZE // 1024 // 1024}MB")
        file_bytes = BytesIO(file_content)
        file_md5 = self._calculate_md5(file_content)
        loop = asyncio.get_event_loop()
        await file.seek(0)
        return await self.tph.run_in_exe(loop, self.__read, file_bytes, file_md5)

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
    def __read(file: BytesIO, file_md5: str) -> ParseResult:
        result = ParseResult(file_md5=file_md5)
        start_row_num = 2

        try:
            excel_file = pd.ExcelFile(file, engine='openpyxl')
            available_sheets = excel_file.sheet_names
            sheet_name = "用例" if "用例" in available_sheets else "template"

            df = pd.read_excel(
                file,
                header=0,
                keep_default_na=False,
                na_values=['', 'nan'],
                sheet_name=sheet_name,
                engine='openpyxl'
            )
            df = df.where(pd.notnull(df), None)

            result.total_count = len(df)

            for df_index, row in df.iterrows():
                row_dict = dict(row)

                if AsyncFilesReader._is_empty_row(row_dict):
                    continue

                current_row = df_index + start_row_num

                case_name = row_dict.get("标题*")

                is_valid = True
                errors = []

   
                if not case_name or pd.isna(case_name):
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
                else:
                    result.errors.append({
                        "row": current_row,
                        "errors": errors
                    })

        except Exception as e:
            log.error(f"读取Excel时发生错误: {e}")
            raise ValueError(f"读取Excel时发生错误")
     

        return result


async def read_excel_async(file: UploadFile) -> ParseResult:
    reader = AsyncFilesReader()
    return await reader.async_read_excel_for_case(file)