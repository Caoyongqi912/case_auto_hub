#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : play_step_content
# @Software: PyCharm
# @Desc:
import datetime
import os

from config import Config

from app.mapper.play import PlayStepV2Mapper
from app.model.playUI.PlayResult import PlayStepContentResult
from ._base import StepBaseStrategy
from croe.play.context import StepContentContext, StepContext
from utils import log, GenerateTools
from ..play_method.result_types import StepExecutionResult


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
            step_content=step_content,
            ignore=IS_IGNORE
        )
        return SUCCESS

    async def write_result(
            self,
            result: StepExecutionResult,
            start_time: datetime.datetime,
            step_content: StepContentContext,
            ignore: bool = False):
        """
        暂存结果
        """
        end_time = datetime.datetime.now()
        content_result = PlayStepContentResult(
            content_step=step_content.index,
            content_id=step_content.play_step_content.id,
            content_name=step_content.play_step_content.content_name,
            content_desc=step_content.play_step_content.content_desc,
            content_type=step_content.play_step_content.content_type,
            starter_id=step_content.starter.userId,
            starter_name=step_content.starter.username,
            start_time=start_time,
            use_time=GenerateTools.timeDiff(start_time, end_time),
            content_ignore_error=ignore,
        )
        content_result.content_result = result.success
        content_result.content_message = result.message

        if result.assert_data:
            # todo
            ...

        if result.extract_data:
            content_result.extracts = result.extract_data

        if not result.success:
            path = await self.to_screenshot(step_content)
            if path:
                content_result.content_screenshot_path = path
        await step_content.play_step_result_writer.add_content_result(content_result)

    @staticmethod
    async def to_screenshot(step_content: StepContentContext):
        """
        截图
        :return:
        """
        try:
            fileDate = GenerateTools.getTime(2)
            fileName = f"{GenerateTools.uid()}.jpeg"
            local_path = os.path.join(Config.ROOT, "play", "play_error_shot", fileDate, fileName)
            # 确保目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            await step_content.page.screenshot(
                path=str(local_path),
                full_page=False,
            )
            # 返回包含static前缀的路径，前端可以通过静态文件服务访问
            await step_content.starter.send("完成失败截图✅")
            from app.mapper.file import FileMapper
            file = await FileMapper.insert_file(filePath=str(local_path), fileName=fileName)
            error_path = f"{Config.UI_ERROR_PATH}{file.uid}"

            return error_path
        except Exception as e:
            await step_content.starter.send(f"截图失败❌ {str(e)}")
            return None
