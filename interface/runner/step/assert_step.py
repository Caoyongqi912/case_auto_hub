#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @Software: PyCharm
# @Desc: 断言步骤执行器

from interface.exec.execAssert import ExecAsserts
from utils import log
from .base import StepStrategy
from interface.writer import InterfaceAPIWriter


class AssertStepStrategy(StepStrategy):
    """断言步骤执行器"""
    
    async def execute(self, step_context) -> bool:
        """执行断言步骤"""
        try:
            case_result = step_context.execution_context.case_result
            _assert_exec = ExecAsserts(variables=step_context.variable_manager.get_vars())
            assert_list_info, assert_success = await _assert_exec.assert_content_list(step_context.step)
            
            if not assert_list_info:
                await step_context.starter.send(
                    f"🆚🆚 断言:  ⚠️⚠️ 未配置断言"
                )
                return True
            
            if assert_success is False:
                case_result.fail_num += 1
            else:
                case_result.success_num += 1
            
            await InterfaceAPIWriter.set_case_step_content_api_assert_result(
                step_index=step_context.step_index,
                interface_case_result_id=step_context.interface_case_result_id,
                interface_task_result_id=step_context.interface_task_result_id,
                assert_data=assert_list_info,
                step_content=step_context.step,
                starter=step_context.starter
            )
            return assert_success
        except Exception as e:
            log.exception(e)
            await step_context.starter.send(f"⚠️⚠️ 步骤断言异常: {str(e)}")
            return False
