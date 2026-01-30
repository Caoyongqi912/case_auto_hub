#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc:

from playwright.async_api import Locator
from utils import log
from ._locator import (
    LocatorMethods,
    GetByAltText,
    GetByLabel,
    GetByPlaceholder,
    GetByText,
    GetByTitle,
    GetByTestId,
)
from croe.play.context import StepContext


class LocatorHandler:
    """
    定位器处理器

    使用 __init_subclass__ 自动注册机制管理所有定位器类。
    根据 getter_name 从注册表中 O(1) 时间复杂度查询定位器类。
    """

    @classmethod
    def get_handler(cls, locator_text: str):
        """
        根据 getter_name 获取对应的定位器处理器

        从 LocatorMethods._registry 中查询，时间复杂度为 O(1)。

        Args:
            locator_text: 定位器名称（如 'get_by_alt_text'）

        Returns:
            对应的定位器类实例

        Raises:
            ValueError: 当 getter_name 不被支持时抛出
        """
        handler_class = LocatorMethods.registry.get(locator_text)

        if handler_class is None:
            supported_getters = list(LocatorMethods.registry.keys())
            raise ValueError(
                f"不支持的定位器类型: {locator_text}. "
                f"支持的类型: {', '.join(supported_getters)}"
            )

        return handler_class()

    @classmethod
    def get_supported_getters(cls) -> list:
        """
        获取所有支持的定位器类型

        Returns:
            支持的定位器名称列表
        """
        return list(LocatorMethods.registry.keys())


async def get_locator(context: StepContext) -> Locator:
    """
    根据步骤上下文获取定位器

    根据 context.step.getter 自动选择合适的定位器类，
    并返回匹配的 Locator 对象。

    Args:
        context: 步骤上下文，包含：
            - page: Playwright 页面对象
            - selector: 选择器字符串
            - step.getter: 定位器类型名称
            - step.iframe_name: iframe 名称（可选）

    Returns:
        Locator: 匹配的定位器对象

    Raises:
        ValueError: 当 locator 不被支持时抛出
        Exception: 当定位器获取失败时抛出

    示例：
        context.step.getter = "get_by_alt_text"
        context.selector = "User Avatar"
        locator = await get_locator(context)
    """
    try:
        # 验证 selector 不为空
        if not context.selector:
            raise ValueError(
                f"步骤 {context.step.name} 缺少选择器：locator 和 selector 都为空"
            )

        if context.locator:
            # 获取对应的定位器处理器（O(1) 查询）
            handler = LocatorHandler.get_handler(context.step.locator)

            # 调用处理器获取定位器
            locator = await handler.locator(context)

            log.info(
                f"成功获取定位器 [{context.step.locator}]: {context.selector}"
            )
        else:
            # 使用 CSS 选择器或 iframe 定位
            if context.step.iframe_name:
                locator = context.page.frame_locator(
                    context.step.iframe_name
                ).locator(context.selector)
            else:
                locator = context.page.locator(context.selector)

        return locator

    except ValueError as e:
        log.error(f"定位器类型错误: {e}")
        raise
    except Exception as e:
        log.error(
            f"获取定位器失败 [{context.step.locator}]: "
            f"{context.selector} - {str(e)}"
        )
        raise


__all__ = [
    "get_locator",
]
