#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/9
# @Author : cyq
# @File : writer
# @Software: PyCharm
# @Desc:
import datetime
from typing import Dict, Any, Optional

from app.mapper.play import PlayCaseResultMapper
from app.mapper.file import FileMapper
from app.mapper.play.playTaskMapper import PlayTaskMapper, PlayTaskResultMapper
from app.model.base import FileModel
from app.model.playUI import PlayCaseResult, PlayTaskResult
from app.model.playUI.PlayResult import PlayStepContentResult
from croe.play.starter import UIStarter
from utils import log
from enums.CaseEnum import Result, Status
from config import Config
from utils import GenerateTools
import os


class ContentResultWriter:

    def __init__(self, play_case_result_id: int, play_task_result_id: Optional[int] = None):
        self.play_case_result_id = play_case_result_id
        self.play_task_result_id = play_task_result_id
        self.content_results = []

    async def add_content_result(self, content_result: PlayStepContentResult):
        content_result.play_case_result_id = self.play_case_result_id,
        content_result.play_task_result_id = self.play_task_result_id,
        self.content_results.append(    
            content_result,
        )

    async def flush(self):
        if not self.content_results:
            return


class Writer:
        """
        执行db记录
        """

        @staticmethod
        async def write_base_result(base_result: PlayTaskResult):
            """
            回写测试结果
            :param base_result: 测试结果实体
            :return:
            """
            eTime = datetime.datetime.now()
            base_result.rate_number = round(base_result.success_number / base_result.total_number * 100, 2)
            base_result.end_time = eTime
            base_result.total_usetime = GenerateTools.timeDiff(base_result.start_time, eTime)
            base_result.status = Status.DONE
            if base_result.fail_number > 0:
                base_result.result = Result.FAIL
            else:
                base_result.result = Result.SUCCESS
            await PlayTaskMapper.set_task_status(base_result.task_id, Status.WAIT)

            return await PlayTaskResultMapper.set_result(base_result)

        @staticmethod
        async def write_case_result(case_result: PlayCaseResult,
                                    starter: UIStarter,
                                    errorMsgMap: Dict[str, str] = None):
            """
            回写测试结果
            :param case_result: 测试结果实体
            :param starter: UIStarter
            :param errorMsgMap: 错误信息
            :return:
            """
            eTime = datetime.datetime.now()
            case_result.end_time = eTime
            case_result.use_time = GenerateTools.timeDiff(case_result.start_time, eTime)
            case_result.result = Result.SUCCESS
            case_result.status = Status.DONE
            case_result.running_logs = "".join(starter.logs)

            if errorMsgMap:
                log.info(f"error_msg = {errorMsgMap}")
                case_result.result = Result.FAIL
                PATH_KEY = "ui_case_err_step_pic_path"
                if errorMsgMap.get(PATH_KEY):
                    file = await Writer.write_error_file(errorMsgMap.get(PATH_KEY))
                    errorMsgMap[PATH_KEY] = f"{Config.UI_ERROR_PATH}{file.uid}"
                for k, v in errorMsgMap.items():
                    setattr(case_result, k, v)
            await PlayCaseResultMapper.set_case_result(case_result)

        @staticmethod
        async def write_error_file(filepath: str) -> FileModel:
            """
            db 写入 file
            :param filepath:
            :return:
            """
            fileName = os.path.split(filepath)[-1]
            file = await FileMapper.insert_file(
                filePath=filepath,
                fileName=fileName
            )
            return file

        @staticmethod
        async def write_assert_info(case_result: PlayCaseResult,
                                    assertsInfo: Any = None):
            """
            写入assertInfo
            :param case_result:
            :param assertsInfo:
            :return:
            """

            if case_result.asserts_info is None:
                case_result.asserts_info = []

            case_result.asserts_info.extend(assertsInfo)
            await PlayCaseResultMapper.set_case_result_assertInfo(case_result.id, case_result.asserts_info)

        @staticmethod
        async def write_vars_info(case_result: PlayCaseResult,
                                  step_name: str,
                                  extract_method: str,
                                  varsInfo: Dict[str, Any] = None):
            """
            写入assertInfo
            :param case_result:
            :param extract_method:
            :param step_name:
            :param varsInfo:
            :return:
            """
            for k, v in varsInfo.items():
                _varsInfo = {
                    "id": GenerateTools.getTime(3),
                    "step_name": step_name,
                    "extract_method": extract_method,
                    "key": k,
                    "value": v
                }
                case_result.vars_info.append(_varsInfo)
            unique_dict = {}
            for item in case_result.vars_info:
                ck = (item['key'], item['value'])
                unique_dict[ck] = item
            unique_data = list(unique_dict.values())
            await PlayCaseResultMapper.set_case_result_varsInfo(case_result.id, unique_data)
