#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc:

from typing import List, Optional

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


class PlayMethodChain:
    """
    处理器链管理器

    负责构建和管理处理器责任链，支持动态添加处理器和构建默认处理器链。
    """

    def __init__(self):
        """
        初始化处理器链

        创建空的处理器列表和链头。
        """
        self._methods: List[BaseMethods] = []
        self._chain: Optional[BaseMethods] = None

    def add_method(self, method: BaseMethods) -> "PlayMethodChain":
        """
        添加处理器到链中

        将处理器添加到处理器列表，支持链式调用。

        Args:
            method: 要添加的处理器实例

        Returns:
            PlayMethodChain: 返回自身，支持链式调用
        """
        self._methods.append(method)
        return self

    def build(self) -> BaseMethods:
        """
        构建处理器链

        将所有添加的处理器按顺序连接成责任链，并返回链头。

        Returns:
            BaseMethods: 责任链的头部处理器

        Raises:
            ValueError: 当没有添加任何处理器时抛出
        """
        if not self._methods:
            raise ValueError("No handlers added to chain")

        if self._chain is None:
            self._chain = self._methods[0]

        for i in range(len(self._methods) - 1):
            self._methods[i].set_next(self._methods[i + 1])

        return self._chain

    @classmethod
    def create_default_chain(cls) -> BaseMethods:
        """
        创建默认的处理器链

        创建包含所有标准处理器的默认责任链，按功能分类排列：
        1. 页面操作方法
        2. 元素交互方法
        3. 数据提取方法
        4. 断言方法

        Returns:
            BaseMethods: 构建完成的默认处理器链
        """
        chain = cls()

        # 页面操作方法
        chain.add_method(GotoMethod())
        chain.add_method(ReloadMethod())
        chain.add_method(BackMethod())
        chain.add_method(ForwardMethod())
        chain.add_method(WaitMethod())

        # 元素交互方法
        chain.add_method(ClickMethod())
        chain.add_method(DblclickMethod())
        chain.add_method(CheckMethod())
        chain.add_method(UncheckMethod())
        chain.add_method(ClearMethod())
        chain.add_method(FillMethod())
        chain.add_method(TypeMethod())
        chain.add_method(FocusMethod())
        chain.add_method(BlurMethod())
        chain.add_method(HoverMethod())
        chain.add_method(PressMethod())
        chain.add_method(SelectOptionLabelMethod())
        chain.add_method(SelectOptionValueMethod())
        chain.add_method(SelectOptionValuesMethod())
        chain.add_method(SetCheckedMethod())
        chain.add_method(SetUncheckedMethod())
        chain.add_method(UploadMethod())

        # 数据提取方法
        chain.add_method(CountMethod())
        chain.add_method(GetAttributeMethod())
        chain.add_method(GetInnerTextMethod())
        chain.add_method(GetInputValueMethod())
        chain.add_method(GetTextContentMethod())
        chain.add_method(EvaluateMethod())

        # 断言方法
        chain.add_method(AssertIsCheckedMethod())
        chain.add_method(AssertIsDisabledMethod())
        chain.add_method(AssertIsEditableMethod())
        chain.add_method(AssertIsEmptyMethod())
        chain.add_method(AssertIsEnabledMethod())
        chain.add_method(AssertIsFocusedMethod())
        chain.add_method(AssertIsHiddenMethod())
        chain.add_method(AssertUrlTitle())

        return chain.build()


# 创建全局方法链实例
method_chain = PlayMethodChain.create_default_chain()

__all__ = [
    "method_chain",
    "PlayMethodChain",
]
