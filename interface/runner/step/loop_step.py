#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : loop_step_strategy
# @Software: PyCharm
# @Desc: 循环步骤策略

from app.mapper.interface.interfaceCaseMapper import InterfaceLoopMapper
from utils import GenerateTools
from interface.runner.loop import get_loop_executor
from interface.writer import InterfaceAPIWriter
from .base import StepStrategy


class LoopStepStrategy(StepStrategy):
    """循环步骤执行器"""
    
    def __init__(self, interface_executor):
        self.interface_executor = interface_executor
    
    async def execute(self, step_context) -> bool:
        """执行循环步骤"""
        loop = await InterfaceLoopMapper.get_by_id(ident=step_context.step.target_id)
        loop_steps = await InterfaceLoopMapper.query_loop_apis_by_content_id(loop_id=step_context.step.target_id)
        
        start_time = GenerateTools.getTime(1)
        _content_result = await InterfaceAPIWriter.init_case_step_loop_result(
            step_index=step_context.step_index,
            interface_case_result_id=step_context.interface_case_result_id,
            interface_task_result_id=step_context.interface_task_result_id,
            step_content=step_context.step,
            starter=step_context.starter,
            start_time=start_time,
        )
        
        executor = get_loop_executor(
            loop.loop_type,
            step_context.starter,
            step_context.variable_manager,
            self.interface_executor
        )
        
        await executor.execute(
            loop=loop,
            api_steps=loop_steps,
            env=step_context.execution_context.env,
            content_result=_content_result
        )
        
        return _content_result.content_result
