"""
BUG-D4 回归测试:`bulk_insert_models` / `bulk_insert_results` 强制要求 session,
杜绝隐式 commit 导致多张表批量操作不在同一事务。

修复要点:
- `bulk_insert_models(session)` 和 `bulk_insert_results(session)` 都会在
  session=None 时直接抛 ValueError,拒绝自开事务
- writer 的 `_flush_cache` 改用 `InterfaceResultMapper.transaction()` 单一事务
  包住两次 bulk,任一失败整体回滚

详见 docs/review/run_interface_case_deep_review.md。
"""
import contextlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceResultMapper,
    InterfaceContentStepResultMapper,
)
from croe.interface.writer.result_writer import ResultWriter
from tests.croe.interface._bug_ids import BUG_D4


@pytest.fixture
def bug_d4_marker():
    return BUG_D4


# ---- Mapper 侧: session=None 必须抛 ----

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d4_bulk_insert_models_rejects_none_session(bug_d4_marker):
    """[BUG-D4] bulk_insert_models 在 session=None 时必须抛 ValueError。"""
    fake_model = MagicMock()
    with pytest.raises(ValueError, match="external session"):
        await InterfaceResultMapper.bulk_insert_models([fake_model])
    with pytest.raises(ValueError, match="external session"):
        await InterfaceResultMapper.bulk_insert_models([fake_model], session=None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d4_bulk_insert_results_rejects_none_session(bug_d4_marker):
    """[BUG-D4] bulk_insert_results 在 session=None 时必须抛 ValueError。"""
    valid = {
        "content_type": 1,  # STEP_API
        "content_id": 1,
        "content_name": "x",
        "interface_result_id": 1,
    }
    with pytest.raises(ValueError, match="external session"):
        await InterfaceContentStepResultMapper.bulk_insert_results([valid])
    with pytest.raises(ValueError, match="external session"):
        await InterfaceContentStepResultMapper.bulk_insert_results(
            [valid], session=None
        )


# ---- Mapper 侧: 传了 session 就用传入的, 不自开事务 ----

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d4_bulk_insert_models_uses_passed_session_only(bug_d4_marker):
    """[BUG-D4] bulk_insert_models 传了 session, 不会再去开自己的 transaction。"""
    fake_model = MagicMock()
    fake_session = AsyncMock()
    fake_session.add_all = MagicMock()
    fake_session.flush = AsyncMock()

    with patch.object(InterfaceResultMapper, "transaction") as mock_tx:
        count = await InterfaceResultMapper.bulk_insert_models(
            [fake_model], session=fake_session
        )

    # 不应再走 transaction (即不再自开事务)
    assert not mock_tx.called, (
        f"[{BUG_D4}] 传了 session 不应再自开 transaction, "
        f"实际 mock_tx 被调用 {mock_tx.call_count} 次"
    )
    assert count == 1
    fake_session.add_all.assert_called_once_with([fake_model])
    fake_session.flush.assert_awaited_once()


# ---- Writer 侧: _flush_cache 用单事务, 失败整体回滚 ----

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d4_writer_flush_uses_single_transaction(bug_d4_marker):
    """[BUG-D4] _flush_cache 必须用 InterfaceResultMapper.transaction() 单事务包两次 bulk。"""
    rw = ResultWriter()
    rw.api_result_cache = []  # 空
    rw.content_result_cache = []  # 空
    rw._progress_update_cache = []

    with patch.object(InterfaceResultMapper, "transaction") as mock_tx:
        # 模拟一个空事务 context
        @contextlib.asynccontextmanager
        async def _empty_tx(*args, **kwargs):
            yield MagicMock()
        mock_tx.side_effect = _empty_tx

        await rw._flush_cache()

    # 应当至少调一次 transaction (单事务),不能为 0 次 (那就退化成无事务)
    assert mock_tx.call_count == 1, (
        f"[{BUG_D4}] _flush_cache 应使用单事务, 实际 transaction() 被调 {mock_tx.call_count} 次"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d4_writer_flush_rollback_triggers_fallback(bug_d4_marker):
    """[BUG-D4] bulk 事务失败 -> 整体回滚 -> 走 fallback 路径(降级逐条)。"""
    rw = ResultWriter()
    fake_model = MagicMock()
    rw.api_result_cache = [fake_model]
    rw.content_result_cache = []  # 空
    rw._progress_update_cache = []

    # 模拟 bulk 事务失败 (transaction 内部抛)
    @contextlib.asynccontextmanager
    async def _broken_tx(*args, **kwargs):
        raise RuntimeError("DB connection lost")
        yield  # unreachable, 让 asynccontextmanager 走 exit 时已经是异常

    with patch.object(InterfaceResultMapper, "transaction", _broken_tx), \
         patch.object(rw, "_fallback_insert_api_results", new=AsyncMock()) as mock_fallback_api, \
         patch.object(rw, "_fallback_insert_content_results", new=AsyncMock()) as mock_fallback_content:
        await rw._flush_cache()

    # 走降级路径
    mock_fallback_api.assert_awaited_once_with()
    mock_fallback_content.assert_awaited_once_with()
    # 缓存被清空
    assert rw.api_result_cache == [], f"[{BUG_D4}] 缓存应被清空"
    assert rw.content_result_cache == [], f"[{BUG_D4}] 缓存应被清空"
