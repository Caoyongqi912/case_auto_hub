#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : play_step_content
# @Software: PyCharm
# @Desc:
import datetime


from app.mapper.play import PlayStepV2Mapper
from ._base import StepBaseStrategy
from croe.play.context import StepContentContext, StepContext


class PlayStepContentStrategy(StepBaseStrategy):
    """
    ui 单步骤执行
    """

    async def execute(self, step_content: StepContentContext) -> bool:
        """
        UI 步骤 执行
        Args:
            step_content:StepContentContext
        Return:
            SUCCESS:bool
        """
        step = await PlayStepV2Mapper.get_by_id(step_content.play_step_content.target_id)
        step_context = StepContext(
            step=step,
            page_manager=step_content.page_manager,
            starter=step_content.starter,
            variable_manager=step_content.variable_manager

        )

        start_time = datetime.datetime.now()
        result = await self.play_executor.execute(
            step_context
        )
        SUCCESS = result.success
        IS_IGNORE = False
        # 定制 忽略错误
        if step_context.step.is_ignore and not SUCCESS:
            await step_context.starter.send(f"忽略错误 ⚠️⚠️")
            IS_IGNORE = True
            result.success = True
            SUCCESS = True

        await self.write_result(
            result=result,
            start_time=start_time,
            step_context=step_content,
            ignore=IS_IGNORE
        )
        return SUCCESS

