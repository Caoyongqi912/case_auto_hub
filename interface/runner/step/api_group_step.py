#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @Software: PyCharm
# @Desc: 接口组步骤执行器

from app.mapper.interface.interfaceGroupMapper import InterfaceGroupMapper
from app.mapper.interface import InterfaceGroupResultMapper
from app.model.interface.interfaceResultModel import InterfaceGroupResult
from enums import InterfaceAPIResultEnum
from .base import StepStrategy
from interface.writer import InterfaceAPIWriter


class ApiGroupStepStrategy(StepStrategy):
    """接口组步骤执行器"""
    
    def __init__(self, interface_executor):
        self.interface_executor = interface_executor
    
    async def execute(self, step_context) -> bool:
        """执行接口组步骤"""
        interfaces = await InterfaceGroupMapper.query_apis(groupId=step_context.step.target_id)
        
        group_result = await InterfaceGroupResultMapper.init_model(
            group_name=step_context.step.content_name,
            group_api_num=len(interfaces),
            interface_case_result_id=step_context.interface_case_result_id
        )
        
        if not interfaces:
            return True
        
        for index, interface in enumerate(interfaces, start=1):
            await step_context.starter.send(f"✍️✍️  EXECUTE GROUP STEP {index} : {interface}")
            
            result, flag = await self.interface_executor.execute(
                interface=interface,
                env=step_context.execution_context.env,
                case_result=step_context.execution_context.case_result
            )
            
            await InterfaceAPIWriter.write_interface_result(
                interface_group_result_id=group_result.id,
                **result
            )
            
            if not flag:
                case_result = step_context.execution_context.case_result
                case_result.result = InterfaceAPIResultEnum.ERROR
                case_result.fail_num += 1
                return False
        
        case_result = step_context.execution_context.case_result
        case_result.success_num += 1
        return True
