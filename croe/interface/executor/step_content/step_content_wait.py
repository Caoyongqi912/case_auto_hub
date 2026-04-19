#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : step_content_wait
# @Software: PyCharm
# @Desc: 等待步骤执行策略

import asyncio
from datetime import datetime
from typing import Optional

from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceContentStepResultMapper
)
from app.model.interfaceAPIModel.contents import InterfaceCaseContents
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from enums.CaseEnum import CaseStepContentType



class APIWaitContentStrategy(StepBaseStrategy):
    """等待步骤执行策略"""

    async def execute(self, step_context: CaseStepContext) -> bool:
        """
        等待指定时间

        设计说明：
        1. 等待指定时间
        2. 写入等待结果到 WaitStepContentResult

        Args:
            step_context: 步骤执行上下文

        Returns:
            是否执行成功（等待步骤总是返回True）
        """
        wait_time = step_context.content.wait_time

        if wait_time is None or wait_time < 0:
            wait_time = 0

        await step_context.starter.send(
            f"⏰⏰  等待 {wait_time} 秒"
        )
        await asyncio.sleep(wait_time)

        task_result_id = None
        if step_context.execution_context.task_result:
            task_result_id = step_context.execution_context.task_result.id

        await write_case_step_content_wait_result(
            step_index=step_context.index,
            interface_case_result_id=step_context.execution_context.case_result.id,
            step_content=step_context.content,
            wait_seconds=wait_time,
            interface_task_result_id=task_result_id,
        )

        return True


async def write_case_step_content_wait_result(
    step_index: int,
    interface_case_result_id: int,
    step_content: InterfaceCaseContents,
    wait_seconds: int,
    interface_task_result_id: Optional[int] = None,
) -> None:
    """
    写入等待步骤内容结果

    使用 InterfaceContentStepResultMapper.insert_result 方法，
    根据 content_type 自动创建对应的子类实例

    Args:
        step_index: 步骤索引
        interface_case_result_id: 用例执行结果ID
        step_content: 步骤内容实例
        wait_seconds: 等待秒数
        interface_task_result_id: 任务执行结果ID（可选）
    """
    await InterfaceContentStepResultMapper.insert_result(
        content_type=CaseStepContentType.STEP_API_WAIT,
        case_result_id=interface_case_result_id,
        task_result_id=interface_task_result_id,
        content_id=step_content.id,
        content_name=step_content.resolved_content_name,
        content_desc=step_content.content_desc,
        content_step=step_index,
        result=True,
        status="SUCCESS",
        start_time=datetime.now(),
        wait_seconds=wait_seconds,
    )
