"""
step_content/__init__.py 单测覆盖率补充 (目标 69% -> 100%)。

测 get_step_strategy 的 8+1 路径:
1. 8 个 CaseStepContentType -> 8 个 Strategy 类
2. 未知 step_type -> raise ValueError
3. 快照测试: strategy_map 覆盖所有 CaseStepContentType (防漏 type)

策略类用 isinstance 锁住继承链, 防止把 strategy_map 改坏。
"""
from unittest.mock import MagicMock

import pytest

from croe.interface.executor.step_content import get_step_strategy
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.interface.executor.step_content.step_content_api import APIStepContentStrategy
from croe.interface.executor.step_content.step_content_assert import APIAssertsContentStrategy
from croe.interface.executor.step_content.step_content_condition import APIConditionContentStrategy
from croe.interface.executor.step_content.step_content_db import APIDBContentStrategy
from croe.interface.executor.step_content.step_content_group import APIGroupContentStrategy
from croe.interface.executor.step_content.step_content_loop import APILoopContentStrategy
from croe.interface.executor.step_content.step_content_script import APIScriptContentStrategy
from croe.interface.executor.step_content.step_content_wait import APIWaitContentStrategy
from enums.CaseEnum import CaseStepContentType


def _executor_stub():
    return MagicMock(name="interface_executor")


@pytest.mark.unit
def test_get_step_strategy_api_returns_api_strategy():
    """STEP_API (1) -> APIStepContentStrategy."""
    strategy = get_step_strategy(CaseStepContentType.STEP_API, _executor_stub())
    assert isinstance(strategy, APIStepContentStrategy)
    assert isinstance(strategy, StepBaseStrategy)


@pytest.mark.unit
def test_get_step_strategy_api_group_returns_group_strategy():
    """STEP_API_GROUP (2) -> APIGroupContentStrategy."""
    strategy = get_step_strategy(CaseStepContentType.STEP_API_GROUP, _executor_stub())
    assert isinstance(strategy, APIGroupContentStrategy)


@pytest.mark.unit
def test_get_step_strategy_api_condition_returns_condition_strategy():
    """STEP_API_CONDITION (3) -> APIConditionContentStrategy."""
    strategy = get_step_strategy(CaseStepContentType.STEP_API_CONDITION, _executor_stub())
    assert isinstance(strategy, APIConditionContentStrategy)


@pytest.mark.unit
def test_get_step_strategy_api_script_returns_script_strategy():
    """STEP_API_SCRIPT (4) -> APIScriptContentStrategy."""
    strategy = get_step_strategy(CaseStepContentType.STEP_API_SCRIPT, _executor_stub())
    assert isinstance(strategy, APIScriptContentStrategy)


@pytest.mark.unit
def test_get_step_strategy_api_db_returns_db_strategy():
    """STEP_API_DB (5) -> APIDBContentStrategy."""
    strategy = get_step_strategy(CaseStepContentType.STEP_API_DB, _executor_stub())
    assert isinstance(strategy, APIDBContentStrategy)


@pytest.mark.unit
def test_get_step_strategy_api_wait_returns_wait_strategy():
    """STEP_API_WAIT (6) -> APIWaitContentStrategy."""
    strategy = get_step_strategy(CaseStepContentType.STEP_API_WAIT, _executor_stub())
    assert isinstance(strategy, APIWaitContentStrategy)


@pytest.mark.unit
def test_get_step_strategy_api_assert_returns_assert_strategy():
    """STEP_API_ASSERT (8) -> APIAssertsContentStrategy."""
    strategy = get_step_strategy(CaseStepContentType.STEP_API_ASSERT, _executor_stub())
    assert isinstance(strategy, APIAssertsContentStrategy)


@pytest.mark.unit
def test_get_step_strategy_loop_returns_loop_strategy():
    """STEP_LOOP (9) -> APILoopContentStrategy."""
    strategy = get_step_strategy(CaseStepContentType.STEP_LOOP, _executor_stub())
    assert isinstance(strategy, APILoopContentStrategy)


@pytest.mark.unit
def test_get_step_strategy_unknown_type_raises_value_error():
    """未知 step_type (不在 enum / 不在 strategy_map): raise ValueError 含 type 数值。"""
    # 用 999 这种不可能在 enum 里的数
    with pytest.raises(ValueError, match="Unknown step type: 999"):
        get_step_strategy(999, _executor_stub())


@pytest.mark.unit
def test_get_step_strategy_passes_executor_to_strategy():
    """interface_executor 实例透传给 strategy.__init__, 保存在 self.interface_executor。"""
    executor = _executor_stub()
    strategy = get_step_strategy(CaseStepContentType.STEP_API, executor)
    assert strategy.interface_executor is executor


@pytest.mark.unit
def test_get_step_strategy_map_covers_all_enum_values():
    """快照测试: strategy_map 必须覆盖 CaseStepContentType 全部 8 个 enum 值。
    防止新增 enum value 但忘了注册 strategy (这种 bug 跑业务时才会崩)。
    """
    # 直接 import strategy_map 不行, 它是局部变量; 走 introspect 路径
    # 全部 enum 都应该成功
    for step_type in CaseStepContentType:
        strategy = get_step_strategy(step_type, _executor_stub())
        assert isinstance(strategy, StepBaseStrategy)
