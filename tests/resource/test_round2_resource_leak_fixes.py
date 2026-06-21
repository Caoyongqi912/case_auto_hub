"""Round 2 资源泄漏审计回归测试: BUG-RES-1

锁定行为:
- BUG-RES-1: InterfaceExecutor / HttpxClient 资源管理
  - 加了 __aenter__ / __aexit__ 上下文支持
  - aclose() 之后 self.http 置 None (幂等)
  - play_interface_strategy 必须用 async with (否则会泄漏 httpx 连接池)
"""
import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest


# --------------------------------------------------------------------------- #
# BUG-RES-1: InterfaceExecutor async with + 幂等 close
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_interface_executor_supports_async_with():
    """[BUG-RES-1] InterfaceExecutor 必须支持 async with 自动 aclose."""
    from croe.interface.executor.interface_executor import InterfaceExecutor
    assert hasattr(InterfaceExecutor, "__aenter__"), "InterfaceExecutor 缺 __aenter__"
    assert hasattr(InterfaceExecutor, "__aexit__"), "InterfaceExecutor 缺 __aexit__"
    assert inspect.iscoroutinefunction(InterfaceExecutor.__aenter__)
    assert inspect.iscoroutinefunction(InterfaceExecutor.__aexit__)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_interface_executor_async_with_closes_httpx():
    """[BUG-RES-1] async with 退出时必须调 http.close()."""
    from croe.interface.executor.interface_executor import InterfaceExecutor

    fake_starter = MagicMock()
    fake_starter.send = AsyncMock()
    fake_vm = MagicMock()
    async with InterfaceExecutor(starter=fake_starter, variable_manager=fake_vm) as ie:
        mock_http = MagicMock()
        mock_http.close = AsyncMock()
        ie.http = mock_http
        assert ie.http is not None
    mock_http.close.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_interface_executor_aclose_is_idempotent():
    """[BUG-RES-1] aclose() 多次调用幂等 (不抛错)。"""
    from croe.interface.executor.interface_executor import InterfaceExecutor
    ie = InterfaceExecutor(starter=MagicMock(send=AsyncMock()), variable_manager=MagicMock())
    mock_http = MagicMock()
    mock_http.close = AsyncMock()
    ie.http = mock_http
    await ie.aclose()
    await ie.aclose()
    assert ie.http is None
    assert mock_http.close.await_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_interface_executor_async_with_closes_on_exception():
    """[BUG-RES-1] async with 块内抛错, 仍要 aclose。"""
    from croe.interface.executor.interface_executor import InterfaceExecutor
    ie = InterfaceExecutor(starter=MagicMock(send=AsyncMock()), variable_manager=MagicMock())
    mock_http = MagicMock()
    mock_http.close = AsyncMock()
    ie.http = mock_http

    with pytest.raises(RuntimeError, match="boom"):
        async with ie:
            raise RuntimeError("boom")
    mock_http.close.assert_awaited_once()
    assert ie.http is None


# --------------------------------------------------------------------------- #
# BUG-RES-1: play_interface_strategy 必须 async with
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_play_interface_strategy_uses_async_with():
    """[BUG-RES-1] PlayInterfaceContentStrategy.execute 必须 async with 包裹 InterfaceExecutor.

    旧代码: 直接 interface_executor = InterfaceExecutor(...), 异常路径不 aclose,
    每次执行都泄漏一个 httpx 连接池。
    """
    import re
    from pathlib import Path
    src = Path("croe/play/executor/step_content_strategy/play_interface_strategy.py").read_text()
    assert "async with InterfaceExecutor" in src, (
        "[BUG-RES-1] PlayInterfaceContentStrategy 必须用 async with 包裹 InterfaceExecutor"
    )
    assert not re.search(r"^\s*interface_executor\s*=\s*InterfaceExecutor\(", src, re.MULTILINE), (
        "[BUG-RES-1] 残留裸 InterfaceExecutor 赋值, 改用 async with"
    )
