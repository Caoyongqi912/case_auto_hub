#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : step_content_assert
# @Software: PyCharm
# @Desc: 断言步骤执行策略

from datetime import datetime
from typing import Optional, List, Dict, Any

from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceContentStepResultMapper
)
from app.model.interfaceAPIModel.contents import InterfaceCaseContents
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.a_manager.assert_manager import AssertManager
from enums.CaseEnum import CaseStepContentType
from utils import log

VARS = List[Dict[str, Any]]


class APIAssertsContentStrategy(StepBaseStrategy):
    """断言步骤执行策略"""

    async def execute(self, step_context: CaseStepContext) -> bool:
        """
        执行断言

        设计说明：
        1. 执行断言验证
        2. 写入断言结果到 AssertStepContentResult
        3. 更新用例统计信息

        Args:
            step_context: 步骤执行上下文

        Returns:
            是否执行成功
        """
        try:
            case_result = step_context.execution_context.case_result

            assert_exec = AssertManager(
                variables=step_context.variable_manager.variables
            )

            if not step_context.content.assert_list:
                await step_context.starter.send(
                    "🆚🆚 断言:  ⚠️⚠️ 未配置断言"
                )
                return True

            assert_result_list, assert_success = await assert_exec.assert_content_list(
                step_context.content.assert_list
            )

            task_result_id = None
            if step_context.execution_context.task_result:
                task_result_id = step_context.execution_context.task_result.id

            await write_case_step_content_assert_result(
                step_index=step_context.index,
                interface_case_result_id=step_context.execution_context.case_result.id,
                step_content=step_context.content,
                assert_data=assert_result_list,
                assert_result=assert_success,
                interface_task_result_id=task_result_id,
            )

            if assert_success:
                case_result.success_num += 1
            else:
                case_result.fail_num += 1

            return True

        except AssertionError as e:
            log.exception(f"断言异常: {e}")
            await step_context.starter.send(
                f"⚠️⚠️ 步骤断言异常: {str(e)}"
            )
            return False


async def write_case_step_content_assert_result(
    step_index: int,
    interface_case_result_id: int,
    step_content: InterfaceCaseContents,
    assert_data: VARS,
    assert_result: bool,
    interface_task_result_id: Optional[int] = None,
) -> None:
    """
    写入断言步骤内容结果

    使用 InterfaceContentStepResultMapper.insert_result 方法，
    根据 content_type 自动创建对应的子类实例

    Args:
        step_index: 步骤索引
        interface_case_result_id: 用例执行结果ID
        step_content: 步骤内容实例
        assert_data: 断言数据
        assert_result: 断言结果
        interface_task_result_id: 任务执行结果ID（可选）
    """
    await InterfaceContentStepResultMapper.insert_result(
        content_type=CaseStepContentType.STEP_API_ASSERT,
        case_result_id=interface_case_result_id,
        task_result_id=interface_task_result_id,
        content_id=step_content.id,
        content_name=step_content.resolved_content_name,
        content_desc=step_content.content_desc,
        content_step=step_index,
        result=assert_result,
        status="SUCCESS" if assert_result else "FAIL",
        start_time=datetime.now(),
        assert_data=assert_data,
        assert_result=assert_result,
    )
