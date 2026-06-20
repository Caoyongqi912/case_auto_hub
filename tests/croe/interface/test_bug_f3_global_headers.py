"""BUG-F3 回归测试:`init_global_headers` 成功分支:"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.model.interfaceAPIModel.interfaceGlobalModel import InterfaceGlobalHeader
from croe.interface.runner import InterfaceRunner
from tests.croe.interface._bug_ids import BUG_F3

@pytest.fixture
def bug_f3_marker():
    return BUG_F3

def _make_starter():
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.username = "u"
    starter.userId = 1
    starter.uid = "u-1"
    starter.logs = []
    return starter

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f3_global_headers_actually_applied_to_executor(bug_f3_marker):
    """[BUG-F3] init_global_headers 加载后,executor.g_headers 应当有值。"""
    runner = InterfaceRunner(starter=_make_starter())

    h1 = InterfaceGlobalHeader(id=1, key="X-Token", value="abc", project_id=1)
    h2 = InterfaceGlobalHeader(id=2, key="X-App", value="case_hub", project_id=1)

    with patch(
        "app.mapper.interfaceApi.interfaceGlobalMapper.InterfaceGlobalHeaderMapper.query_all",
        new=AsyncMock(return_value=[h1, h2]),
    ):
        await runner.init_global_headers()

    # 关键断言:executor.g_headers 应有这 2 个 header
    assert len(runner.interface_executor.g_headers) == 2, (
        f"[{BUG_F3}] executor.g_headers 应有 2 个全局 header,"
        f"实际 {len(runner.interface_executor.g_headers)}"
    )
    keys = {h.key for h in runner.interface_executor.g_headers}
    assert keys == {"X-Token", "X-App"}, f"keys 错了: {keys}"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f3_global_headers_log_message_uses_actual_count(bug_f3_marker):
    """[BUG-F3] send 出去的日志应反映实际加载数量,而不是 self.global_headers (恒为 0)。"""
    runner = InterfaceRunner(starter=_make_starter())
    h1 = InterfaceGlobalHeader(id=1, key="X-Token", value="abc", project_id=1)

    with patch(
        "app.mapper.interfaceApi.interfaceGlobalMapper.InterfaceGlobalHeaderMapper.query_all",
        new=AsyncMock(return_value=[h1]),
    ):
        await runner.init_global_headers()

    # 找到包含 "已加载" 的 send 调用,断言里面有 "1 条"(而不是 "0 条")
    found = False
    for call in runner.starter.send.call_args_list:
        msg = str(call.args[0]) if call.args else ""
        if "已加载" in msg and "1" in msg:
            found = True
            break
    assert found, (
        f"[{BUG_F3}] send 出去的日志应反映实际加载 1 条 header,"
        f"实际调用: {runner.starter.send.call_args_list}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f3_global_headers_empty(bug_f3_marker):
    """[BUG-F3] 全局 header 为空时,executor.g_headers 应为空列表(不报错)。"""
    runner = InterfaceRunner(starter=_make_starter())

    with patch(
        "app.mapper.interfaceApi.interfaceGlobalMapper.InterfaceGlobalHeaderMapper.query_all",
        new=AsyncMock(return_value=[]),
    ):
        await runner.init_global_headers()

    assert runner.interface_executor.g_headers == []
