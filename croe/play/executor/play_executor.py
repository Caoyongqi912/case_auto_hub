#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : play_executor
# @Software: PyCharm
# @Desc:

from typing import Optional, Tuple

from playwright.async_api import Page

from croe.play.context import StepContext
from croe.play.executor.locator import get_locator
from croe.play.executor.play_method import method_chain
from utils import log


class PlayExecutor:
    """ui 步骤执行"""

    @classmethod
    async def execute(cls, step_context: StepContext) -> Tuple[bool, Optional[str]]:
        """
        UI 执行
        """
        try:
            locator = await get_locator(step_context)
            # 如果操作打开了新页面、返回新页面的page 进行后续操作
            if step_context.step.new_page:
                async with step_context.page.expect_popup() as p:
                    SUCCESS, MESSAGE = await method_chain.handle(locator=locator, context=step_context)
                    page = await p.value
                    log.info(f"[PlayExecutor] New page detected: {page.url}")
                    # 如果有页面管理器，设置新页面为当前活动页面
                    if step_context.page_manager:
                        step_context.page_manager.set_page(page)
                        await step_context.starter.send(f"📄 切换到新页面: {page.url}")
                    return SUCCESS,MESSAGE
            SUCCESS, MESSAGE = await method_chain.handle(locator=locator, context=step_context)
            return SUCCESS,MESSAGE
        except Exception as e:
            log.error(f"[PlayExecutor] execute error: {e}")
            return False, str(e)
