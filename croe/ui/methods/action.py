#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2026/1/29# @Author : cyq# @File : action_methods# @Software: PyCharm# @Desc:from .base import BaseMethodsfrom .context import StepContextfrom ..locator.locator import get_locatorfrom ..wait.strategy import WaitStrategyclass ClickMethod(BaseMethods):    """    点击    """    handler_name = "play_click"    async def execute(self, context: StepContext) -> None:        """        执行点击操作        定位元素，等待其可见，然后执行点击操作。        支持通过click_count参数指定点击次数。        Args:            context: 步骤上下文，包含页面对象、步骤信息和变量转换器        """        locator = await get_locator(context.page, context)        wait_strategy = WaitStrategy()        await wait_strategy.wait_for_element(locator, state="visible")        await locator.click()        await context.starter.send(f"点击元素 ✅ : {context.selector}")class DBCClickMethod(BaseMethods):    """    点击    """    handler_name = "play_dblclick"    async def execute(self, context: StepContext) -> None:        """        执行点击操作        定位元素，等待其可见，然后执行点击操作。        支持通过click_count参数指定点击次数。        Args:            context: 步骤上下文，包含页面对象、步骤信息和变量转换器        """        locator = await get_locator(context.page, context)        wait_strategy = WaitStrategy()        await wait_strategy.wait_for_element(locator, state="visible")        await locator.dblclick()        await context.starter.send(f"双击元素 ✅ : {context.selector}")class FillMethod(BaseMethods):    """    填充处理器    处理输入框填充操作，清空输入框后填充指定值。    """    handler_name = "play_fill"    async def execute(self, context: StepContext) -> None:        """        执行填充操作        定位输入框元素，等待其可见，然后清空并填充指定值。        Args:            context: 步骤上下文，包含页面对象、步骤信息和变量转换器        """        locator = await get_locator(context.page, context)        wait_strategy = WaitStrategy()        await wait_strategy.wait_for_element(locator, state="visible")        fill_value = await context.variable_manager.trans(context.step.fill_value)        await locator.fill(fill_value)        await context.starter.send(f"填充输入 ✅ : {context.selector} = {fill_value}")class TypeMethod(BaseMethods):    """    输入处理器    处理文本输入操作，不清空输入框直接追加文本。    """    handler_name = "play_type"    async def execute(self, context: StepContext) -> None:        """        执行输入操作        定位输入框元素，等待其可见，然后追加输入指定文本。        Args:            context: 步骤上下文，包含页面对象、步骤信息和变量转换器        """        locator = await get_locator(context.page, context)        wait_strategy = WaitStrategy()        await wait_strategy.wait_for_element(locator, state="visible")        type_value = await context.variable_manager.trans(context.step.fill_value)        await locator.type(type_value)        await context.starter.send(f"输入文本 ✅ : {context.selector} = {type_value}")class SelectMethod(BaseMethods):    """    选择处理器    处理下拉框选择操作，根据值选择选项。    """    handler_name = "play_select"    async def execute(self, context: StepContext) -> None:        """        执行选择操作        定位下拉框元素，等待其可见，然后选择指定值的选项。        Args:            context: 步骤上下文，包含页面对象、步骤信息和变量转换器        """        locator = await get_locator(context.page, context)        wait_strategy = WaitStrategy()        await wait_strategy.wait_for_element(locator, state="visible")        select_value = await context.variable_manager.trans(context.step.fill_value)        await locator.select_option(select_value)        await context.starter.send(f"选择选项 ✅ : {context.selector} = {select_value}")class CheckMethod(BaseMethods):    """    勾选处理器    处理复选框勾选操作。    """    handler_name = "play_check"    async def execute(self, context: StepContext) -> None:        """        执行勾选操作        定位复选框元素，等待其可见，然后执行勾选操作。        Args:            context: 步骤上下文，包含页面对象、步骤信息和变量转换器        """        locator = await get_locator(context.page, context)        wait_strategy = WaitStrategy()        await wait_strategy.wait_for_element(locator, state="visible")        await locator.check()        await context.starter.send(f"勾选复选框 ✅ : {context.selector}")class UncheckMethod(BaseMethods):    """    取消勾选处理器    处理复选框取消勾选操作。    """    handler_name = "play_uncheck"    async def execute(self, context: StepContext) -> None:        """        执行取消勾选操作        定位复选框元素，等待其可见，然后执行取消勾选操作。        Args:            context: 步骤上下文，包含页面对象、步骤信息和变量转换器        """        locator = await get_locator(context.page, context)        wait_strategy = WaitStrategy()        await wait_strategy.wait_for_element(locator, state="visible")        await locator.uncheck()        await context.starter.send(f"取消勾选 ✅ : {context.selector}")class HoverMethods(BaseMethods):    """    悬停处理器    处理鼠标悬停操作。    """    handler_name = "play_hover"    async def execute(self, context: StepContext) -> None:        """        执行悬停操作        定位元素，等待其可见，然后执行鼠标悬停操作。        Args:            context: 步骤上下文，包含页面对象、步骤信息和变量转换器        """        locator = await get_locator(context.page, context)        wait_strategy = WaitStrategy()        await wait_strategy.wait_for_element(locator, state="visible")        await locator.hover()        await context.starter.send(f"悬停元素 ✅ : {context.selector}")class FocusMethod(BaseMethods):    """    聚焦处理器    处理元素聚焦操作。    """    handler_name = "play_focus"    async def execute(self, context: StepContext) -> None:        """        执行聚焦操作        定位元素，等待其可见，然后执行聚焦操作。        Args:            context: 步骤上下文，包含页面对象、步骤信息和变量转换器        """        locator = await get_locator(context.page, context)        wait_strategy = WaitStrategy()        await wait_strategy.wait_for_element(locator, state="visible")        await locator.focus()        await context.starter.send(f"聚焦元素 ✅ : {context.selector}")

class PressMethod(BaseMethods):
    """
    键盘按键处理器
    模拟键盘按键操作，支持单个按键或组合键。
    """
    handler_name = "play_press"

    async def execute(self, context: StepContext) -> None:
        """
        执行键盘按键操作
        在页面上模拟按下指定的键盘按键。
        Args:
            context: 步骤上下文，包含页面对象、步骤信息和变量转换器
        """
        key = await context.variable_manager.trans(context.step.fill_value)
        key = key.strip()
        await context.page.keyboard.press(key)
        await context.starter.send(f"按键 ✅ : {key}")


class UploadMethod(BaseMethods):
    """
    文件上传处理器
    向文件上传元素选择并上传文件。
    """
    handler_name = "play_upload"

    async def execute(self, context: StepContext) -> None:
        """
        执行文件上传操作
        定位文件上传元素，根据文件类型选择对应的测试文件进行上传。
        Args:
            context: 步骤上下文，包含页面对象、步骤信息和变量转换器
        """
        from config import png, xlsx

        locator = await get_locator(context.page, context)
        wait_strategy = WaitStrategy()
        await wait_strategy.wait_for_element(locator, state="visible")

        file_type = await context.variable_manager.trans(context.step.fill_value)
        if file_type == "xlsx":
            await locator.set_input_files(xlsx)
        else:
            await locator.set_input_files(png)
        await context.starter.send(f"上传文件 ✅ : {file_type}")
