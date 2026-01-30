#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/8/12
# @Author : cyq
# @File : exception
# @Software: PyCharm
# @Desc:


class APIAssertException(AssertionError):
    ...



class RetryException(Exception):
    ...


class PlayExecutionError(Exception):
    """基础执行异常"""
    pass


class ActionError(PlayExecutionError):
    """操作异常"""
    pass


class AssertionFailedError(PlayExecutionError):
    """断言失败异常"""
    pass


class VariableError(PlayExecutionError):
    """变量异常"""
    pass

