#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : result_types
# @Software: PyCharm
# @Desc: 定义方法执行结果的类型和工具函数

from typing import Dict, Any, Optional, Literal

# 类型别名
InfoDict = Dict[str, Any]
ErrorType = Literal["timeout", "element_not_found", "assertion_failed", "interaction_failed", "unknown"]


def create_error_info(
    error_type: ErrorType,
    message: str,
    selector: Optional[str] = None,
    **extra
) -> InfoDict:
    """
    创建错误信息字典

    Args:
        error_type: 错误类型
        message: 错误消息
        selector: 选择器（可选）
        **extra: 其他额外信息

    Returns:
        标准化的错误信息字典
    """
    info = {
        "error_type": error_type,
        "message": message,
    }
    if selector:
        info["selector"] = selector
    if extra:
        info.update(extra)
    return info


def create_assert_info(
    assert_name: str,
    assert_opt: str,
    assert_expect: Any,
    assert_actual: Any,
    assert_result: bool,
    **extra
) -> InfoDict:
    """
    创建断言信息字典

    Args:
        assert_name: 断言名称
        assert_opt: 断言操作符（=, !=, >, < 等）
        assert_expect: 期望值
        assert_actual: 实际值
        assert_result: 断言结果
        **extra: 其他额外信息（如 id, desc, type 等）

    Returns:
        标准化的断言信息字典
    """
    info = {
        "assert_name": assert_name,
        "assert_opt": assert_opt,
        "assert_expect": assert_expect,
        "assert_actual": assert_actual,
        "assert_result": assert_result,
    }
    if extra:
        info.update(extra)
    return info


__all__ = [
    "InfoDict",
    "ErrorType",
    "create_error_info",
    "create_assert_info",
]
