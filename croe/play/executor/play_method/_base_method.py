#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : _base_api
# @Software: PyCharm
# @Desc:

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from croe.play.context import StepContext
from croe.play.executor.play_method.result_types import create_error_info, StepExecutionResult
from utils import log


class BaseMethods(ABC):
    """
    处理器基类

    实现责任链模式，每个处理器负责处理特定类型的操作。
    如果当前处理器无法处理请求，则传递给下一个处理器。
    """
    method_name: str = "base"
    requires_locator: bool = True

    @abstractmethod
    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        """
        执行具体的处理逻辑

        子类必须实现此方法，定义具体的操作执行逻辑。

        Args:
            context: 步骤上下文，包含页面对象、步骤信息和变量转换器
            locator:

        Returns:
            tuple[bool, Optional[Dict[str, Any]]]:
                - 第一个元素表示执行是否成功
                - 第二个元素包含执行结果信息（错误信息或断言信息），成功时可能为None

        """
        pass


__all__ = [
    "BaseMethods",
]
