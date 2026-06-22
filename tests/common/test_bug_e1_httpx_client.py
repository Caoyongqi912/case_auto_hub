"""`HttpxClient` 资源管理 + timeout 不再污染共享 client。"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from common.httpxClient import HttpxClient
from tests.croe.interface._bug_ids import BUG_E1

@pytest.fixture
def bug_e1_marker():
    return BUG_E1

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_e1_client_close_releases_resource(bug_e1_marker):
    """close() 应当真正调用底层 client.aclose()。"""
    client = HttpxClient()
    # 触发懒初始化
    _ = client.client
    # mock aclose (保留引用,因为 close() 之后 _client 会被置 None)
    mock_aclose = AsyncMock()
    client._client.aclose = mock_aclose

    await client.close()

    mock_aclose.assert_awaited_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_e1_timeout_passed_per_request_not_mutate_client(bug_e1_marker):
    """__call__ 不应直接修改 self.client.timeout。"""
    client = HttpxClient()
    _ = client.client
    original_timeout = client._client.timeout

    with patch.object(client._client, "request", new=AsyncMock(return_value=MagicMock())) as mock_req:
        await client(method="GET", url="http://x", read=3, connect=2)

    # 关键断言:client.timeout 保持原样(不修改)
    assert client._client.timeout is original_timeout, (
        f"[{BUG_E1}] __call__ 不应修改 self.client.timeout"
    )
    # 关键断言:request 被以 timeout 参数调用
    call_kwargs = mock_req.call_args.kwargs
    assert "timeout" in call_kwargs, f"[{BUG_E1}] request 应接收 timeout 形参,实际 kwargs: {call_kwargs}"
