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
    from croe.interface.writer.result_writer import ResultWriter
    from app.model.interfaceAPIModel.contents import InterfaceCaseContents
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
    # BUG-F8 修复: result_writer 注入上下文, 替代模块级单例
    # (BUG-D1 修复不闭环: 8 个 step_content_*.py 仍用模块单例,
    # 导致 STEP_API content_result_cache 永远不被 flush, 案例拿不到数据)
    result_writer: "ResultWriter"
    task_result: Optional["InterfaceTaskResult"] = None


@dataclass
class CaseStepContext:
    """步骤执行上下文"""

    index: int
    content: "InterfaceCaseContents"
    execution_context: ExecutionContext
    starter: Union[APIStarter, UIStarter]
    variable_manager: VariableManager

    @property
    def result_writer(self) -> "ResultWriter":
        """[BUG-F8] 步骤级便捷访问, 避免每个 strategy 写一长串 execution_context.result_writer"""
        return self.execution_context.result_writer

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
