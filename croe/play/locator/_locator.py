#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : _locator.py
# @Software: PyCharm
# @Desc:
from abc import ABC, abstractmethod
from playwright.async_api import Locator
from croe.play.context import StepContext
from utils import log


class LocatorMethods(ABC):
    """
    定位器方法基类

    所有定位器类的基类，使用 __init_subclass__ 实现自动注册机制。
    子类会自动注册到 _registry 字典中，支持 O(1) 时间复杂度的查询。
    """
    getter_name: str = "base"  # play step getter
    registry: dict = {}  # 定位器类注册表

    def __init_subclass__(cls, **kwargs):
        """
        子类自动注册机制

        当定义新的定位器子类时，自动将其注册到 registry 字典中。
        这样可以实现 O(1) 时间复杂度的定位器查询。

        示例：
            class GetByCustom(LocatorMethods):
                getter_name = "get_by_custom"
                # 自动注册到 registry["get_by_custom"] = GetByCustom
        """
        super().__init_subclass__(**kwargs)
        if cls.getter_name != "base":  # 跳过基类本身
            LocatorMethods.registry[cls.getter_name] = cls

    @abstractmethod
    async def locator(self, context) -> Locator:
        """
        执行具体的处理逻辑

        子类必须实现此方法，定义具体的操作执行逻辑。

        Args:
            context: 步骤上下文，包含页面对象、步骤信息和变量转换器

        Returns:
            Locator: 匹配的定位器对象
        """
        pass


class GetByAltText(LocatorMethods):
    """
    通过 alt 文本定位元素（通常用于图片）

    示例：
        <img alt="User Avatar">
    """
    getter_name = "get_by_alt_text"

    async def locator(self, context: StepContext) -> Locator:
        """
        通过 alt 属性文本获取定位器

        Args:
            context: 步骤上下文，包含页面对象和选择器

        Returns:
            Locator: 匹配的定位器对象
        """
        locator = context.page.get_by_alt_text(context.selector)
        log.info(f"get_by_alt_text: {context.selector}")
        return locator


class GetByLabel(LocatorMethods):
    """
    通过关联的 label 文本定位表单元素

    示例：
        <label for="username">Username:</label>
        <input id="username">
    """
    getter_name = "get_by_label"

    async def locator(self, context: StepContext) -> Locator:
        """
        通过 label 文本获取定位器

        Args:
            context: 步骤上下文，包含页面对象和选择器

        Returns:
            Locator: 匹配的定位器对象
        """
        locator = context.page.get_by_label(context.selector, exact=True)
        log.info(f"get_by_label: {context.selector}")
        return locator


class GetByPlaceholder(LocatorMethods):
    """
    通过 placeholder 属性定位输入框

    示例：
        <input placeholder="Enter your name">
    """
    getter_name = "get_by_placeholder"

    async def locator(self, context: StepContext) -> Locator:
        """
        通过 placeholder 属性获取定位器

        Args:
            context: 步骤上下文，包含页面对象和选择器

        Returns:
            Locator: 匹配的定位器对象
        """
        locator = context.page.get_by_placeholder(context.selector, exact=True)
        log.info(f"get_by_placeholder: {context.selector}")
        return locator


class GetByTestId(LocatorMethods):
    """
    通过 data-testid 属性定位元素

    示例：
        <button data-testid="submit-button">Submit</button>
    """
    getter_name = "get_by_test_id"

    async def locator(self, context: StepContext) -> Locator:
        """
        通过 data-testid 属性获取定位器

        Args:
            context: 步骤上下文，包含页面对象和选择器

        Returns:
            Locator: 匹配的定位器对象
        """
        locator = context.page.get_by_test_id(context.selector)
        log.info(f"get_by_test_id: {context.selector}")
        return locator


class GetByText(LocatorMethods):
    """
    通过文本内容定位元素

    示例：
        <button>Click me</button>
        <span>Welcome</span>
    """
    getter_name = "get_by_text"

    async def locator(self, context: StepContext) -> Locator:
        """
        通过文本内容获取定位器

        Args:
            context: 步骤上下文，包含页面对象和选择器

        Returns:
            Locator: 匹配的定位器对象
        """
        locator = context.page.get_by_text(context.selector, exact=True)
        log.info(f"get_by_text: {context.selector}")
        return locator


class GetByTitle(LocatorMethods):
    """
    通过 title 属性定位元素

    示例：
        <button title="Save changes">Save</button>
    """
    getter_name = "get_by_title"

    async def locator(self, context: StepContext) -> Locator:
        """
        通过 title 属性获取定位器

        Args:
            context: 步骤上下文，包含页面对象和选择器

        Returns:
            Locator: 匹配的定位器对象
        """
        locator = context.page.get_by_title(context.selector, exact=True)
        log.info(f"get_by_title: {context.selector}")
        return locator


__all__ = [
    "LocatorMethods",
    "GetByAltText",
    "GetByLabel",
    "GetByPlaceholder",
    "GetByTestId",
    "GetByText",
    "GetByTitle",
]
