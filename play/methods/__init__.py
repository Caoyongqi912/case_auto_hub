import re
from typing import Dict, Type, Any

from playwright.async_api import Page, Locator, expect
from abc import ABC, abstractmethod
from app.model.playUI import PlayStep, PlayCaseResult
from play.starter import UIStarter
from play.upload_files import png, xlsx
from play.writer import Writer
from utils import MyLoguru, GenerateTools
from utils.variableTrans import VariableTrans

log = MyLoguru().get_logger()
expect.set_options(timeout=1000)


class _MethodHandler(ABC):

    @abstractmethod
    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):
        pass


class GetAttrHandler(_MethodHandler):
    """
    获取locator上的属性
    name;attr => key:value
    """

    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):

        try:
            try:
                key, attr_name = play_step.fill_value.split(";")
            except Exception:
                await starter.send(f"提取变量格式错误  ⚠️ :{play_step.fill_value}")
                raise Exception(f"提取变量格式错误 ⚠️ :{play_step.fill_value}")
            locator = await get_locator(page, play_step)
            attr = await locator.get_attribute(attr_name)
            if attr:
                tempVariable = {
                    key: attr.strip()
                }
                await starter.send(f"提取变量 ✅ {tempVariable}")
                await vt.add_var(key=key, value=attr.strip())
                await Writer.write_vars_info(case_result=case_result, extract_method=play_step.method,
                                             step_name=play_step.name, varsInfo=tempVariable)
        except Exception as e:
            raise e


class GetTextHandler(_MethodHandler):
    """
    获取locator上的文案 存入变量
    """

    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):

        try:
            locator = await get_locator(page, play_step)
            text = await locator.inner_text()
            tempVariable = {
                play_step.fill_value.strip(): text.strip()
            }
            await starter.send(f"提取变量 ✅ {tempVariable}")
            await vt.add_var(key=play_step.fill_value.strip(), value=text.strip())
            await Writer.write_vars_info(case_result=case_result, extract_method=play_step.method,
                                         step_name=play_step.name, varsInfo=tempVariable)

        except Exception as e:
            raise e


class GOTOHandler(_MethodHandler):
    """
    跳转
    """

    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):

        try:

            url = await vt.trans(play_step.fill_value)
            await starter.send(f"执行 >> 打开地址:\"{url}\"")
            await page.goto(url, wait_until="load")
            # await page.wait_for_load_state()
        except Exception as e:
            log.error(f"An error occurred: {e}")
            raise e


class WaitHandler(_MethodHandler):
    """
    等待
    """

    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):
        try:
            await page.wait_for_timeout(float(play_step.fill_value))
            await starter.send(f"wait_for_timeout  {play_step.fill_value} done")
        except Exception as e:
            raise e


class EvaluateHandler(_MethodHandler):
    """
    执行js
    """

    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):
        try:

            result = await page.evaluate(play_step.fill_value)
            await starter.send(f">> evaluate:  \"{play_step.fill_value}\" result: {result}")
        except Exception as e:
            raise e


class FillHandler(_MethodHandler):
    """
    填充
    """

    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):
        try:
            locator = await get_locator(page, play_step)
            fill_value = await vt.trans(play_step.fill_value)
            await starter.send(f"输入 >> \"{fill_value}\"")
            await locator.fill(str(fill_value).strip())
        except Exception as e:
            raise e


class UploadHandler(_MethodHandler):
    """
    上传文件
    """

    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):
        try:
            locator = await get_locator(page, play_step)
            if play_step.fill_value == "xlsx":
                await locator.set_input_files(xlsx)
            else:
                await locator.set_input_files(png)
            await starter.send("上传附件 ✅")
        except Exception as e:
            raise e


class PlayClickHandler(_MethodHandler):
    """点击"""

    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):
        try:
            locator = await get_locator(page, play_step)
            await locator.click()
        except Exception as e:
            raise e


class PlayDBClickHandler(_MethodHandler):
    """点击"""

    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):
        try:
            locator = await get_locator(page, play_step)
            await locator.dblclick()
        except Exception as e:
            raise e


class PlayPressKeyHandler(_MethodHandler):
    """
    键盘模拟输入
    """

    async def handle(self, page: Page, play_step: PlayStep, starter: UIStarter, case_result: PlayCaseResult,
                     vt: VariableTrans):
        try:
            await starter.send(f"use keyboard press \"{play_step.fill_value.strip()}\"")
            await page.keyboard.press(play_step.fill_value.strip())
        except Exception as e:
            raise e


