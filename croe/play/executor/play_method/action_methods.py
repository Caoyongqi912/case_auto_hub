#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : action_methods
# @Software: PyCharm
# @Desc: https://playwright.dev/python/docs/api/class-locator#locator-all

from typing import Optional

from playwright.async_api import Locator, TimeoutError

from croe.play.context import StepContext
from utils import log
from ._base_method import BaseMethods
from .result_types import InfoDict, create_error_info, create_success_result, create_error_result, StepExecutionResult


class ClickMethod(BaseMethods):
    """点击元素"""
    method_name = "click"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await locator.click()
            await context.log(f"点击元素 ✅ : {context.selector}")
            return create_success_result(message=f"点击元素成功: {context.selector}")
        except TimeoutError as e:
            # 返回超时错误
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"点击操作失败 ❌: {str(e)}")
            # 返回交互失败错
            return create_error_result(
                error_type="interaction_failed",
                message=f"点击操作失败: {str(e)}",
                selector=context.selector
            )


class DblclickMethod(BaseMethods):
    """双击元素"""
    method_name = "dblclick"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await locator.dblclick()
            await context.log(f"双击元素 ✅ : {context.selector}")
            return create_success_result(message=f"双击元素成功: {context.selector}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"双击操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"双击操作失败: {str(e)}",
                selector=context.selector
            )


class CheckMethod(BaseMethods):
    """勾选复选框"""
    method_name = "check"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await locator.check()
            await context.log(f"勾选复选框 ✅ : {context.selector}")
            return create_success_result(message=f"勾选复选框成功: {context.selector}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"勾选操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"勾选操作失败: {str(e)}",
                selector=context.selector
            )


class UncheckMethod(BaseMethods):
    """取消勾选复选框"""
    method_name = "uncheck"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await locator.uncheck()
            await context.log(f"取消勾选 ✅ : {context.selector}")
            return create_success_result(message=f"取消勾选成功: {context.selector}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"取消勾选操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"取消勾选操作失败: {str(e)}",
                selector=context.selector
            )


class ClearMethod(BaseMethods):
    """清空输入框"""
    method_name = "clear"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await locator.clear()
            await context.log(f"清空输入框 ✅ : {context.selector}")
            return create_success_result(message=f"清空输入框成功: {context.selector}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"清空操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"清空操作失败: {str(e)}",
                selector=context.selector
            )


class FillMethod(BaseMethods):
    """填充输入框（清空后填充）"""
    method_name = "fill"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            value = await context.variable_manager.trans(context.value.strip())
            await locator.fill(value=value)
            await context.log(f"填充输入 ✅ : {context.selector} = {value}")
            return create_success_result(message=f"填充输入成功: {context.selector} = {value}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"填充操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"填充操作失败: {str(e)}",
                selector=context.selector
            )


class TypeMethod(BaseMethods):
    """输入文本（不清空，追加输入）"""
    method_name = "type"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            value = await context.variable_manager.trans(context.value.strip())
            await locator.type(value)
            await context.log(f"输入文本 ✅ : {context.selector} = {value}")
            return create_success_result(message=f"输入文本成功: {context.selector} = {value}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"输入文本操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"输入文本操作失败: {str(e)}",
                selector=context.selector
            )


class FocusMethod(BaseMethods):
    """聚焦元素"""
    method_name = "focus"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await locator.focus()
            await context.log(f"聚焦元素 ✅ : {context.selector}")
            return create_success_result(message=f"聚焦元素成功: {context.selector}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"聚焦操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"聚焦操作失败: {str(e)}",
                selector=context.selector
            )


class BlurMethod(BaseMethods):
    """失焦元素"""
    method_name = "blur"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await locator.blur()
            await context.log(f"失焦元素 ✅ : {context.selector}")
            return create_success_result(message=f"失焦元素成功: {context.selector}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"失焦操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"失焦操作失败: {str(e)}",
                selector=context.selector
            )


class HoverMethod(BaseMethods):
    """悬停元素"""
    method_name = "hover"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await locator.hover()
            await context.log(f"悬停元素 ✅ : {context.selector}")
            return create_success_result(message=f"悬停元素成功: {context.selector}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"悬停操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"悬停操作失败: {str(e)}",
                selector=context.selector
            )


class PressMethod(BaseMethods):
    """按键操作"""
    method_name = "press"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            key = await context.variable_manager.trans(context.value.strip())
            await locator.press(key)
            await context.log(f"按键 ✅ : {key}")
            return create_success_result(message=f"按键操作成功: {key}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"按键操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"按键操作失败: {str(e)}",
                selector=context.selector
            )


class SelectOptionLabelMethod(BaseMethods):
    """通过标签选择下拉选项"""
    method_name = "select_option_label"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            value = await context.variable_manager.trans(context.value.strip())
            await locator.select_option(label=value)
            await context.log(f"选择选项(标签) ✅ : {context.selector} = {value}")
            return create_success_result(message=f"选择选项(标签)成功: {context.selector} = {value}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"选择选项操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"选择选项操作失败: {str(e)}",
                selector=context.selector
            )


class SelectOptionValueMethod(BaseMethods):
    """通过值选择下拉选项"""
    method_name = "select_option_value"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            value = await context.variable_manager.trans(context.value.strip())
            await locator.select_option(value=value)
            await context.log(f"选择选项(值) ✅ : {context.selector} = {value}")
            return create_success_result(message=f"选择选项(值)成功: {context.selector} = {value}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"选择选项操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"选择选项操作失败: {str(e)}",
                selector=context.selector
            )


