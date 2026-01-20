#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @Software: PyCharm
# @Desc: 等待步骤执行器

import asyncio

from .base import StepStrategy
from interface.writer import InterfaceAPIWriter


class WaitStepStrategy(StepStrategy):
    """等待步骤执行器"""
    
    async def execute(self, step_context) -> bool:
        """执行等待步骤"""
        wait_time = step_context.step.api_wait_time
        
        await step_context.starter.send(f"⏰⏰  等待 {wait_time} 秒")
        await asyncio.sleep(wait_time)
        
        await InterfaceAPIWriter.set_case_step_content_api_wait_result(
            step_index=step_context.step_index,
            interface_case_result_id=step_context.interface_case_result_id,
            step_content=step_context.step,
            starter=step_context.starter,
            interface_task_result_id=step_context.interface_task_result_id
        )
        return True
