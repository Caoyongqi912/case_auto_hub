"""InterfaceExecutor.execute 返回 InterfaceResult, 不再 (Dict, bool) tuple 或 Dict。"""

import inspect
import pytest
from unittest.mock import MagicMock

from app.model.interfaceAPIModel.interfaceResultModel import InterfaceResult
from croe.interface.executor.interface_executor import InterfaceExecutor
from tests.croe.interface._bug_ids import BUG_E6


@pytest.fixture
def bug_e6_marker():
    return BUG_E6


def _make_ctx(success: bool = True) -> MagicMock:
    """构造一个 mock ExecutionContext, 包含 from_execution_context 需要的字段。"""
    ctx = MagicMock()
    ctx.success = success
    ctx.start_time = "2026-06-19 10:00:00"
    ctx.interface = MagicMock()
    ctx.interface.id = 1
    ctx.interface.interface_name = "test_api"
    ctx.interface.uid = "uid-1"
    ctx.interface.interface_desc = "test"
    ctx.interface.interface_method = "GET"
    ctx.interface.interface_body_type = 0
    ctx.interface.env_id = 1
    ctx.env = None
    ctx.resolved_url = "http://example.com"
    ctx.request_info = {}
    ctx.error = None
    ctx.response = None
    ctx.extracted_vars = []
    ctx.asserts = []
    return ctx


@pytest.mark.unit
def test_bug_e6_from_execution_context_returns_interface_result(bug_e6_marker):
    """from_execution_context 必须返回 InterfaceResult 实例, 不再 dict/tuple。"""
    ctx = _make_ctx(success=True)
    result = InterfaceResult.from_execution_context(
        ctx,
        starter_id=10,
        starter_name="alice",
    )
    assert isinstance(result, InterfaceResult), (
        f"[{BUG_E6}] from_execution_context 必须返回 InterfaceResult, "
        f"实际 {type(result).__name__}"
    )
    assert not isinstance(result, tuple), (
        f"[{BUG_E6}] 不能再是 tuple, 那会回到 (Dict, bool) 歧义"
    )


@pytest.mark.unit
def test_bug_e6_from_execution_context_contains_result_field(bug_e6_marker):
    """返回的 InterfaceResult 必须包含 result 属性, 跟 ctx.success 对应。"""
    # Success case
    ctx = _make_ctx(success=True)
    result = InterfaceResult.from_execution_context(
        ctx,
        starter_id=10,
        starter_name="alice",
    )
    assert result.result is True, (
        f"[{BUG_E6}] success=True 时, result.result 应为 True, 实际 {result.result}"
    )

    # Failure case
    ctx = _make_ctx(success=False)
    result = InterfaceResult.from_execution_context(
        ctx,
        starter_id=10,
        starter_name="alice",
    )
    assert result.result is False, (
        f"[{BUG_E6}] success=False 时, result.result 应为 False, 实际 {result.result}"
    )


@pytest.mark.unit
def test_bug_e6_execute_signature_returns_interface_result(bug_e6_marker):
    """InterfaceExecutor.execute 的签名应返回 InterfaceResult, 不是 Dict/Tuple。"""
    sig = inspect.signature(InterfaceExecutor.execute)
    anno = sig.return_annotation
    # 注解可能是 InterfaceResult 或 "InterfaceResult"
    anno_str = str(anno)
    assert "InterfaceResult" in anno_str, (
        f"[{BUG_E6}] execute() 返回类型注解必须是 InterfaceResult, 实际 {anno_str}"
    )
    assert "Tuple" not in anno_str, (
        f"[{BUG_E6}] execute() 不应再标 Tuple, 实际 {anno_str}"
    )
    assert "Dict" not in anno_str, (
        f"[{BUG_E6}] execute() 不应再标 Dict, 实际 {anno_str}"
    )
