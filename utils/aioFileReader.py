#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/9/9
# @Author : cyq
# @File : aioFileReader
# @Software: PyCharm
# @Desc:
import asyncio
from typing import List, Dict, Any
import pandas as pd
from fastapi import UploadFile
from io import BytesIO

from utils.threadPool import ThreadPoolHelper

TEST_CASE_FIELD_NAMES = ["case_tag", "case_name", "case_setup", "action", "expected_result", "case_level", "case_type"]
TEST_CASE_SHEET_NAME = "用例"


class AsyncFilesReader:
    def __init__(self):
        self.tph = ThreadPoolHelper(workers=2)

    async def async_read_excel_for_case(self, file: UploadFile):
        file_content = await file.read()
        file_bytes = BytesIO(file_content)
        loop = asyncio.get_event_loop()
        return await self.tph.run_in_exe(loop, self.__read, file_bytes)

    @staticmethod
    def __read(file: BytesIO) -> tuple[List[Dict[str, Any]], List[str]]:
        data_rows: List[Dict[str, Any]] = []
        messages: List[str] = []
        start_row_num = 3

        try:
            excel_file = pd.ExcelFile(file, engine='openpyxl')
            available_sheets = excel_file.sheet_names
            sheet_name = TEST_CASE_SHEET_NAME if TEST_CASE_SHEET_NAME in available_sheets else available_sheets[0]

            df = pd.read_excel(file,
                               header=1,
                               keep_default_na=False,
                               na_values=['', 'nan'],
                               sheet_name=sheet_name,
                               engine='openpyxl')
            df = df.where(pd.notnull(df), None)

            for df_index, row in df.iterrows():
                if row.isnull().all():
                    continue
                row_data = []
                for value in row.iloc[:len(TEST_CASE_FIELD_NAMES)]:
                    if pd.isna(value):
                        row_data.append(None)
                    else:
                        row_data.append(value)

                current_row_num = df_index + start_row_num
                if not row_data[0] or not row_data[1]:
                    messages.append(f"第{current_row_num}行标签或用例名为空")
                    continue

                if not row_data[5]:
                    row_data[5] = "P2"
                if not row_data[6]:
                    row_data[6] = 1

                data_rows.append(dict(zip(TEST_CASE_FIELD_NAMES, row_data)))
        except Exception as e:
            messages.append(f"读取Excel时发生错误: {str(e)}")
            raise

        return data_rows, messages