class SelectOptionValuesMethod(BaseMethods):
    """通过多个值选择下拉选项"""
    method_name = "select_option_values"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            value = await context.variable_manager.trans(context.value)
            values = [v.strip() for v in value.split(",")]
            await locator.select_option(value=values)
            await context.log(f"选择多个选项 ✅ : {context.selector} = {values}")
            return create_success_result(message=f"选择多个选项成功: {context.selector} = {values}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"选择多个选项操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"选择多个选项操作失败: {str(e)}",
                selector=context.selector
            )


class SetCheckedMethod(BaseMethods):
    """设置为勾选状态"""
    method_name = "set_checked"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await locator.set_checked(True)
            await context.log(f"设置勾选 ✅ : {context.selector}")
            return create_success_result(message=f"设置勾选成功: {context.selector}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"设置勾选操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"设置勾选操作失败: {str(e)}",
                selector=context.selector
            )


class SetUncheckedMethod(BaseMethods):
    """设置为未勾选状态"""
    method_name = "set_unchecked"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            await locator.set_checked(False)
            await context.log(f"设置未勾选 ✅ : {context.selector}")
            return create_success_result(message=f"设置未勾选成功: {context.selector}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"设置未勾选操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"设置未勾选操作失败: {str(e)}",
                selector=context.selector
            )


class UploadMethod(BaseMethods):
    """上传文件"""
    method_name = "upload"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            from .upload_files import xlsx, png
            if context.value == "xlsx":
                await locator.set_input_files(xlsx)
            else:
                await locator.set_input_files(png)
            await context.log(f"上传文件 ✅")
            return create_success_result(message=f"上传文件成功: {context.value}")
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"上传文件操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="interaction_failed",
                message=f"上传文件操作失败: {str(e)}",
                selector=context.selector
            )


class CountMethod(BaseMethods):
    """获取元素数量"""
    method_name = "count"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            key = context.key
            count = await locator.count()
            await context.variable_manager.add_var(key, str(count))
            await context.log(f"提取数量 ✅ : {key} = {count}")
            return create_success_result(
                message=f"提取数量成功: {key} = {count}",
                extract_data={
                    "variable_name": key,
                    "extracted_value": str(count),
                }
            )
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"提取数量操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="unknown",
                message=f"提取数量操作失败: {str(e)}",
                selector=context.selector
            )


class GetAttributeMethod(BaseMethods):
    """获取元素属性"""
    method_name = "get_attribute"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            key = context.key
            attr_name = context.value
            value = await locator.get_attribute(name=attr_name)

            if value is None:
                log.warning(f"[GetAttributeMethod] attribute '{attr_name}' not found")
                value = ""

            await context.variable_manager.add_var(key, value)
            await context.log(f"提取属性 ✅ : {key} = {value}")
            return create_success_result(
                message=f"提取属性成功: {key} = {value}",
                extract_data={
                    "variable_name": key,
                    "extracted_value": value,
                }
            )
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"提取属性操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="unknown",
                message=f"提取属性操作失败: {str(e)}",
                selector=context.selector
            )


class GetInnerTextMethod(BaseMethods):
    """获取元素内部文本"""
    method_name = "get_inner_text"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            key = context.key
            value = await locator.inner_text()
            await context.variable_manager.add_var(key, value)
            await context.log(f"提取文本 ✅ : {key} = {value}")
            return create_success_result(
                message=f"提取文本成功: {key} = {value}",
                extract_data={
                    "variable_name": key,
                    "extracted_value": value,
                }
            )
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"提取文本操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="unknown",
                message=f"提取文本操作失败: {str(e)}",
                selector=context.selector
            )


class GetInputValueMethod(BaseMethods):
    """获取输入框的值"""
    method_name = "get_input_value"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            key = context.key
            value = await locator.input_value()
            await context.variable_manager.add_var(key, value.strip())
            await context.log(f"提取值 ✅ : {key} = {value}")
            return create_success_result(
                message=f"提取值成功: {key} = {value}",
                extract_data={
                    "variable_name": key,
                    "extracted_value": value.strip(),
                }
            )
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"提取值操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="unknown",
                message=f"提取值操作失败: {str(e)}",
                selector=context.selector
            )


class GetTextContentMethod(BaseMethods):
    """获取元素文本内容"""
    method_name = "get_text_content"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            key = context.key
            value = await locator.text_content()
            if value:
                value = value
            else:
                value = ""
            await context.variable_manager.add_var(key, value)
            await context.log(f"提取文本内容 ✅ : {key} = {value}")
            return create_success_result(
                message=f"提取文本内容成功: {key} = {value}",
                extract_data={
                    "variable_name": key,
                    "extracted_value": value,
                }
            )
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"提取文本内容操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="unknown",
                message=f"提取文本内容操作失败: {str(e)}",
                selector=context.selector
            )


class EvaluateMethod(BaseMethods):
    """执行 JavaScript 表达式"""
    method_name = "evaluate"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        try:
            script = await context.variable_manager.trans(context.value.strip())
            result = await locator.evaluate(script)
            await context.log(f"执行脚本 ✅ : {script}")

            if result is not None:
                log.info(f"[EvaluateMethod] result: {result}")

            return create_success_result(
                message=f"执行脚本成功: {script}",

            )
        except TimeoutError as e:
            await context.log(f"元素定位超时 ❌: {str(e)}")
            return create_error_result(
                error_type="timeout",
                message=f"元素定位超时: {str(e)}",
                selector=context.selector
            )
        except Exception as e:
            await context.log(f"执行脚本操作失败 ❌: {str(e)}")
            return create_error_result(
                error_type="unknown",
                message=f"执行脚本操作失败: {str(e)}",
                selector=context.selector
            )


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