class PlayAssertToHaveText(_MethodHandler):
    """
    断言有文案
    """

    async def handle(self, page: Page,
                     play_step: PlayStep,
                     starter: UIStarter,
                     vt: VariableTrans,
                     case_result: PlayCaseResult):
        assert_info = set_assert_info(play_step=play_step, opt="=", expect_value=play_step.fill_value)
        try:
            locator = await get_locator(page, play_step)
            await expect(locator).to_have_text(play_step.fill_value,
                                               use_inner_text=True)
            assert_info["assert_actual"] = await locator.inner_text()
            assert_info["assert_result"] = True
        except AssertionError as e:
            assert_info["assert_actual"] = await get_error_value(e)
            raise
        finally:
            await Writer.write_assert_info(case_result, [assert_info])


class PlayAssertToBeAttachedAndVisible(_MethodHandler):
    """
    确认元素存在并可视
    """

    async def handle(self, page: Page,
                     play_step: PlayStep,
                     starter: UIStarter,
                     vt: VariableTrans,
                     case_result: PlayCaseResult):
        assert_info = set_assert_info(play_step=play_step, opt="=", expect_value=True)
        try:
            locator = await get_locator(page, play_step)
            await expect(locator).to_be_attached(attached=True)
            await expect(locator).to_be_visible()
            assert_info["assert_actual"] = True
            assert_info["assert_result"] = True
        except AssertionError:
            assert_info["assert_actual"] = False
            raise
        finally:
            await Writer.write_assert_info(case_result, [assert_info])


class PlayAssertNotToBeAttachedAndVisible(_MethodHandler):
    """
    确认元素不存
    """

    async def handle(self, page: Page,
                     play_step: PlayStep,
                     starter: UIStarter,
                     vt: VariableTrans,
                     case_result: PlayCaseResult):
        assert_info = set_assert_info(play_step=play_step, opt="!=", expect_value=False)
        try:
            locator = await get_locator(page, play_step)
            await expect(locator).not_to_be_attached(attached=False)
            assert_info["assert_actual"] = False
            assert_info["assert_result"] = True
        except AssertionError:
            assert_info["assert_actual"] = False
            raise
        finally:
            await Writer.write_assert_info(case_result, [assert_info])


class PlayAssertToHaveAttribute(_MethodHandler):
    """
    断言属性
    """

    async def handle(self, page: Page,
                     play_step: PlayStep,
                     starter: UIStarter,
                     vt: VariableTrans,
                     case_result: PlayCaseResult):
        key, attr = play_step.fill_value.split(":")
        assert_info = set_assert_info(play_step=play_step, opt="=", expect_value=attr)
        try:
            locator = await get_locator(page, play_step)
            await expect(locator).to_have_attribute(key, attr)
            assert_info["assert_actual"] = await locator.get_attribute(key)
            assert_info["assert_result"] = True
        except AssertionError:
            assert_info["assert_actual"] = None
            raise
        finally:
            await Writer.write_assert_info(case_result, [assert_info])


class PlayAssertNotToHaveAttribute(_MethodHandler):
    """
    断言属性
    """

    async def handle(self, page: Page,
                     play_step: PlayStep,
                     starter: UIStarter,
                     vt: VariableTrans,
                     case_result: PlayCaseResult):
        key, attr = play_step.fill_value.split(":")
        assert_info = set_assert_info(play_step=play_step, opt="!=", expect_value=attr)
        try:
            locator = await get_locator(page, play_step)
            await expect(locator).not_to_have_attribute(key, attr)
            assert_info["assert_actual"] = await locator.get_attribute(key)
            assert_info["assert_result"] = True
        except AssertionError:
            assert_info["assert_actual"] = None
            raise
        finally:
            await Writer.write_assert_info(case_result, [assert_info])


class PlayAssertToHaveTitle(_MethodHandler):
    """
    断言标题
    """

    async def handle(self, page: Page,
                     play_step: PlayStep,
                     starter: UIStarter,
                     vt: VariableTrans,
                     case_result: PlayCaseResult):

        assert_info = set_assert_info(play_step=play_step, opt="=", expect_value=play_step.fill_value)
        try:
            await expect(page).to_have_title(play_step.fill_value)
            assert_info["assert_actual"] = await page.title()
            assert_info["assert_result"] = True
        except AssertionError as e:
            assert_info["assert_actual"] = await get_error_value(e)
            raise
        finally:
            await Writer.write_assert_info(case_result, [assert_info])


