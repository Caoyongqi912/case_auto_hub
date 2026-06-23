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
# (原模块级单例写入的 cache 永远不会被 flush, 案例拿不到数据)
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

        interface_result = await self.interface_executor.execute(
            interface=interface,
            env=step_context.execution_context.env
        )
        success = interface_result.result

        log.info(f"api step interface_result {interface_result}")
        interface_result = await step_context.result_writer.write_interface_result(
            interface_result=interface_result,
            immediate=True
        )
        log.info(f"api step interface_result {interface_result}")
        task_result_id = None
        if step_context.execution_context.task_result:
            task_result_id = step_context.execution_context.task_result.id

        # 子步骤立即插入，获取 id 后回填 interface_result.content_result_id
        content_result = await step_context.result_writer.write_step_result(
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
            immediate=True,  # 立即插入以获取 id 回填 FK
        )
        if content_result is not None and content_result.id is not None:
            # 回填 interface_result.content_result_id
            try:
                await InterfaceResultMapper.update_by_id(
                    id=interface_result.id,
                    content_result_id=content_result.id,
                )
            except Exception as e:
                log.warning(
                    f"回填 interface_result.content_result_id 失败 "
                    f"(interface_result_id={interface_result.id}, "
                    f"content_result_id={content_result.id}): {e}"
                )

        await self._record_step_outcome(step_context, success)

        return success
