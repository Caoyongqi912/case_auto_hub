from typing import Optional

from playwright.async_api import Locator, TimeoutError as PlaywrightTimeoutError

from croe.play.context import StepContext
from utils import log
from ._base_method import BaseMethods
from .result_types import InfoDict, create_error_info


class GotoMethod(BaseMethods):
    """
    page goto
    """
    method_name = "goto"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            page = context.page
            url = await context.variable_manager.trans(context.step.value)
            await page.goto(url)
            await context.log(f"跳转页面 ✅ : {url}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[GotoMethod] 页面加载超时: {e}")
            return False, create_error_info("timeout", str(e))
        except Exception as e:
            log.error(f"[GotoMethod] goto error: {e}")
            return False, create_error_info("unknown", str(e))


class ReloadMethod(BaseMethods):
    """
    page reload
    """
    method_name = "reload"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await context.page.reload()
            await context.log("刷新页面 ✅")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[ReloadMethod] 页面刷新超时: {e}")
            return False, create_error_info("timeout", str(e))
        except Exception as e:
            log.error(f"[ReloadMethod] reload error: {e}")
            return False, create_error_info("unknown", str(e))


class BackMethod(BaseMethods):
    """
    page back
    """
    method_name = "back"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await context.page.go_back()
            await context.starter.send("返回上一页 ✅")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[BackMethod] 页面返回超时: {e}")
            return False, create_error_info("timeout", str(e))
        except Exception as e:
            log.error(f"[BackMethod] back error: {e}")
            return False, create_error_info("unknown", str(e))


class ForwardMethod(BaseMethods):
    """
    page forward
    """
    method_name = "forward"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await context.page.go_forward()
            await context.starter.send("前进下一页 ✅")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[ForwardMethod] 页面前进超时: {e}")
            return False, create_error_info("timeout", str(e))
        except Exception as e:
            log.error(f"[ForwardMethod] forward error: {e}")
            return False, create_error_info("unknown", str(e))


class WaitMethod(BaseMethods):
    """
    page wait
    """
    method_name = "wait"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            try:
                wait_time = int(context.step.value)
            except ValueError:
                wait_time = 0
            await context.page.wait_for_timeout(wait_time)
            await context.starter.send(f"等待 ✅ : {wait_time}ms")
            return True, None
        except Exception as e:
            log.error(f"[WaitMethod] wait error: {e}")
            return False, create_error_info("unknown", str(e))

