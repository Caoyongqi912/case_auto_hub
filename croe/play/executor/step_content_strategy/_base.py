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
from typing import Any

from app.model.playUI.PlayResult import PlayStepContentResult
from app.model.playUI.playStepContent import PlayStepContent
from config import Config
from croe.play.context import StepContentContext, StepContext
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
            step_context: StepContentContext,
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
            step_context=step_context,
            ignore=ignore,
        )
        await step_context.play_step_result_writer.add_content_result(
            step_index=step_context.index,
            content_result=content_result
        )

        if not result.success:
            await step_context.play_case_result_writer.set_error_step_info(content_result)



    async def write_child_result(
            self,
            parent_index: int,
            result: StepExecutionResult,
            start_time: datetime.datetime,
            step_context: StepContentContext,
            ignore: bool = False,
    ):
        """
        写入子步骤
        """
        content_result = await self._build_content_result(
            result=result,
            start_time=start_time,
            step_context=step_context,
            ignore=ignore,
        )
        await step_context.play_step_result_writer.add_child_content_result(
            parent_index=parent_index,
            content_result=content_result
        )

    async def _execute_child_step(
            self,
            step_context: StepContentContext,
            child_step: Any,
            child_step_content: PlayStepContent,
            index: int,
    ) -> StepExecutionResult:
        """
        统一执行单个子步骤并写入子结果。

        Args:
            step_context: 父步骤上下文
            child_step: 子步骤模型（PlayStepModel）
            child_step_content: 子步骤内容包装（PlayStepContent）
            index: 子步骤在父容器中的序号

        Returns:
            子步骤执行结果 StepExecutionResult
        """
        child_content_ctx = StepContentContext(
            index=index,
            play_step_content=child_step_content,
            page_manager=step_context.page_manager,
            starter=step_context.starter,
            variable_manager=step_context.variable_manager,
            play_step_result_writer=step_context.play_step_result_writer,
            play_case_result_writer=step_context.play_case_result_writer,
        )
        child_step_ctx = StepContext(
            step=child_step,
            page_manager=step_context.page_manager,
            starter=step_context.starter,
            variable_manager=step_context.variable_manager,
        )

        step_start_time = datetime.datetime.now()
        result = await self.play_executor.execute(child_step_ctx)
        await self.write_child_result(
            parent_index=step_context.index,
            result=result,
            start_time=step_start_time,
            step_context=child_content_ctx,
        )
        return result

    async def _build_content_result(
            self,
            result: StepExecutionResult,
            start_time: datetime.datetime,
            step_context: StepContentContext,
            ignore: bool = False,
    ) -> PlayStepContentResult:
        """
        构建内容结果对象（复用逻辑）
        """
        end_time = datetime.datetime.now()
        content_result = PlayStepContentResult(
            content_step=step_context.index,
            content_id=step_context.play_step_content.id,
            content_name=step_context.play_step_content.content_name,
            content_desc=step_context.play_step_content.content_desc,
            content_type=step_context.play_step_content.content_type,
            starter_id=step_context.starter.userId,
            starter_name=step_context.starter.username,
            start_time=start_time,
            use_time=GenerateTools.timeDiff(start_time, end_time),
            content_ignore_error=ignore,
            content_target_result_id=result.content_target_result_id
        )
        content_result.content_result = result.success
        content_result.content_message = result.message

        # 断言结果
        if result.assert_data:
            content_result.content_asserts = result.assert_data

        # 变量提取
        if result.extract_data:
            content_result.extracts = result.extract_data

        # 截图
        # 执行失败 && play 类型 && 不是 交互错误interaction_failed
        if not result.success and step_context.play_step_content.content_type == PlayStepContentType.STEP_PLAY and result.error_type != 'interaction_failed':
            path = await self.to_screenshot(step_context)
            if path:
                content_result.content_screenshot_path = path

        return content_result

    @staticmethod
    async def to_screenshot(step_context: StepContentContext):
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

            await step_context.page.screenshot(
                path=str(local_path),
                full_page=False,
            )
            # 返回包含static前缀的路径，前端可以通过静态文件服务访问
            await step_context.starter.send("完成失败截图✅")
            from app.mapper.file import FileMapper
            file = await FileMapper.insert_file(filePath=str(local_path), fileName=fileName)
            error_path = f"{Config.UI_ERROR_PATH}{file.uid}"

            return error_path
        except Exception as e:
            await step_context.starter.send(f"截图失败❌ {str(e)}")
            return None
