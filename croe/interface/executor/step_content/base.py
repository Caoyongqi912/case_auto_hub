#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : base
# @Software: PyCharm
# @Desc: 步骤执行策略基类

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from enums import InterfaceAPIResultEnum

if TYPE_CHECKING:
    from croe.interface.executor.context import CaseStepContext
    from croe.interface.executor.interface_executor import InterfaceExecutor


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

    async def _record_step_outcome(
        self,
        step_context: "CaseStepContext",
        success: bool
    ) -> None:
        """
        记录步骤执行结果并更新用例统计与进度。

        Args:
            step_context: 步骤执行上下文
            success: 步骤是否成功
        """
        case_result = step_context.execution_context.case_result
        if success:
            case_result.success_num += 1
        else:
            case_result.fail_num += 1
            case_result.result = InterfaceAPIResultEnum.ERROR
        await step_context.result_writer.update_case_progress(case_result)
