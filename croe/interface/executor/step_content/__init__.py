#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: 步骤执行策略工厂

from typing import TYPE_CHECKING

from enums.CaseEnum import CaseStepContentType
from .step_content_api import APIStepContentStrategy
from .step_content_assert import APIAssertsContentStrategy
from .step_content_condition import APIConditionContentStrategy
from .step_content_db import APIDBContentStrategy
from .step_content_group import APIGroupContentStrategy
from .step_content_loop import APILoopContentStrategy
from .step_content_script import APIScriptContentStrategy
from .step_content_wait import APIWaitContentStrategy

if TYPE_CHECKING:
    from .base import StepBaseStrategy


def get_step_strategy(
    step_type: int,
    interface_executor: "InterfaceExecutor"
) -> "StepBaseStrategy":
    """
    获取步骤执行策略

    Args:
        step_type: 步骤类型
        interface_executor: 接口执行器实例

    Returns:
        对应的步骤执行策略实例

    Raises:
        Exception: 未知的步骤类型
    """
    strategy_map = {
        CaseStepContentType.STEP_API: APIStepContentStrategy,
        CaseStepContentType.STEP_API_GROUP: APIGroupContentStrategy,
        CaseStepContentType.STEP_API_WAIT: APIWaitContentStrategy,
        CaseStepContentType.STEP_API_SCRIPT: APIScriptContentStrategy,
        CaseStepContentType.STEP_API_CONDITION: APIConditionContentStrategy,
        CaseStepContentType.STEP_LOOP: APILoopContentStrategy,
        CaseStepContentType.STEP_API_DB: APIDBContentStrategy,
        CaseStepContentType.STEP_API_ASSERT: APIAssertsContentStrategy,
    }

    strategy_class = strategy_map.get(step_type)

    if strategy_class is None:
        raise ValueError(f"Unknown step type: {step_type}")

    return strategy_class(interface_executor)
