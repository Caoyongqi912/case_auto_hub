#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : api
# @Software: PyCharm
# @Desc: API步骤执行策略


from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceResult
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.interface.writer import result_writer
from enums import InterfaceAPIResultEnum
from enums.CaseEnum import CaseStepContentType
from utils import log



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
            env=step_context.execution_context.env
        )

        log.info(f"api step step_result {step_result}")
        interface_result = await result_writer.write_interface_result(
            interface_result=InterfaceResult(**step_result),
            immediate=True
        )
        log.info(f"api step interface_result {interface_result}")
        task_result_id = None
        if step_context.execution_context.task_result:
            task_result_id = step_context.execution_context.task_result.id

        await result_writer.write_step_result(
            content_type=CaseStepContentType.STEP_API,
            case_result_id=step_context.execution_context.case_result.id,
            task_result_id=task_result_id,
            content_id=step_context.content.id,
            content_name=step_context.content.resolved_content_name,
            content_desc=step_context.content.content_desc,
            content_step=step_context.index,
            success=success,
            start_time=interface_result.start_time,
            use_time=interface_result.use_time,
            interface_result_id=interface_result.id,
        )

        case_result = step_context.execution_context.case_result
        if success:
            case_result.success_num += 1
        else:
            case_result.fail_num += 1
            case_result.result = InterfaceAPIResultEnum.ERROR

        await result_writer.update_case_progress(case_result)

        return success
