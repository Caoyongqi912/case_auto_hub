#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : action_methods
# @Software: PyCharm
# @Desc: https://playwright.dev/python/docs/api/class-locator#locator-all

from typing import Optional

from playwright.async_api import Locator, TimeoutError as PlaywrightTimeoutError

from croe.play.context import StepContext
from utils import log
from ._base_method import BaseMethods
from .result_types import InfoDict, create_error_info


class ClickMethod(BaseMethods):
    """点击元素"""
    method_name = "click"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.click()
            await context.log(f"点击元素 ✅ : {context.selector}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[ClickMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[ClickMethod] click error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class DblclickMethod(BaseMethods):
    """双击元素"""
    method_name = "dblclick"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.dblclick()
            await context.log(f"双击元素 ✅ : {context.selector}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[DblclickMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[DblclickMethod] dblclick error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class CheckMethod(BaseMethods):
    """勾选复选框"""
    method_name = "check"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.check()
            await context.log(f"勾选复选框 ✅ : {context.selector}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[CheckMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[CheckMethod] check error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class UncheckMethod(BaseMethods):
    """取消勾选复选框"""
    method_name = "uncheck"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.uncheck()
            await context.log(f"取消勾选 ✅ : {context.selector}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[UncheckMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[UncheckMethod] uncheck error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class ClearMethod(BaseMethods):
    """清空输入框"""
    method_name = "clear"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.clear()
            await context.log(f"清空输入框 ✅ : {context.selector}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[ClearMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[ClearMethod] clear error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class FillMethod(BaseMethods):
    """填充输入框（清空后填充）"""
    method_name = "fill"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            value = await context.variable_manager.trans(context.value.strip())
            await locator.fill(value=value)
            await context.log(f"填充输入 ✅ : {context.selector} = {value}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[FillMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[FillMethod] fill error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class TypeMethod(BaseMethods):
    """输入文本（不清空，追加输入）"""
    method_name = "type"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            value = await context.variable_manager.trans(context.value.strip())
            await locator.type(value)
            await context.log(f"输入文本 ✅ : {context.selector} = {value}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[TypeMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[TypeMethod] type error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class FocusMethod(BaseMethods):
    """聚焦元素"""
    method_name = "focus"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.focus()
            await context.log(f"聚焦元素 ✅ : {context.selector}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[FocusMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[FocusMethod] focus error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class BlurMethod(BaseMethods):
    """失焦元素"""
    method_name = "blur"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.blur()
            await context.log(f"失焦元素 ✅ : {context.selector}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[BlurMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[BlurMethod] blur error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class HoverMethod(BaseMethods):
    """悬停元素"""
    method_name = "hover"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.hover()
            await context.log(f"悬停元素 ✅ : {context.selector}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[HoverMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[HoverMethod] hover error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class PressMethod(BaseMethods):
    """按键操作"""
    method_name = "press"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            key = await context.variable_manager.trans(context.value.strip())
            await locator.press(key)
            await context.log(f"按键 ✅ : {key}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[PressMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[PressMethod] press error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class SelectOptionLabelMethod(BaseMethods):
    """通过标签选择下拉选项"""
    method_name = "select_option_label"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            value = await context.variable_manager.trans(context.value.strip())
            await locator.select_option(label=value)
            await context.log(f"选择选项(标签) ✅ : {context.selector} = {value}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[SelectOptionLabelMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[SelectOptionLabelMethod] select option error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class SelectOptionValueMethod(BaseMethods):
    """通过值选择下拉选项"""
    method_name = "select_option_value"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            value = await context.variable_manager.trans(context.value.strip())
            await locator.select_option(value=value)
            await context.log(f"选择选项(值) ✅ : {context.selector} = {value}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[SelectOptionValueMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[SelectOptionValueMethod] select option error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class SelectOptionValuesMethod(BaseMethods):
    """通过多个值选择下拉选项"""
    method_name = "select_option_values"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            value = await context.variable_manager.trans(context.value)
            values = [v.strip() for v in value.split(",")]
            await locator.select_option(value=values)
            await context.log(f"选择多个选项 ✅ : {context.selector} = {values}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[SelectOptionValuesMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[SelectOptionValuesMethod] select options error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class SetCheckedMethod(BaseMethods):
    """设置为勾选状态"""
    method_name = "set_checked"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.set_checked(True)
            await context.log(f"设置勾选 ✅ : {context.selector}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[SetCheckedMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[SetCheckedMethod] set checked error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class SetUncheckedMethod(BaseMethods):
    """设置为未勾选状态"""
    method_name = "set_unchecked"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.set_checked(False)
            await context.log(f"设置未勾选 ✅ : {context.selector}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[SetUncheckedMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[SetUncheckedMethod] set unchecked error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class UploadMethod(BaseMethods):
    """上传文件"""
    method_name = "upload"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            from .upload_files import xlsx, png
            if context.value == "xlsx":
                await locator.set_input_files(xlsx)
            else:
                await locator.set_input_files(png)
            await context.log(f"上传文件 ✅")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[UploadMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[UploadMethod] upload error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)


class CountMethod(BaseMethods):
    """获取元素数量"""
    method_name = "count"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            key = context.key
            count = await locator.count()
            await context.variable_manager.add_var(key, str(count))
            await context.log(f"提取数量 ✅ : {key} = {count}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[CountMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[CountMethod] count error: {e}")
            return False, create_error_info("unknown", str(e), context.selector)


class GetAttributeMethod(BaseMethods):
    """获取元素属性"""
    method_name = "get_attribute"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            key = context.key
            attr_name = context.value
            value = await locator.get_attribute(name=attr_name)

            if value is None:
                log.warning(f"[GetAttributeMethod] attribute '{attr_name}' not found")
                value = ""

            await context.variable_manager.add_var(key, value)
            await context.log(f"提取属性 ✅ : {key} = {value}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[GetAttributeMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[GetAttributeMethod] get attribute error: {e}")
            return False, create_error_info("unknown", str(e), context.selector)


class GetInnerTextMethod(BaseMethods):
    """获取元素内部文本"""
    method_name = "get_inner_text"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            key = context.key
            value = await locator.inner_text()
            await context.variable_manager.add_var(key, value)
            await context.log(f"提取文本 ✅ : {key} = {value}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[GetInnerTextMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[GetInnerTextMethod] get inner text error: {e}")
            return False, create_error_info("unknown", str(e), context.selector)


class GetInputValueMethod(BaseMethods):
    """获取输入框的值"""
    method_name = "get_input_value"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            key = context.value
            value = await locator.input_value()
            await context.variable_manager.add_var(key, value.strip())
            await context.log(f"提取值 ✅ : {key} = {value}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[GetInputValueMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[GetInputValueMethod] get input value error: {e}")
            return False, create_error_info("unknown", str(e), context.selector)


class GetTextContentMethod(BaseMethods):
    """获取元素文本内容"""
    method_name = "get_text_content"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            key = context.value
            value = await locator.text_content()
            if value:
                value = value
            else:
                value = ""
            await context.variable_manager.add_var(key, value)
            await context.log(f"提取文本内容 ✅ : {key} = {value}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[GetTextContentMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[GetTextContentMethod] get text content error: {e}")
            return False, create_error_info("unknown", str(e), context.selector)


class EvaluateMethod(BaseMethods):
    """执行 JavaScript 表达式"""
    method_name = "evaluate"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            script = await context.variable_manager.trans(context.value.strip())
            result = await locator.evaluate(script)
            await context.log(f"执行脚本 ✅ : {script}")

            if result is not None:
                log.info(f"[EvaluateMethod] result: {result}")
            return True, None
        except PlaywrightTimeoutError as e:
            log.error(f"[EvaluateMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)
        except Exception as e:
            log.error(f"[EvaluateMethod] evaluate error: {e}")
            return False, create_error_info("unknown", str(e), context.selector)


__all__ = (
    "ClickMethod",
    "DblclickMethod",
    "CheckMethod",
    "UncheckMethod",
    "ClearMethod",
    "FillMethod",
    "TypeMethod",
    "FocusMethod",
    "BlurMethod",
    "HoverMethod",
    "PressMethod",
    "SelectOptionLabelMethod",
    "SelectOptionValueMethod",
    "SelectOptionValuesMethod",
    "SetCheckedMethod",
    "SetUncheckedMethod",
    "UploadMethod",
    "CountMethod",
    "GetAttributeMethod",
    "GetInnerTextMethod",
    "GetInputValueMethod",
    "GetTextContentMethod",
    "EvaluateMethod",
)
