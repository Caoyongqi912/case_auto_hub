#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @Software: PyCharm
# @Desc: 条件步骤执行器

from app.mapper.interface import InterfaceConditionMapper
from app.model.interface.InterfaceCaseStepContent import InterfaceCondition
from enums import InterfaceAPIResultEnum
from utils import GenerateTools
from interface.exec.execCondition import ExecCondition
from .base import StepStrategy
from interface.writer import InterfaceAPIWriter


class ConditionStepStrategy(StepStrategy):
    """条件步骤执行器"""
    
    def __init__(self, interface_executor):
        self.interface_executor = interface_executor
    
    async def execute(self, step_context) -> bool:
        """执行条件步骤"""
        condition: InterfaceCondition = await InterfaceConditionMapper.get_by_id(ident=step_context.step.target_id)
        
        _execCondition = ExecCondition(step_context.variable_manager.vars)
        condition_passed, content_condition = await _execCondition.invoke(condition, step_context.starter)
        
        start_time = GenerateTools.getTime(1)
        case_result = step_context.execution_context.case_result
        
        _content_result = await InterfaceAPIWriter.set_case_step_content_api_condition_result(
            step_index=step_context.step_index,
            interface_case_result_id=step_context.interface_case_result_id,
            interface_task_result_id=step_context.interface_task_result_id,
            step_content=step_context.step,
            starter=step_context.starter,
            start_time=start_time,
            content_condition=content_condition,
        )
        
        if condition_passed:
            await step_context.starter.send("✍️✍️  执行条件判断通过 🎉🎉")
            
            condition_apis = await InterfaceConditionMapper.query_condition_apis_by_content_id(condition.id)
            
            if not condition_apis:
                _content_result.content_result = True
                await InterfaceAPIWriter.set_content_finally_result(_content_result)
                case_result.success_num += 1
                return True
            
            for index, interface in enumerate(condition_apis, start=1):
                await step_context.starter.send(
                    f"✍️✍️  {'-' * 20} 执行条件步骤 {index}/{len(condition_apis)}: "
                    f"{interface.name} {'-' * 20}"
                )
                
                result, api_success = await self.interface_executor.execute(
                    interface=interface,
                    env=step_context.execution_context.env,
                    case_result=case_result
                )
                
                await InterfaceAPIWriter.write_interface_result(
                    interface_condition_result_id=_content_result.id,
                    **result
                )
                
                if not api_success:
                    await step_context.starter.send(f"✍️✍️  步骤 {index}/{len(condition_apis)} 执行失败，停止后续执行")
                    case_result.result = InterfaceAPIResultEnum.ERROR
                    case_result.fail_num += 1
                    _content_result.content_result = False
                    await InterfaceAPIWriter.set_content_finally_result(_content_result)
                    return False
                
                case_result.success_num += 1
            
            _content_result.content_result = True
            await InterfaceAPIWriter.set_content_finally_result(_content_result)
            return True
        else:
            await step_context.starter.send("✍️✍️  执行条件判断未通过 ❌❌  跳过子步骤")
            case_result.success_num += 1
            _content_result.content_result = True
            await InterfaceAPIWriter.set_content_finally_result(_content_result)
            return True
