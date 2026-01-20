#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : __init__
# @Software: PyCharm
# @Desc:

from .base import StepStrategy
from .api_step import ApiStepStrategy
from .api_group_step import ApiGroupStepStrategy
from .wait_step import WaitStepStrategy
from .script_step import ScriptStepStrategy
from .assert_step import AssertStepStrategy
from .sql_step import SqlStepStrategy
from .condition_step import ConditionStepStrategy
from enums.CaseEnum import CaseStepContentType


def get_step_strategy(step_type: int, interface_executor) -> StepStrategy:
    """根据步骤类型获取对应的策略"""
    match step_type:
        case CaseStepContentType.STEP_API:
            return ApiStepStrategy(interface_executor)
        case CaseStepContentType.STEP_API_GROUP:
            return ApiGroupStepStrategy(interface_executor)
        case CaseStepContentType.STEP_API_WAIT:
            return WaitStepStrategy()
        case CaseStepContentType.STEP_API_SCRIPT:
            return ScriptStepStrategy()
        case CaseStepContentType.STEP_API_ASSERT:
            return AssertStepStrategy()
        case CaseStepContentType.STEP_API_DB:
            return SqlStepStrategy()
        case CaseStepContentType.STEP_API_CONDITION:
            return ConditionStepStrategy(interface_executor)
        case _:
            raise ValueError(f"Unknown step type: {step_type}")
