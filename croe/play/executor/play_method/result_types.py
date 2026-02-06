#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : result_types
# @Software: PyCharm
# @Desc: 定义方法执行结果的类型和工具函数

from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass

# 类型别名
InfoDict = Dict[str, Any]
ErrorType = Literal["timeout", "element_not_found", "assertion_failed", "interaction_failed", "unknown"]


@dataclass
class StepExecutionResult:
    """
    步骤执行结果
    
    用于统一所有步骤执行器的返回格式，确保流程能够无缝继续到下一个步骤。
    """
    success: bool
    """执行是否成功"""

    message: Optional[str] = None
    """执行结果消息（错误信息或成功消息）"""

    error_type: Optional[ErrorType] = None
    """错误类型（仅当success为False时有值）"""

    assert_data: Optional[Dict[str, Any]] = None
    """执行产生的额外数据（如断言信息）"""

    extract_data: Optional[Dict[str, Any]] = None
    """执行产生的额外数据（提取的变量）"""

    def to_tuple(self) -> tuple[bool, Optional[str]]:
        """
        转换为旧格式的元组，保持向后兼容
        
        Returns:
            (success, message) 元组
        """
        return self.success, self.message


def create_success_result(message: Optional[str] = None, assert_data: Optional[Dict[str, Any]] = None,
                          extract_data: Optional[Dict[str, Any]] = None) -> StepExecutionResult:
    """
    创建成功执行结果
    
    Args:
        message: 成功消息
        assert_data: 断言数据
        extract_data: 变量谁
        
    Returns:
        StepExecutionResult: 成功的执行结果
    """
    return StepExecutionResult(
        success=True,
        message=message,
        assert_data=assert_data,
        extract_data=extract_data
    )


def create_error_result(
        error_type: ErrorType,
        message: str,
        selector: Optional[str] = None,
        **extra
) -> StepExecutionResult:
    """
    创建错误执行结果
    
    Args:
        error_type: 错误类型
        message: 错误消息
        selector: 选择器（可选）
        **extra: 其他额外信息
        
    Returns:
        StepExecutionResult: 失败的执行结果
    """
    data = {"error_type": error_type}
    if selector:
        data["selector"] = selector
    if extra:
        data.update(extra)

    return StepExecutionResult(
        success=False,
        message=message,
        error_type=error_type,
    )


def create_error_info(
        error_type: ErrorType,
        message: str,
        selector: Optional[str] = None,
        **extra
) -> InfoDict:
    """
    创建错误信息字典（保持向后兼容）

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
    创建断言信息字典（保持向后兼容）

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
    "StepExecutionResult",
    "create_success_result",
    "create_error_result",
    "create_error_info",
    "create_assert_info",
]
