"""_build_result 返回 Dict, 不再 (Dict, bool) tuple。"""

import pytest
from unittest.mock import MagicMock

from croe.interface.executor.interface_executor import InterfaceExecutor
from tests.croe.interface._bug_ids import BUG_E6

@pytest.fixture
def bug_e6_marker():
    return BUG_E6

def _make_ctx(success: bool = True) -> MagicMock:
    """构造一个 mock ExecutionContext, 包含 _build_result 需要的字段。"""
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
    ctx.env = None
    ctx.resolved_url = "http://example.com"
    ctx.request_info = {}
    ctx.error = None
    ctx.response = None
    ctx.extracted_vars = []
    ctx.asserts = []
    return ctx

@pytest.mark.unit
def test_bug_e6_build_result_returns_dict_not_tuple(bug_e6_marker):
    """_build_result 必须返回 Dict, 不再 (Dict, bool)。"""
    executor = InterfaceExecutor.__new__(InterfaceExecutor)
    executor.starter = MagicMock()
    ctx = _make_ctx(success=True)
    result = executor._build_result(ctx)
    assert isinstance(result, dict), (
        f"[{BUG_E6}] _build_result 必须返回 Dict, 实际 {type(result).__name__}"
    )
    assert not isinstance(result, tuple), (
        f"[{BUG_E6}] 不能再是 tuple, 那会回到 (Dict, bool) 歧义"
    )

@pytest.mark.unit
def test_bug_e6_build_result_contains_result_field(bug_e6_marker):
    """返回的 dict 必须包含 'result' 字段, 跟 ctx.success 对应。"""
    executor = InterfaceExecutor.__new__(InterfaceExecutor)
    executor.starter = MagicMock()

    # Success case
    ctx = _make_ctx(success=True)
    result = executor._build_result(ctx)
    assert result.get("result") is True, (
        f"[{BUG_E6}] success=True 时, result['result'] 应为 True, 实际 {result.get('result')}"
    )

    # Failure case
    ctx = _make_ctx(success=False)
    result = executor._build_result(ctx)
    assert result.get("result") is False, (
        f"[{BUG_E6}] success=False 时, result['result'] 应为 False, 实际 {result.get('result')}"
    )

@pytest.mark.unit
def test_bug_e6_execute_signature_returns_dict(bug_e6_marker):
    """InterfaceExecutor.execute 的签名应返回 Dict, 不是 Tuple。"""
    import inspect
    sig = inspect.signature(InterfaceExecutor.execute)
    anno = sig.return_annotation
    # 注解可能是 typing.Dict[...] 或 dict
    anno_str = str(anno)
    assert "Dict" in anno_str or "dict" in anno_str, (
        f"[{BUG_E6}] execute() 返回类型注解必须是 Dict, 实际 {anno_str}"
    )
    assert "Tuple" not in anno_str, (
        f"[{BUG_E6}] execute() 不应再标 Tuple, 实际 {anno_str}"
    )
