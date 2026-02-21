from typing import Optional

from playwright.async_api import Locator, TimeoutError as PlaywrightTimeoutError

from croe.play.context import StepContext
from utils import log
from ._base_method import BaseMethods
from .result_types import  create_success_result, create_error_result, StepExecutionResult


class GotoMethod(BaseMethods):
    """
    page goto
    """
    method_name = "goto"
    requires_locator: bool = False

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        url = ""
        try:
            page = context.page
            url = await context.variable_manager.trans(context.step.value)
            await page.goto(url)
            message = f"跳转页面 ✅ : {url}"
            await context.log(message)
            return create_success_result(message)
        except PlaywrightTimeoutError as e:
            log.error(f"timeout {e}")
            # 返回超时错误
            return create_error_result(
                error_type="timeout",
                message=f"页面{url}加载超时: {str(e)} ",
            )
        except Exception as e:
            log.error(f"error {e}")
            # 返回交互失败错误
            return create_error_result(
                error_type="interaction_failed",
                message=f"页面{url}加载失败: {str(e)}",
                selector=context.selector
            )


class ReloadMethod(BaseMethods):
    """
    page reload
    """
    method_name = "reload"
    requires_locator: bool = False

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await context.page.reload()
            await context.log("刷新页面 ✅")
            return create_success_result(f"刷新页面 ✅")
        except PlaywrightTimeoutError as e:
            await context.starter.send(f"[ReloadMethod] 页面刷新超时: {e}")
            return create_error_result(
                error_type="timeout",
                message=f"页面刷新超时: {str(e)} ",
            )
        except Exception as e:
            await context.starter.send(f"[ReloadMethod] reload error: {e}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"页面刷新失败: {str(e)} ",
            )


class BackMethod(BaseMethods):
    """
    page back
    """
    method_name = "back"
    requires_locator: bool = False

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await context.page.go_back()
            await context.starter.send("返回上一页 ✅")
            return create_success_result(f"返回上一页 ✅")
        except PlaywrightTimeoutError as e:
            await context.starter.send(f"[BackMethod] 页面返回超时: {e}")
            return create_error_result(
                error_type="timeout",
                message=f"页面返回超时: {str(e)} ",
            )
        except Exception as e:
            await context.starter.send(f"[BackMethod] back error: {e}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"页面返回失败: {str(e)} ",
            )


class ForwardMethod(BaseMethods):
    """
    page forward
    """
    method_name = "forward"
    requires_locator: bool = False

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await context.page.go_forward()
            await context.starter.send("前进下一页 ✅")
            return create_success_result(f"前进下一页 ✅")
        except PlaywrightTimeoutError as e:
            await context.starter.send(f"[ForwardMethod] 页面前进超时: {e}")
            return create_error_result(
                error_type="timeout",
                message=f"页面前进超时: {str(e)} ",
            )
        except Exception as e:
            await context.starter.send(f"[ForwardMethod] forward error: {e}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"页面前进失败: {str(e)} ",
            )


class WaitMethod(BaseMethods):
    """
    page wait
    """
    method_name = "wait"
    requires_locator: bool = False

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            try:
                wait_time = int(context.step.value)
            except ValueError:
                wait_time = 0
            await context.page.wait_for_timeout(wait_time)
            await context.starter.send(f"等待 ✅ : {wait_time}ms")
            return create_success_result(f"等待 ✅ : {wait_time}ms")
        except Exception as e:
            await context.starter.send(f"[WaitMethod] wait error: {e}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"等待失败: {str(e)} ",
            )
