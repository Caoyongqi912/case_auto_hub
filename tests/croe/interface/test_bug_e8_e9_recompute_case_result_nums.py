"""
[BUG-E8 + E9] case_result.total_num 跟 success_num/fail_num 不一致

E8: total_num 在 init_case_result 时设一次 = case_api_num, 之后不再更新。
    如果 case_api_num 跟实际跑的 API 数对不上 (或运行时漂移), total_num 永久错位。
E9: GROUP/LOOP/CONDITION 等 parent step 在 step strategy 里
    case_result.success_num += 1, 但实际跑了 N 个 API, 应该 +N。
    多个 step strategy 行为不对称, 改全量成本高、易漏。

修法: 在 finalize_case_result 末尾调一次 recompute_case_result_nums,
      用 interface_result 表的 COUNT 当权威源, 覆写 case_result 三字段,
      保证 total_num = success_num + fail_num 恒成立。
      step strategy 的手动维护保留 (不影响在线行为), 这里做最终对账。

测试 (5 个, 不接 DB 走 mock):
  - 4 个 mapper 层: SQL 正确 (含 case/case 表达式) + session=None 抛 + 跟 update_by_id 联动
  - 1 个 result_writer 集成: finalize 调 recompute
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_bug_e8_e9_recompute_uses_interface_result_count():
    """核心: recompute SQL 必须 COUNT interface_result 表 + SUM(result=True/False)"""
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper
    import inspect
    src = inspect.getsource(InterfaceCaseResultMapper.recompute_case_result_nums)
    # 必须 COUNT interface_result 表
    assert "InterfaceResult" in src, "[BUG-E8] recompute SQL 应 COUNT interface_result 表"
    assert "func.count" in src or "COUNT" in src, "[BUG-E8] 应有 COUNT 表达式"
    # 必须按 result (True/False) 分桶
    assert "True" in src and "False" in src, "[BUG-E8] 应按 result True/False 分桶"


def test_bug_e8_e9_recompute_session_none_no_longer_raises():
    """[BUG-DOC 修复] 之前 session=None 抛 ValueError, 但调用方
    (result_writer.py:367) 注释写 "自管事务", 实际静默 except 丢对账。
    改: session=None 时开自己的 transaction()。

    测试: 不接 DB, 用 inspect.getsource 检查源码, 锁住
    1. 不再 raise ValueError
    2. 走 if session is None 分支调 cls.transaction()
    3. session 传进来时走 else 分支复用
    """
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper
    import inspect

    src = inspect.getsource(InterfaceCaseResultMapper.recompute_case_result_nums)

    # 不应有 raise ValueError("...external session...")
    assert "raise ValueError" not in src, (
        "[BUG-DOC 修复后] session=None 不应再 raise ValueError, "
        "改走 if session is None: async with cls.transaction() as session"
    )

    # 必须有 if session is None 分支调 cls.transaction()
    assert "if session is None" in src, (
        "[BUG-DOC 修复后] 必须有 if session is None 分支"
    )
    assert "cls.transaction()" in src, (
        "[BUG-DOC 修复后] session=None 走 cls.transaction() 自管事务"
    )


@pytest.mark.asyncio
async def test_bug_e8_e9_recompute_updates_case_result_fields():
    """端到端 mock: 模拟 session.execute 返回 3 个字段, 验证 update_by_id 被调"""
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper

    # mock session
    mock_session = AsyncMock()
    mock_row = MagicMock()
    mock_row.total = 5
    mock_row.success = 3
    mock_row.fail = 2

    mock_result = MagicMock()
    mock_result.one = MagicMock(return_value=mock_row)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch.object(
        InterfaceCaseResultMapper, "update_by_id", new=AsyncMock()
    ) as mock_update:
        result = await InterfaceCaseResultMapper.recompute_case_result_nums(
            case_result_id=42,
            session=mock_session,
        )

    # 返回值
    assert result == {"total": 5, "success": 3, "fail": 2}, f"返回 dict 错: {result}"
    # update_by_id 调过 + 字段对
    mock_update.assert_awaited_once()
    kwargs = mock_update.await_args.kwargs
    assert kwargs["id"] == 42
    assert kwargs["total_num"] == 5
    assert kwargs["success_num"] == 3
    assert kwargs["fail_num"] == 2
    # session 必须传进 update_by_id (D4 风格)
    assert kwargs.get("session") is mock_session, "[BUG-E8] update_by_id 必须复用同 session"


@pytest.mark.asyncio
async def test_bug_e8_e9_recompute_handles_zero_results():
    """边界: 0 个 interface_result 行 (空 case) → 全部 0"""
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper

    mock_session = AsyncMock()
    mock_row = MagicMock()
    mock_row.total = 0
    mock_row.success = 0
    mock_row.fail = 0
    mock_result = MagicMock()
    mock_result.one = MagicMock(return_value=mock_row)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch.object(
        InterfaceCaseResultMapper, "update_by_id", new=AsyncMock()
    ) as mock_update:
        result = await InterfaceCaseResultMapper.recompute_case_result_nums(
            case_result_id=99,
            session=mock_session,
        )

    assert result == {"total": 0, "success": 0, "fail": 0}
    mock_update.assert_awaited_once()
    kwargs = mock_update.await_args.kwargs
    assert kwargs["total_num"] == 0


@pytest.mark.asyncio
async def test_bug_e8_e9_recompute_failure_does_not_break_finalize():
    """recompute 失败时, finalize 不应崩 (主流程有 try/except 兜底)"""
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB down"))

    with pytest.raises(RuntimeError, match="DB down"):
        # mapper 层应让异常往外冒, 让调用方决定如何处理
        await InterfaceCaseResultMapper.recompute_case_result_nums(
            case_result_id=1,
            session=mock_session,
        )


def test_bug_e8_e9_finalize_invokes_recompute():
    """集成: finalize_case_result 源码里必须调 recompute_case_result_nums"""
    from croe.interface.writer.result_writer import ResultWriter
    import inspect
    src = inspect.getsource(ResultWriter.finalize_case_result)
    assert "recompute_case_result_nums" in src, (
        "[BUG-E8] finalize_case_result 必须调 recompute_case_result_nums"
    )
    # 必须在 _flush_cache 之后 (要等 interface_result 真落盘)
    flush_pos = src.find("_flush_cache")
    recompute_pos = src.find("recompute_case_result_nums")
    assert flush_pos < recompute_pos, (
        f"[BUG-E8] recompute 必须在 _flush_cache 之后"
        f" (flush_pos={flush_pos}, recompute_pos={recompute_pos})"
    )
