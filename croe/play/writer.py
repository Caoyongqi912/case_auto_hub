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
from app.mapper.play.playResultMapper import PlayContentResultMapper
from app.mapper.play.playTaskMapper import PlayTaskMapper, PlayTaskResultMapper
from app.model.base import FileModel
from app.model.playUI import PlayCaseResult, PlayTaskResult, PlayCase
from app.model.playUI.PlayResult import PlayStepContentResult
from croe.play.starter import UIStarter
from utils import log
from enums.CaseEnum import Result, Status
from config import Config
from utils import GenerateTools
import os


class ContentResultWriter:
    """
    步骤结果写入
    - 步骤1
    - 步骤2
    - 步骤组3
        - 步骤组3-1
        - 步骤组3-2
    - 步骤4
    
    存储结构:
    {
        1: {"result": step1_result, "children": []},
        2: {"result": step2_result, "children": []},
        3: {"result": group3_result, "children": [child1, child2]},
        4: {"result": step4_result, "children": []}
    }
    """

    def __init__(self, play_case_result_id: int, play_task_result_id: Optional[int] = None):
        self.play_case_result_id = play_case_result_id
        self.play_task_result_id = play_task_result_id
        self.content_results = {}

    async def add_content_result(self, step_index: int, content_result: PlayStepContentResult):
        """
        添加主步骤结果
        Args:
            step_index (int): 主步骤的索引
            content_result (PlayStepContentResult): 主步骤的结果对象
        """
        content_result.play_case_result_id = self.play_case_result_id
        content_result.play_task_result_id = self.play_task_result_id
        self.content_results[step_index] = {
            "result": content_result,
            "children": []
        }
    
    async def update_content_result(self, step_index: int, success:bool):
        """
        更新主步骤结果
        Args:
            step_index (int): 主步骤的索引
            success (bool): 主步骤的执行结果
        """
        if step_index in self.content_results:
            self.content_results[step_index]["result"].content_result = success
        else:
            log.warning(f"[ContentResultWriter] Step index {step_index} not found")
     
    
    async def add_child_content_result(self, parent_index: int, content_result: PlayStepContentResult):
        """
        添加子步骤结果到指定父步骤
        Args:
            parent_index (int): 父步骤的索引
            content_result (PlayStepContentResult): 子步骤的结果对象
        """
        content_result.play_case_result_id = self.play_case_result_id
        content_result.play_task_result_id = self.play_task_result_id
        if parent_index in self.content_results:
            self.content_results[parent_index]["children"].append(content_result)
        else:
            log.warning(f"[ContentResultWriter] Parent index {parent_index} not found, adding as main step")
    


    async def flush(self):
        if not self.content_results:
            log.error("[ContentResultWriter] No content results to write")
            return
        
        # 直接批量插入所有结果
        count = await PlayContentResultMapper.save_result_batch(self.content_results)
        log.info(f"[ContentResultWriter] Batch inserted {count} results")

    @property
    def results(self):
        """
        返回展平的结果列表
        """
        return len(self.content_results)

    def __repr__(self):
        return f"<ContentResultWriter case_result_id={self.play_case_result_id}> task_result_id={self.play_task_result_id}> results={len(self.content_results)}> />"


class PlayCaseResultWriter:
    """
    UI 业务流 结果写入
    """

    def __init__(self, starter: UIStarter, play_task_result_id: int = None):
        self._starter = starter
        self.play_case_result: Optional[PlayCaseResult] = None
        self.play_task_result_id = play_task_result_id

    @property
    def play_case_result_id(self):
        if self.play_case_result:
            return self.play_case_result.id
        else:
            log.warning("[PlayCaseResultWriter] No case result to write")
            return None

    async def init_result(self, play_case: PlayCase, vars_info: Dict[str, str] = None):
        """
        初始化
        """
        vars_list = self._build_vars(vars_info)
        self.play_case_result = await PlayCaseResultMapper.init_case_result(
            play_case=play_case,
            user=self._starter,
            task_result_id=self.play_task_result_id,
            vars_list=vars_list,
        )

    async def write_result(self, SUCCESS=bool):
        """
        写入最终结果
        """
        end_time = datetime.datetime.now()
        self.play_case_result.end_time = end_time
        self.play_case_result.use_time = GenerateTools.timeDiff(self.play_case_result.start_time, end_time)
        self.play_case_result.status = Status.DONE
        self.play_case_result.result = Result.SUCCESS if SUCCESS else Result.FAIL
        self.play_case_result.running_logs = "".join(self._starter.logs)
        await PlayCaseResultMapper.set_case_result(self.play_case_result)


    @staticmethod
    def _build_vars(vars_map: Dict[str, Any]):
        """
        写入前置变量
        """
        vars_list = []
        for k, v in vars_map.items():
            _varsInfo = {
                "id": GenerateTools.getTime(3),
                "step_name": "Before_Vars",
                "extract_method": "Before",
                "key": k,
                "value": v
            }
            vars_list.append(_varsInfo)
        return vars_list

    def __repr__(self):
        return f"<PlayCaseResultWriter case_result_id={self.play_case_result_id}, case_task_result_id={self.play_task_result_id}>"


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
