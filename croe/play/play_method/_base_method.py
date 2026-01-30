#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : _base_api
# @Software: PyCharm
# @Desc:

from abc import ABC, abstractmethod
from typing import Optional

from patchright.async_api import Locator

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

    async def handle(self, context) -> bool:
        """
        处理步骤请求

        如果当前处理器可以处理该请求，则执行处理逻辑；
        否则将请求传递给下一个处理器。

        Args:
            context: 步骤上下文，包含页面对象、步骤信息和变量转换器

        Returns:
            bool: 如果请求被处理则返回True，否则返回False

        Raises:
            ActionError: 当处理器执行失败时抛出
        """
        if self.can_handle(context):
            try:
                await self.execute(context)
                return True
            except Exception:
                raise
        if self._next_method:
            return await self._next_method.handle(context)
        return False

    def can_handle(self, context) -> bool:
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
    async def execute(self, locator: Locator, context: StepContext) -> None:
        """
        执行具体的处理逻辑

        子类必须实现此方法，定义具体的操作执行逻辑。

        Args:
            context: 步骤上下文，包含页面对象、步骤信息和变量转换器
            locator:
        """
        pass


# class HandlerChain:
#     """
#     处理器链管理器
#
#     负责构建和管理处理器责任链，支持动态添加处理器和构建默认处理器链。
#     """
#
#     def __init__(self):
#         """
#         初始化处理器链
#
#         创建空的处理器列表和链头。
#         """
#         self._handlers: List[BaseHandler] = []
#         self._chain: Optional[BaseHandler] = None
#
#     def add_handler(self, handler: BaseHandler) -> "HandlerChain":
#         """
#         添加处理器到链中
#
#         将处理器添加到处理器列表，支持链式调用。
#
#         Args:
#             handler: 要添加的处理器实例
#
#         Returns:
#             HandlerChain: 返回自身，支持链式调用
#         """
#         self._handlers.append(handler)
#         return self
#
#     def build(self) -> BaseHandler:
#         """
#         构建处理器链
#
#         将所有添加的处理器按顺序连接成责任链，并返回链头。
#
#         Returns:
#             BaseHandler: 责任链的头部处理器
#
#         Raises:
#             ValueError: 当没有添加任何处理器时抛出
#         """
#         if not self._handlers:
#             raise ValueError("No handlers added to chain")
#
#         if self._chain is None:
#             self._chain = self._handlers[0]
#
#         for i in range(len(self._handlers) - 1):
#             self._handlers[i].set_next(self._handlers[i + 1])
#
#         return self._chain
#
#     @classmethod
#     def create_default_chain(cls) -> BaseHandler:
#         """
#         创建默认的处理器链
#
#         创建包含所有标准处理器的默认责任链，按功能分类排列。
#
#         Returns:
#             BaseHandler: 构建完成的默认处理器链
#         """
#         chain = cls()
#
#         chain.add_handler(ClickHandler())
#
#
#         return chain.build()


__all__ = [
    "BaseMethods",
]
