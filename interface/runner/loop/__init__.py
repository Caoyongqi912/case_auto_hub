#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : __init__
# @Software: PyCharm
# @Desc:

from .base import LoopExecutor
from .loop_times import LoopTimesExecutor
from .loop_items import LoopItemsExecutor
from .loop_condition import LoopConditionExecutor
from enums.CaseEnum import LoopTypeEnum


def get_loop_executor(loop_type: int, starter, variable_manager, interface_executor) -> LoopExecutor:
    """根据循环类型获取对应的执行器"""
    match loop_type:
        case LoopTypeEnum.LoopTimes:
            return LoopTimesExecutor(starter, variable_manager, interface_executor)
        case LoopTypeEnum.LoopItems:
            return LoopItemsExecutor(starter, variable_manager, interface_executor)
        case LoopTypeEnum.LoopCondition:
            return LoopConditionExecutor(starter, variable_manager, interface_executor)
        case _:
            raise ValueError(f"Unknown loop type: {loop_type}")
