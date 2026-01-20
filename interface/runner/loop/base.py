#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : base
# @Software: PyCharm
# @Desc: 循环执行器基类

from abc import ABC, abstractmethod
from typing import List

from app.model.interface import InterfaceAPI
from app.model.base import Env
from app.model.interface.InterfaceCaseStepContent import InterfaceCaseStepContent
from app.model.interface.interfaceResultModel import InterfaceContentResult


class LoopExecutor(ABC):
    """循环执行器基类"""
    
    def __init__(self, starter, variable_manager, interface_executor):
        self.starter = starter
        self.variable_manager = variable_manager
        self.interface_executor = interface_executor
    
    @abstractmethod
    async def execute(
        self,
        loop: InterfaceCaseStepContent,
        api_steps: List[InterfaceAPI],
        env: Env,
        content_result: InterfaceContentResult
    ):
        """执行循环"""
        pass
