#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: 步骤执行器注册中心 - 替代责任链模式，实现基于method_name的精确匹配

from typing import Dict, Type, Optional, List

from ._base_method import BaseMethods
from .action_methods import (
    ClickMethod,
    BlurMethod,
    DblclickMethod,
    CheckMethod,
    UncheckMethod,
    ClearMethod,
    CountMethod,
    EvaluateMethod,
    FocusMethod,
    FillMethod,
    TypeMethod,
    HoverMethod,
    PressMethod,
    GetAttributeMethod,
    GetInnerTextMethod,
    GetInputValueMethod,
    GetTextContentMethod,
    SelectOptionLabelMethod,
    SelectOptionValueMethod,
    SelectOptionValuesMethod,
    SetCheckedMethod,
    SetUncheckedMethod,
    UploadMethod,
)
from .assert_methods import (
    AssertIsCheckedMethod,
    AssertIsDisabledMethod,
    AssertIsEditableMethod,
    AssertIsEmptyMethod,
    AssertIsEnabledMethod,
    AssertIsFocusedMethod,
    AssertIsHiddenMethod,
    AssertUrlTitle,
)
from .page_method import (
    GotoMethod,
    ReloadMethod,
    BackMethod,
    ForwardMethod,
    WaitMethod,
)
from utils import log


class StepExecutorRegistry:
    """
    步骤执行器注册中心
    
    使用字典映射实现基于method_name的精确匹配，替代责任链模式。
    提供高性能的步骤执行器查找和执行能力。
    """
    
    def __init__(self):
        self._executors: Dict[str, BaseMethods] = {}
    
    def register(self, executor_class: Type[BaseMethods]) -> None:
        """
        注册步骤执行器
        
        Args:
            executor_class: 执行器类，必须继承自BaseMethods
        """
        executor = executor_class()
        method_name = executor.method_name
        if method_name in self._executors:
            log.warning(f"Executor for method '{method_name}' already registered, overwriting")
        self._executors[method_name] = executor

    def get_executor(self, method_name: str) -> Optional[BaseMethods]:
        """
        获取指定method_name对应的执行器
        
        Args:
            method_name: 方法名称
            
        Returns:
            执行器实例，如果未找到则返回None
        """
        return self._executors.get(method_name)
    
    def has_executor(self, method_name: str) -> bool:
        """
        检查是否存在指定method_name的执行器
        
        Args:
            method_name: 方法名称
            
        Returns:
            如果存在返回True，否则返回False
        """
        return method_name in self._executors
    
    def get_all_method_names(self) -> List[str]:
        """
        获取所有已注册的方法名称
        
        Returns:
            方法名称列表
        """
        return list(self._executors.keys())
    
    def register_default_executors(self) -> None:
        """
        注册所有默认的执行器
        """
        # 页面操作方法
        self.register(GotoMethod)
        self.register(ReloadMethod)
        self.register(BackMethod)
        self.register(ForwardMethod)
        self.register(WaitMethod)
        
        # 元素交互方法
        self.register(ClickMethod)
        self.register(DblclickMethod)
        self.register(CheckMethod)
        self.register(UncheckMethod)
        self.register(ClearMethod)
        self.register(FillMethod)
        self.register(TypeMethod)
        self.register(FocusMethod)
        self.register(BlurMethod)
        self.register(HoverMethod)
        self.register(PressMethod)
        self.register(SelectOptionLabelMethod)
        self.register(SelectOptionValueMethod)
        self.register(SelectOptionValuesMethod)
        self.register(SetCheckedMethod)
        self.register(SetUncheckedMethod)
        self.register(UploadMethod)
        
        # 数据提取方法
        self.register(CountMethod)
        self.register(GetAttributeMethod)
        self.register(GetInnerTextMethod)
        self.register(GetInputValueMethod)
        self.register(GetTextContentMethod)
        self.register(EvaluateMethod)
        
        # 断言方法
        self.register(AssertIsCheckedMethod)
        self.register(AssertIsDisabledMethod)
        self.register(AssertIsEditableMethod)
        self.register(AssertIsEmptyMethod)
        self.register(AssertIsEnabledMethod)
        self.register(AssertIsFocusedMethod)
        self.register(AssertIsHiddenMethod)
        self.register(AssertUrlTitle)


# 创建全局执行器注册中心实例
executor_registry = StepExecutorRegistry()
executor_registry.register_default_executors()


__all__ = [
    "StepExecutorRegistry",
    "executor_registry",
]
