#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : step_content_script.py
# @Software: PyCharm
# @Desc: 脚本步骤执行策略

import json
from datetime import datetime
from typing import Optional

from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceContentStepResultMapper
)
from app.model.interfaceAPIModel.contents import InterfaceCaseContents
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.a_manager import ScriptManager, ScriptSecurityError
from enums.CaseEnum import CaseStepContentType
from utils import log




class APIScriptContentStrategy(StepBaseStrategy):
    """脚本步骤执行策略"""

    async def execute(self, step_context: CaseStepContext) -> bool:
        """
        执行脚本

        设计说明：
        1. 执行自定义脚本
        2. 提取变量
        3. 写入脚本结果到 ScriptStepContentResult

        Args:
            step_context: 步骤执行上下文

        Returns:
            是否执行成功
        """
        script = step_context.content.script_text
        script_output = None
        script_error = None
        success = True

        if script:
            try:
                script_manager = ScriptManager()
                extracted_vars = script_manager.execute(script)
                log.debug(f"脚本执行结果: {extracted_vars}")

                script_output = json.dumps(
                    extracted_vars, ensure_ascii=False
                )

                await step_context.variable_manager.add_vars(extracted_vars)
                await step_context.starter.send(
                    f"🫳🫳  脚本变量 = "
                    f"{json.dumps(extracted_vars, ensure_ascii=False)}"
                )
            except ScriptSecurityError as e:
                script_error = str(e)
                success = False
                await step_context.starter.send(
                    f"脚本执行安全错误: {e}"
                )
            except Exception as e:
                script_error = str(e)
                success = False
                await step_context.starter.send(
                    f"脚本执行错误: {e}"
                )

        task_result_id = None
        if step_context.execution_context.task_result:
            task_result_id = step_context.execution_context.task_result.id

        await write_case_step_content_script_result(
            step_index=step_context.index,
            interface_case_result_id=step_context.execution_context.case_result.id,
            step_content=step_context.content,
            script_output=script_output,
            script_error=script_error,
            success=success,
            interface_task_result_id=task_result_id,
        )

        return success


async def write_case_step_content_script_result(
    step_index: int,
    interface_case_result_id: int,
    step_content: InterfaceCaseContents,
    script_output: Optional[str],
    script_error: Optional[str],
    success: bool,
    interface_task_result_id: Optional[int] = None,
) -> None:
    """
    写入脚本步骤内容结果

    使用 InterfaceContentStepResultMapper.insert_result 方法，
    根据 content_type 自动创建对应的子类实例

    Args:
        step_index: 步骤索引
        interface_case_result_id: 用例执行结果ID
        step_content: 步骤内容实例
        script_output: 脚本输出
        script_error: 脚本错误
        success: 是否成功
        interface_task_result_id: 任务执行结果ID（可选）
    """
    await InterfaceContentStepResultMapper.insert_result(
        content_type=CaseStepContentType.STEP_API_SCRIPT,
        case_result_id=interface_case_result_id,
        task_result_id=interface_task_result_id,
        content_id=step_content.id,
        content_name=step_content.resolved_content_name,
        content_desc=step_content.content_desc,
        content_step=step_index,
        result=success,
        status="SUCCESS" if success else "FAIL",
        start_time=datetime.now(),
        script_output=script_output,
        script_error=script_error,
    )
