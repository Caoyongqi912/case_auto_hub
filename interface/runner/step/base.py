#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : base
# @Software: PyCharm
# @Desc: 步骤执行器基类

from abc import ABC, abstractmethod

from .context import StepContext


class StepStrategy(ABC):
    """步骤执行策略基类"""
    
    @abstractmethod
    async def execute(self, step_context: StepContext) -> bool:
        """执行步骤，返回是否成功"""
        pass
