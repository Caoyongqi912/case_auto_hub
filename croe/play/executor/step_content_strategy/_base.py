#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : _base
# @Software: PyCharm
# @Desc:
import datetime
import os
from abc import ABC, abstractmethod

from app.model.playUI.PlayResult import PlayStepContentResult
from config import Config
from croe.play.context import StepContentContext
from croe.play.executor import PlayExecutor
from croe.play.executor.play_method.result_types import StepExecutionResult
from enums.CaseEnum import PlayStepContentType
from utils import GenerateTools


class StepBaseStrategy(ABC):
    """
    步骤执行策略基类
    """

    def __init__(self):
        self.play_executor = PlayExecutor()

    @abstractmethod
    async def execute(self, step_context: StepContentContext) -> bool:
        """执行步骤，返回是否成功"""
        ...

    async def write_result(
            self,
            result: StepExecutionResult,
            start_time: datetime.datetime,
            step_content: StepContentContext,
            ignore: bool = False,
    ):
        """
        暂存结果
        - 变量
        - 断言
        - 截图
        """
        content_result = await self._build_content_result(
            result=result,
            start_time=start_time,
            step_content=step_content,
            ignore=ignore,
        )
        await step_content.play_step_result_writer.add_content_result(
            step_index=step_content.index,
            content_result=content_result
        )

    async def write_child_result(
            self,
            parent_index: int,
            result: StepExecutionResult,
            start_time: datetime.datetime,
            step_content: StepContentContext,
            ignore: bool = False,
    ):
        """
        写入子步骤
        """
        content_result = await self._build_content_result(
            result=result,
            start_time=start_time,
            step_content=step_content,
            ignore=ignore,
        )
        await step_content.play_step_result_writer.add_child_content_result(
            parent_index=parent_index,
            content_result=content_result
        )

    async def _build_content_result(
            self,
            result: StepExecutionResult,
            start_time: datetime.datetime,
            step_content: StepContentContext,
            ignore: bool = False,
    ) -> PlayStepContentResult:
        """
        构建内容结果对象（复用逻辑）
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
        
        # 截图
        if not result.success and step_content.play_step_content.content_type == PlayStepContentType.STEP_PLAY:
            path = await self.to_screenshot(step_content)
            if path:
                content_result.content_screenshot_path = path
        
        return content_result
        

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
