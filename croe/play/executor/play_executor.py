#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : play_executor
# @Software: PyCharm
# @Desc:
import os
from typing import Optional, Tuple

from patchright.async_api import Locator

from config import Config
from playwright.async_api import Page

from croe.play.context import StepContext
from croe.play.executor.locator import get_locator
from croe.play.executor.play_method import executor_registry
from croe.play.executor.play_method.result_types import StepExecutionResult
from utils import log, GenerateTools


class PlayExecutor:
    """ui 步骤执行"""

    @classmethod
    async def execute(cls, step_context: StepContext) -> StepExecutionResult:
        """
        UI 执行
        """

        method_name = step_context.step.method
        # 检查method_name是否有效
        if not method_name:
            error_msg = "Method name is empty"
            log.error(f"[PlayExecutor] {error_msg}")
            await step_context.starter.send(f"❌ 执行失败: {error_msg}")
            return StepExecutionResult(
                success=False,
                message=error_msg,
            )
        executor = executor_registry.get_executor(method_name)
        if not executor:
            available_methods = executor_registry.get_all_method_names()
            error_msg = f"Method '{method_name}' not found. Available methods: {', '.join(available_methods)}"
            log.error(f"[PlayExecutor] {error_msg}")
            await step_context.starter.send(f"❌ {error_msg}")
            return StepExecutionResult(
                success=False,
                message=error_msg,
            )
        locator = get_locator(step_context)
        log.info(f"[PlayExecutor] execute step: locator = {locator}, method ={step_context.step.method}")

        # 如果操作打开了新页面、返回新页面的page 进行后续操作
        if step_context.step.new_page:
            async with step_context.page.expect_popup() as p:
                result = await cls.invoke(executor, step_context, locator)
                page = await p.value
                log.info(f"[PlayExecutor] New page detected: {page.url}")
                # 如果有页面管理器，设置新页面为当前活动页面
                if step_context.page_manager:
                    step_context.page_manager.set_page(page)
                    await step_context.starter.send(f"📄 切换到新页面: {page.url}")
                return result
                # 正常执行步骤
        return await cls.invoke(executor, step_context, locator)

    @classmethod
    async def invoke(cls, executor, context: StepContext, locator: Optional[Locator]) -> StepExecutionResult:
        method_name = context.step.method
        try:
            return await executor.execute(context=context, locator=locator)
        except Exception as e:
            log.exception(f"[PlayExecutor] Error executing method '{executor}' with new page: {e}")
            error_msg = f"Execution failed for method '{method_name}': {str(e)}"
            await context.starter.send(f"❌ {error_msg}")
            return StepExecutionResult(
                success=False,
                message=error_msg,
            )
