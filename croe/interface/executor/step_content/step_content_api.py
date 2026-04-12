#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : api
# @Software: PyCharm
# @Desc: API步骤执行策略

from typing import Optional, TYPE_CHECKING

from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceContentStepResultMapper
)
from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
from app.model.interfaceAPIModel import InterfaceResult
from app.model.interfaceAPIModel.contents import InterfaceCaseContents
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.interface.writer import write_interface_result
from enums import InterfaceAPIResultEnum
from enums.CaseEnum import CaseStepContentType

if TYPE_CHECKING:
    from croe.interface.executor.interface_executor import InterfaceExecutor


class APIStepContentStrategy(StepBaseStrategy):
    """API步骤执行策略"""

    async def execute(self, step_context: CaseStepContext) -> bool:
        """
        执行API步骤

        Args:
            step_context: 步骤执行上下文

        Returns:
            是否执行成功
        """
        interface = await InterfaceMapper.get_by_id(
            ident=step_context.content.target_id
        )

        if not interface:
            await step_context.starter.send(
                f"未找到接口: id={step_context.content.target_id}"
            )
            return False

        step_result, success = await self.interface_executor.execute(
            interface=interface,
            env=step_context.execution_context.env,
            case_result=step_context.execution_context.case_result,
            task_result=step_context.execution_context.task_result,
        )

        interface_result = await write_interface_result(**step_result)

        await write_case_step_content_api_result(
            step_index=step_context.index,
            interface_case_result_id=step_context.execution_context.case_result.id,
            step_content=step_context.content,
            interface_result=interface_result,
            success=success,
            interface_task_result_id=step_context.task_result_id,
        )

        case_result = step_context.execution_context.case_result
        if success:
            case_result.success_num += 1
        else:
            case_result.fail_num += 1
            case_result.result = InterfaceAPIResultEnum.ERROR

        return success


async def write_case_step_content_api_result(
    step_index: int,
    interface_case_result_id: int,
    step_content: InterfaceCaseContents,
    interface_result: InterfaceResult,
    success: bool,
    interface_task_result_id: Optional[int] = None,
) -> None:
    """
    写入API步骤内容结果

    使用 InterfaceContentStepResultMapper.insert_result 方法，
    根据 content_type 自动创建对应的子类实例

    Args:
        step_index: 步骤索引
        interface_case_result_id: 用例执行结果ID
        step_content: 步骤内容实例
        interface_result: 接口执行结果实例
        success: 是否成功
        interface_task_result_id: 任务执行结果ID（可选）
    """
    await InterfaceContentStepResultMapper.insert_result(
        content_type=CaseStepContentType.STEP_API,
        case_result_id=interface_case_result_id,
        task_result_id=interface_task_result_id,
        content_id=step_content.id,
        content_name=step_content.resolved_content_name,
        content_desc=step_content.content_desc,
        content_step=step_index,
        result=success,
        status="SUCCESS" if success else "FAIL",
        start_time=interface_result.start_time,
        use_time=interface_result.use_time,
        interface_result_id=interface_result.id,
    )
