"""InterfaceResult.from_execution_context 工厂方法回归测试"""

from datetime import datetime
from unittest.mock import MagicMock

import httpx
import pytest

from app.model.interfaceAPIModel.interfaceModel import Interface
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceResult
from croe.interface.executor.interface_executor import ExecutionContext


@pytest.mark.unit
def test_from_execution_context_success_response():
    """正常响应时，from_execution_context 字段映射正确。"""
    interface = MagicMock(spec=Interface)
    interface.id = 1
    interface.interface_name = "login"
    interface.uid = "uid-1"
    interface.interface_desc = "登录"
    interface.interface_method = "POST"
    interface.interface_body_type = 1
    interface.env_id = 3

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.text = '{"ok": true}'
    response.headers = {"content-type": "application/json"}
    response.elapsed.total_seconds.return_value = 0.123

    ctx = ExecutionContext(
        interface=interface,
        resolved_url="http://example.com/login",
        request_info={"json": {"user": "admin"}, "headers": {"X": "1"}},
        response=response,
        extracted_vars=[{"key": "token", "value": "abc"}],
        asserts=[{"result": True}],
        start_time="2026-06-22 12:00:00",
    )

    result = InterfaceResult.from_execution_context(
        ctx, starter_id=42, starter_name="tester"
    )

    assert result.interface_id == 1
    assert result.interface_name == "login"
    assert result.starter_id == 42
    assert result.starter_name == "tester"
    assert result.request_url == "http://example.com/login"
    assert result.request_method == "POST"
    assert result.response_status == 200
    assert result.response_text == '{"ok": true}'
    assert result.result is True
    assert result.use_time == "123.0"


@pytest.mark.unit
def test_from_execution_context_error_response():
    """执行异常时，result 为 False，response_status 为 500。"""
    interface = MagicMock(spec=Interface)
    interface.id = 2
    interface.interface_name = "err"
    interface.uid = "uid-2"
    interface.interface_desc = None
    interface.interface_method = "GET"
    interface.interface_body_type = 0
    interface.env_id = None

    ctx = ExecutionContext(
        interface=interface,
        resolved_url="http://example.com/err",
        error="connection refused",
        start_time="2026-06-22 12:00:00",
    )

    result = InterfaceResult.from_execution_context(ctx)

    assert result.response_status == 500
    assert result.response_text == "connection refused"
    assert result.result is False
    assert result.use_time == "0"


@pytest.mark.unit
def test_from_execution_context_assert_failure_overrides_success():
    """响应成功但断言失败时，result 应为 False。"""
    interface = MagicMock(spec=Interface)
    interface.id = 3
    interface.interface_name = "assert"
    interface.uid = "uid-3"
    interface.interface_desc = None
    interface.interface_method = "GET"
    interface.interface_body_type = 0
    interface.env_id = 1

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.text = "ok"
    response.headers = {}
    response.elapsed.total_seconds.return_value = 0.05

    ctx = ExecutionContext(
        interface=interface,
        response=response,
        asserts=[{"result": False}],
        start_time="2026-06-22 12:00:00",
    )

    result = InterfaceResult.from_execution_context(ctx)
    assert result.result is False
