"""`hub_api_request` 不应在 async 上下文里阻塞事件循环。"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from croe.a_manager.script_manager import ScriptManager
from tests.croe.interface._bug_ids import BUG_V4

@pytest.fixture
def bug_v4_marker():
    return BUG_V4

@pytest.mark.unit
def test_bug_v4_uses_async_httpx_under_the_hood(bug_v4_marker):
    """_hub_api_request 内部应走 httpx.AsyncClient,不是同步 Client。"""
    # 抓模块里 import 走的地方
    import inspect
    from croe.a_manager.script_manager import ScriptManager
    src = inspect.getsource(ScriptManager._hub_api_request)
    # 同步 Client 不应再出现
    assert "httpx.Client" not in src, (
        f"[{BUG_V4}] _hub_api_request 仍使用同步 httpx.Client,"
        f"应改 httpx.AsyncClient"
    )
    # 异步 Client 应当出现
    assert "httpx.AsyncClient" in src or "AsyncClient" in src, (
        f"[{BUG_V4}] _hub_api_request 应改用 httpx.AsyncClient"
    )

@pytest.mark.unit
def test_bug_v4_returns_parsed_json(bug_v4_marker):
    """正常路径:返回 JSON 解析结果。"""
    # 模拟整个异步请求链路
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.headers = {"content-type": "application/json"}
    fake_response.json.return_value = {"ok": True}
    fake_response.raise_for_status = MagicMock()

    async def fake_request(self, method, url, **kwargs):
        return fake_response

    with patch("httpx.AsyncClient.request", new=fake_request), \
         patch("croe.a_manager.script_manager._check_ssrf"):
        result = ScriptManager._hub_api_request("http://example.com")
    assert result == {"ok": True}, f"期望 {{'ok': True}},实际 {result!r}"

@pytest.mark.unit
def test_bug_v4_returns_text_for_non_json(bug_v4_marker):
    """非 JSON 响应应返回 text。"""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.headers = {"content-type": "text/html"}
    fake_response.text = "<html>hi</html>"
    fake_response.raise_for_status = MagicMock()

    async def fake_request(self, method, url, **kwargs):
        return fake_response

    with patch("httpx.AsyncClient.request", new=fake_request), \
         patch("croe.a_manager.script_manager._check_ssrf"):
        result = ScriptManager._hub_api_request("http://example.com")
    assert result == "<html>hi</html>", f"期望 text,实际 {result!r}"

@pytest.mark.unit
def test_bug_v4_returns_none_on_error(bug_v4_marker):
    """失败时仍应返回 None(原版行为,不强求抛)。"""

    async def fake_request(self, method, url, **kwargs):
        raise RuntimeError("network down")

    with patch("httpx.AsyncClient.request", new=fake_request), \
         patch("croe.a_manager.script_manager._check_ssrf"):
        result = ScriptManager._hub_api_request("http://example.com")
    assert result is None, f"失败应返回 None,实际 {result!r}"
