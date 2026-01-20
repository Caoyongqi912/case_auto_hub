#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : api_step
# @Software: PyCharm
# @Desc: 接口步骤执行器

from app.mapper.interface import InterfaceMapper
from app.model.interface.interfaceResultModel import InterfaceResultModel
from enums import InterfaceAPIResultEnum
from .base import StepStrategy
from interface.writer import InterfaceAPIWriter


class ApiStepStrategy(StepStrategy):
    """接口步骤执行器"""
    
    def __init__(self, interface_executor):
        self.interface_executor = interface_executor
    
    async def execute(self, step_context) -> bool:
        """执行单个API步骤"""
        interface = await InterfaceMapper.get_by_id(ident=step_context.step.target_id)
        
        step_result, interface_result = await self.interface_executor.execute(
            interface=interface,
            env=step_context.execution_context.env,
            case_result=step_context.execution_context.case_result
        )
        
        interface_result = await InterfaceAPIWriter.write_interface_result(**interface_result)
        
        case_result = step_context.execution_context.case_result
        if step_result:
            case_result.success_num += 1
        else:
            case_result.result = InterfaceAPIResultEnum.ERROR
            case_result.fail_num += 1
        
        return step_result
