#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : context
# @Software: PyCharm
# @Desc: 执行上下文模块

from dataclasses import dataclass
from typing import Optional, Union, TYPE_CHECKING

from croe.a_manager.variable_manager import VariableManager
from croe.interface.starter import APIStarter
from croe.play.starter import UIStarter

if TYPE_CHECKING:
    from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
    from app.model.interfaceAPIModel.interfaceResultModel import (
        InterfaceCaseResult,
        InterfaceTaskResult
    )
    from app.model.base import EnvModel


@dataclass
class ExecutionContext:
    """执行上下文"""

    interface_case: "InterfaceCase"
    env: "EnvModel"
    case_result: "InterfaceCaseResult"
    task_result: Optional["InterfaceTaskResult"] = None


@dataclass
class CaseStepContext:
    """步骤执行上下文"""

    index: int
    content: "InterfaceCaseContent"
    execution_context: "ExecutionContext"
    starter: Union["APIStarter", "UIStarter"]
    variable_manager: "VariableManager"

    @property
    def task_result_id(self) -> Optional[int]:
        """
        获取任务结果ID

        Returns:
            任务结果ID，如果不存在则返回None
        """
        if self.execution_context.task_result:
            return self.execution_context.task_result.id
        return None

    @property
    def case_result_id(self) -> int:
        """
        获取用例结果ID

        Returns:
            用例结果ID
        """
        return self.execution_context.case_result.id
