"""Round 3 并发与竞态回归测试: BUG-CON-2 / BUG-CON-3 / BUG-CON-4

锁定行为:
- BUG-CON-2: socketio disconnect 必须清理 clientIds (避免泄漏 + 旧 sid 残留)
- BUG-CON-3: clientIds 是 instance variable, 不是 class variable
- BUG-CON-4: 同一 clientId 重复 connect, 旧 sid 必须让位 (不能发到错误 sid)
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from urllib.parse import urlencode


# --------------------------------------------------------------------------- #
# BUG-CON-3: clientIds 是 instance variable
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_clientids_is_instance_variable():
    """[BUG-CON-3] clientIds 不能是 class variable, 否则跨实例共享。"""
    from app.ws.io import AsyncIOServerManager
    a = AsyncIOServerManager()
    b = AsyncIOServerManager()
    a.clientIds["c1"] = "s1"
    assert b.clientIds == {}, "clientIds 是 class variable, 跨实例污染"


# --------------------------------------------------------------------------- #
# BUG-CON-2: connect 记录反向索引, disconnect 时清理
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.asyncio
async def test_connect_records_reverse_index():
    """[BUG-CON-2] connect 时除写 clientIds, 还写 _sid_to_client 反向索引。"""
    from app.ws.io import async_io, api_namespace_connect
    async_io.clientIds.clear()
    async_io._sid_to_client.clear()
    qs = urlencode({"clientId": "user_A"})
    await api_namespace_connect(sid="sid_1", env={"QUERY_STRING": qs})
    assert async_io.clientIds["user_A"] == "sid_1"
    assert async_io._sid_to_client["sid_1"] == "user_A"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_disconnect_cleans_clientids():
    """[BUG-CON-2] disconnect 必须把 clientId 从 clientIds 里删掉, 防泄漏。"""
    from app.ws.io import async_io, api_namespace_connect, api_namespace_disconnect
    async_io.clientIds.clear()
    async_io._sid_to_client.clear()
    qs = urlencode({"clientId": "user_B"})
    await api_namespace_connect(sid="sid_2", env={"QUERY_STRING": qs})
    assert "user_B" in async_io.clientIds
    await api_namespace_disconnect(sid="sid_2")
    assert "user_B" not in async_io.clientIds, (
        "[BUG-CON-2] disconnect 后 clientId 仍残留在 clientIds, 内存泄漏"
    )
    assert "sid_2" not in async_io._sid_to_client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_disconnect_does_not_remove_other_clients():
    """[BUG-CON-2] disconnect 一个 sid 不该误删别的 clientId。"""
    from app.ws.io import async_io, api_namespace_connect, api_namespace_disconnect
    async_io.clientIds.clear()
    async_io._sid_to_client.clear()
    # 同一 user 用 2 个 tab 连进来
    qs1 = urlencode({"clientId": "user_C"})
    qs2 = urlencode({"clientId": "user_D"})
    await api_namespace_connect(sid="sid_a", env={"QUERY_STRING": qs1})
    await api_namespace_connect(sid="sid_b", env={"QUERY_STRING": qs2})
    await api_namespace_disconnect(sid="sid_a")
    assert "user_C" not in async_io.clientIds
    assert "user_D" in async_io.clientIds
    assert async_io.clientIds["user_D"] == "sid_b"


# --------------------------------------------------------------------------- #
# BUG-CON-4: 同一 clientId 重复 connect 旧 sid 让位
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.asyncio
async def test_duplicate_connect_evicts_old_sid():
    """[BUG-CON-4] 同一 clientId 二次 connect, 旧 sid 必须从 _sid_to_client 移除。"""
    from app.ws.io import async_io, api_namespace_connect
    async_io.clientIds.clear()
    async_io._sid_to_client.clear()
    qs = urlencode({"clientId": "user_E"})
    await api_namespace_connect(sid="old_sid", env={"QUERY_STRING": qs})
    await api_namespace_connect(sid="new_sid", env={"QUERY_STRING": qs})
    # 新的覆盖
    assert async_io.clientIds["user_E"] == "new_sid"
    # 旧 sid 不应再在反向索引里
    assert "old_sid" not in async_io._sid_to_client
    # 新 sid 必须在反向索引里
    assert async_io._sid_to_client["new_sid"] == "user_E"
