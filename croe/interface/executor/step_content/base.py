#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : base
# @Software: PyCharm
# @Desc: 步骤执行策略基类

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from croe.interface.executor.context import CaseStepContext


class StepBaseStrategy(ABC):
    """步骤执行策略基类"""

    def __init__(self, interface_executor: "InterfaceExecutor") -> None:
        """
        初始化步骤执行策略

        Args:
            interface_executor: 接口执行器实例
        """
        self.interface_executor = interface_executor

    @abstractmethod
    async def execute(self, step_context: "CaseStepContext") -> bool:
        """
        执行步骤

        Args:
            step_context: 步骤执行上下文

        Returns:
            是否执行成功
        """
        pass
