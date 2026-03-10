#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : step_content_script.py
# @Software: PyCharm
# @Desc:
import json

from app.mapper.interface import InterfaceContentStepResultMapper
from app.model.interface.interfaceResultModel import InterfaceCaseStepContentResult
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.a_manager import ScriptManager, ScriptSecurityError
from croe.interface.types import InterfaceCaseContent, VARS
from enums import ExtractTargetVariablesEnum
from croe.interface.starter import APIStarter
from utils import log


class APIScriptContentStrategy(StepBaseStrategy):

    async def execute(self, step_context: CaseStepContext) -> bool:
        """
        执行脚本
        """
        script = step_context.content.script_text
        script_vars = None
        if script:
            try:
                script_manger = ScriptManager()
                _extracted_vars = script_manger.execute(script)
                log.debug(_extracted_vars)
                script_vars = [{
                    ExtractTargetVariablesEnum.KEY: k,
                    ExtractTargetVariablesEnum.VALUE: v,
                    ExtractTargetVariablesEnum.Target: ExtractTargetVariablesEnum.StepScript
                } for k, v in _extracted_vars.items()]
                await step_context.variable_manager.add_vars(_extracted_vars)
                await step_context.starter.send(f"🫳🫳  脚本变量 = {json.dumps(_extracted_vars, ensure_ascii=False)}")
            except ScriptSecurityError as e:
                await step_context.starter.send(f"脚本执行安全错误: {e}")
                return False

        await set_case_step_content_api_script_vars_result(
            step_index=step_context.index,
            interface_case_result_id=step_context.case_result_id,
            interface_task_result_id=step_context.task_result_id,
            step_content=step_context.content,
            starter=step_context.starter,
            script_vars=script_vars,
        )
        return True


async def set_case_step_content_api_script_vars_result(
        step_index: int,
        interface_case_result_id: int,
        step_content: "InterfaceCaseContent",
        starter: APIStarter,
        script_vars: VARS,
        interface_task_result_id: int = None,

):
    """
    脚本变量写入
    """
    result = InterfaceCaseStepContentResult(
        content_id=step_content.id,
        content_type=step_content.content_type,
        content_name=step_content.content_name,
        content_desc=step_content.content_desc,
        content_result=True,
        content_step=step_index,
        interface_case_result_id=interface_case_result_id,
        interface_task_result_id=interface_task_result_id,
        starter_id=starter.userId,
        script_extracts=script_vars,
        starter_name=starter.username,
    )
    await InterfaceContentStepResultMapper.insert(result)
