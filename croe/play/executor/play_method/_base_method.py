#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : _base_api
# @Software: PyCharm
# @Desc:

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from playwright.async_api import Locator, Page

from croe.play.context import StepContext


class BaseMethods(ABC):
    """
    处理器基类

    实现责任链模式，每个处理器负责处理特定类型的操作。
    如果当前处理器无法处理请求，则传递给下一个处理器。
    """
    method_name: str = "base"

    def __init__(self):
        """
        初始化处理器

        创建处理器实例，并初始化下一个处理器的引用。
        """
        self._next_method: Optional[BaseMethods] = None

    def set_next(self, method: "BaseMethods") -> "BaseMethods":
        """
        设置下一个处理器

        在责任链中设置下一个处理器，形成链式调用结构。

        Args:
            method: 下一个处理器实例

        Returns:
            BaseMethods: 返回传入的处理器，支持链式调用
        """
        self._next_method = method
        return method

    async def handle(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        处理步骤请求

        如果当前处理器可以处理该请求，则执行处理逻辑；
        否则将请求传递给下一个处理器。

        Args:
            context: 步骤上下文，包含页面对象、步骤信息和变量转换器
            locator:

        Returns:
            tuple[bool, Optional[Dict[str, Any]]]: 执行结果和断言信息（如果是断言方法）

        Raises:
            ActionError: 当处理器执行失败时抛出
        """
        if self.__can_handle(context):
            try:
                return await self.execute(locator=locator, context=context)
            except Exception:
                raise
        if self._next_method:
            return await self._next_method.handle(locator=locator, context=context)
        return False, None

    def __can_handle(self, context) -> bool:
        """
        判断是否可以处理该请求

        根据步骤的方法名称判断当前处理器是否可以处理该请求。

        Args:
            context: 步骤上下文

        Returns:
            bool: 如果可以处理则返回True，否则返回False
        """
        return context.step.method == self.method_name

    @abstractmethod
    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        执行具体的处理逻辑

        子类必须实现此方法，定义具体的操作执行逻辑。

        Args:
            context: 步骤上下文，包含页面对象、步骤信息和变量转换器
            locator:

        Returns:
            tuple[bool, Optional[Dict[str, Any]]]: 执行结果和断言信息（如果是断言方法）
        """
        pass


__all__ = [
    "BaseMethods",
]