class PlayAssertToHaveURL(_MethodHandler):
    """
    断言路由
    """

    async def handle(self, page: Page,
                     play_step: PlayStep,
                     starter: UIStarter,
                     vt: VariableTrans,
                     case_result: PlayCaseResult):

        assert_info = set_assert_info(play_step=play_step, opt="=", expect_value=play_step.fill_value)
        try:
            await expect(page).to_have_url(play_step.fill_value)
            assert_info["assert_actual"] = page.url
            assert_info["assert_result"] = True
        except AssertionError as e:
            assert_info["assert_actual"] = await get_error_value(e)
            raise
        finally:
            await Writer.write_assert_info(case_result, [assert_info])


class CustomizeMethod:
    handlers: Dict[str, Type[_MethodHandler]] = {
        "play_get_attr": GetAttrHandler,
        "play_get_text": GetTextHandler,
        "play_go_to": GOTOHandler,
        "play_wait": WaitHandler,
        "play_evaluate": EvaluateHandler,
        "play_fill": FillHandler,
        "play_upload": UploadHandler,
        "play_click": PlayClickHandler,
        "play_dblclick": PlayDBClickHandler,
        "play_press_key": PlayPressKeyHandler,
        "expect.play_to_have_text": PlayAssertToHaveText,
        "expect.play_to_have_title": PlayAssertToHaveTitle,
        "expect.play_to_have_url": PlayAssertToHaveURL,
        "expect.play_to_have_attr": PlayAssertToHaveAttribute,
        "expect.play_to_attached_and_visible": PlayAssertToBeAttachedAndVisible,
        "expect.play_not_to_attached": PlayAssertNotToBeAttachedAndVisible,
        "expect.play_not_to_have_attr": PlayAssertNotToHaveAttribute,

    }

    @classmethod
    async def play(cls, page: Page, play_step: PlayStep, starter: UIStarter, vt: VariableTrans,
                   play_result: PlayCaseResult = None):
        """执行方法"""
        handler_class = cls.handlers.get(play_step.method)
        if not handler_class:
            raise ValueError(f"Unknown method: {play_step.method}")

        handler = handler_class()
        await handler.handle(page=page, play_step=play_step, starter=starter, vt=vt, case_result=play_result)


async def get_locator(page: Page, play_step: PlayStep) -> Locator:
    """
    获取 page locator
    区分是否在iframe上
    并滚动到对应元素
    :param page: Page
    :param play_step: 步骤
    :return: Locator
    """

    try:
        if play_step.iframe_name:
            element_locator = page.frame_locator(play_step.iframe_name).locator(play_step.locator)
        else:
            element_locator = page.locator(play_step.locator)
        await element_locator.scroll_into_view_if_needed()
        return element_locator
    except Exception as e:
        raise e


async def new_page(page: Page, play_step: PlayStep, starter: UIStarter, vt: VariableTrans) -> Page:
    """
    actions On New Page
    1、点击 a[target="_blank"]
    2、点击后 windows.open
    :return: new page
    """
    try:
        async with page.expect_popup() as p:
            # 执行方法
            await CustomizeMethod.play(page=page,
                                       play_step=play_step,
                                       starter=starter,
                                       vt=vt
                                       )
        return await p.value
    except Exception as e:
        log.error(e)
        raise e


async def get_error_value(e: AssertionError):
    err = str(e)
    if "Actual value:" in err:
        # 正则表达式匹配 Actual value 和 Call log 之间的内容
        pattern = r"Actual value:\s*(.*?)\s*Call log:"
        match = re.search(pattern, err, re.DOTALL)
        if match:
            actual_value = match.group(1).strip()
            return actual_value
        else:
            return ""
    return ""


def set_assert_info(play_step: PlayStep, opt: str, expect_value: Any) -> Dict[str, Any]:
    return {
        "id": GenerateTools.getTime(3),
        "desc": play_step.description,
        "type": "UI",
        "assert_name": play_step.name,
        "assert_opt": opt,
        "assert_script": play_step.method,
        "assert_expect": expect_value,
        "assert_actual": None,
        "assert_result": False
    }


__all__ = [
    "CustomizeMethod",
    "get_locator",
    "new_page",
]
