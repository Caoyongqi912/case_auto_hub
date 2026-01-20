#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @Software: PyCharm
# @Desc: 脚本步骤执行器

from enums import InterfaceExtractTargetVariablesEnum
from interface.exec.execSafeScript import ExecSafeScript
from .base import StepStrategy
from interface.writer import InterfaceAPIWriter


class ScriptStepStrategy(StepStrategy):
    """脚本步骤执行器"""
    
    async def execute(self, step_context) -> bool:
        """执行脚本步骤"""
        script = step_context.step.api_script_text
        exe = ExecSafeScript()
        temp_vars = exe.execute(script)
        
        await step_context.variable_manager.add_vars(temp_vars)
        
        await step_context.starter.send(
            f"🫳🫳  脚本变量 = {temp_vars}"
        )
        
        await InterfaceAPIWriter.set_case_step_content_api_script_vars_result(
            step_index=step_context.step_index,
            interface_case_result_id=step_context.interface_case_result_id,
            step_content=step_context.step,
            starter=step_context.starter,
            script_vars=[{
                InterfaceExtractTargetVariablesEnum.KEY: k,
                InterfaceExtractTargetVariablesEnum.VALUE: v,
                InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.StepScript
            } for k, v in temp_vars.items()],
            interface_task_result_id=step_context.interface_task_result_id
        )
        return True
