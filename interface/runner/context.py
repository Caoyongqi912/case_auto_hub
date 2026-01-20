#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : context
# @Software: PyCharm
# @Desc: 执行上下文

from dataclasses import dataclass, field
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.model.interface import InterFaceCaseModel, InterfaceCaseStepContent
    from app.model.base import Env
    from app.model.interface.interfaceResultModel import (
        InterfaceCaseResult, InterfaceTaskResult
    )
    from interface.runner.variable_manager import VariableManager


@dataclass
class ExecutionContext:
    """执行上下文"""
    interface_case: 'InterFaceCaseModel'
    env: 'Env'
    case_result: 'InterfaceCaseResult'
    task: Optional['InterfaceTaskResult'] = None
    current_step_index: int = 0
    total_steps: int = 0
    error_stop: bool = True

    @property
    def current_progress(self) -> float:
        """当前执行进度百分比"""
        if self.total_steps == 0:
            return 100.0
        return round(self.current_step_index / self.total_steps, 2) * 100

    def should_stop_on_error(self, flag: bool) -> bool:
        """是否在错误时停止"""
        return not flag and self.error_stop

    def update_progress(self, step_index: int):
        """更新进度"""
        self.current_step_index = step_index
        self.case_result.progress = self.current_progress


@dataclass
class StepContext:
    """步骤执行上下文"""
    step: 'InterfaceCaseStepContent'
    step_index: int
    execution_context: ExecutionContext
    starter: 'APIStarter'
    variable_manager: 'VariableManager'

    @property
    def interface_task_result_id(self) -> Optional[int]:
        return self.execution_context.task.id if self.execution_context.task else None

    @property
    def interface_case_result_id(self) -> int:
        return self.execution_context.case_result.id
