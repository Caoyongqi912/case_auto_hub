#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
UI自动化测试框架 - 主入口模块

提供优化后的UI自动化测试核心功能，包括：
- 浏览器管理（单例模式 + 上下文池）
- 元素定位缓存
- 自适应等待策略
- 批量数据库写入
- 异步截图处理
- 条件判断缓存
"""

# 核心组件
from .core.browser_manager import (
    BrowserManager,
    BrowserManagerFactory,
)

# 执行器
from .executor.case_executor import CaseExecutor
from .executor.step_executor import StepExecutor
from .executor.method_chain import MethodChain

# 方法处理器
from .methods.base import BaseMethods
from .methods.context import StepContext

# 元素定位
from .locator.locator import get_locator

# 等待策略
from .wait.strategy import WaitStrategy

# 结果处理
from .result.writer import PlayResultWriter

__version__ = "2.0.0"

__all__ = [
    "BrowserManager",
    "BrowserManagerFactory",
    "CaseExecutor",
    "StepExecutor",
    "MethodChain",
    "BaseMethods",
    "StepContext",
    "get_locator",
    "WaitStrategy",
    "PlayResultWriter",
]
