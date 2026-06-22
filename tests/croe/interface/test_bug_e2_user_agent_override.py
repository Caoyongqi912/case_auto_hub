"""HttpxClient 不应硬写 user-agent, 应支持 default_user_agent 入参,"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import inspect
import pytest

from common.httpxClient import HttpxClient
from tests.croe.interface._bug_ids import BUG_E2

REPO_ROOT = Path(__file__).resolve().parents[3]

def _client_src() -> str:
    return (REPO_ROOT / "common/httpxClient.py").read_text(encoding="utf-8")

@pytest.fixture
def bug_e2_marker():
    return BUG_E2

# --------------------------------------------------------------------------- #
# E2.1 - 源码层: 写死 magic string 应消失
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_bug_e2_no_magic_user_agent_in_source(bug_e2_marker):
    """HttpxClient 不应再写死 'case_Hub_http/v0.1' user-agent。"""
    src = _client_src()

    code_lines = [
        ln for ln in src.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    code_blob = "\n".join(code_lines)
    assert "case_Hub_http/v0.1" not in code_blob, (
        f"[{BUG_E2}] 写死的 user-agent 'case_Hub_http/v0.1' 仍在代码 (非注释) 中。"
    )
    assert "DEFAULT_HEADERS" not in code_blob, (
        f"[{BUG_E2}] class 级 DEFAULT_HEADERS 还在, 应改为 default_user_agent 入参。"
    )

@pytest.mark.unit
def test_bug_e2_default_user_agent_param_exists(bug_e2_marker):
    """HttpxClient.__init__ 应该有 default_user_agent 入参。"""
    sig = inspect.signature(HttpxClient.__init__)
    assert "default_user_agent" in sig.parameters, (
        f"[{BUG_E2}] HttpxClient.__init__ 应新增 default_user_agent 入参。"
    )

# --------------------------------------------------------------------------- #
# E2.2 / E2.3 - 行为层
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_bug_e2_no_default_user_agent_means_empty_client_headers(bug_e2_marker):
    """不传 default_user_agent: client headers 不含 user-agent。"""
    c = HttpxClient()
    cfg = c._client_config
    assert "headers" in cfg
    assert "user-agent" not in cfg["headers"], (
        f"[{BUG_E2}] 不传 default_user_agent 时不应注入 user-agent 到 client headers。"
    )

@pytest.mark.unit
def test_bug_e2_with_default_user_agent_sets_client_header(bug_e2_marker):
    """传 default_user_agent='case_Hub/1.0': client headers 注入 user-agent。"""
    c = HttpxClient(default_user_agent="case_Hub/1.0")
    cfg = c._client_config
    assert cfg["headers"].get("user-agent") == "case_Hub/1.0", (
        f"[{BUG_E2}] 传 default_user_agent 时 client headers 应注入 user-agent。"
    )

@pytest.mark.unit
def test_bug_e2_runtime_request_headers_pass_through(bug_e2_marker):
    """[
    httpx 合并规则: 单次 request 的 headers 覆盖 client.headers 同名 key。
    锁住 'User-Agent 透传' 这个行为, 用户配 interface_headers['User-Agent'] = 'X'
    时,  X 必须原样到达 self.client.request(headers=...)。
    """
    import asyncio

    c = HttpxClient(default_user_agent="case_Hub/1.0")
    # 注入 mock client, 跳过真实 AsyncClient 创建
    mock_request = MagicMock()
    async def fake_request(method, url, **kwargs):
        mock_request.kwargs = kwargs
        r = MagicMock()
        r.status_code = 200
        return r
    c._client = MagicMock()
    c._client.request = fake_request
    c._client.aclose = MagicMock()

    async def run():
        return await c(
            method="GET",
            url="http://example.com",
            headers={"User-Agent": "overridden/9.9"},
        )

    asyncio.run(run())

    assert mock_request.kwargs["headers"]["User-Agent"] == "overridden/9.9", (
        f"[{BUG_E2}] request headers 的 User-Agent 没透传, "
        f"实际 {mock_request.kwargs.get('headers')}"
    )

@pytest.mark.unit
def test_bug_e2_no_default_user_agent_keeps_runtime_user_agent(bug_e2_marker):
    """不传 default_user_agent: runtime headers 的 User-Agent 仍能透传。"""
    import asyncio

    c = HttpxClient()  # 不传 default_user_agent
    mock_request = MagicMock()
    async def fake_request(method, url, **kwargs):
        mock_request.kwargs = kwargs
        r = MagicMock()
        r.status_code = 200
        return r
    c._client = MagicMock()
    c._client.request = fake_request
    c._client.aclose = MagicMock()

    async def run():
        return await c(
            method="POST",
            url="http://example.com",
            headers={"User-Agent": "agent/2.0", "X-Custom": "1"},
        )

    asyncio.run(run())

    sent = mock_request.kwargs["headers"]
    assert sent["User-Agent"] == "agent/2.0"
    assert sent["X-Custom"] == "1"
