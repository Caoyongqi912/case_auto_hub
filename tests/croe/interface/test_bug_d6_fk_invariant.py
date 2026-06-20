"""[BUG-D6] InterfaceResult <-> APIStepContentResult 双向 FK 漂移检测 + reconcile"""

import ast
import inspect
import re

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.mapper.interfaceApi.interfaceResultMapper import InterfaceResultMapper
from tests.croe.interface._bug_ids import BUG_D6

@pytest.fixture
def bug_d6_marker():
    return BUG_D6

# ---- session=None 强制 ----

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d6_find_fk_inconsistencies_requires_session(bug_d6_marker):
    """[BUG-D6] find_fk_inconsistencies 在 session=None 时必须抛 ValueError。"""
    with pytest.raises(ValueError, match="external session"):
        await InterfaceResultMapper.find_fk_inconsistencies(session=None)

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d6_reconcile_fk_requires_session(bug_d6_marker):
    """[BUG-D6] reconcile_fk_from_polymorphic 在 session=None 时必须抛 ValueError。"""
    with pytest.raises(ValueError, match="external session"):
        await InterfaceResultMapper.reconcile_fk_from_polymorphic(session=None)

# ---- SQL 形状锁住 ----

def _get_src(method):
    return inspect.getsource(method)

@pytest.mark.unit
def test_bug_d6_find_sql_has_three_mismatch_reasons(bug_d6_marker):
    """[BUG-D6] find_fk_inconsistencies 的 SQL CASE WHEN 必须包含 3 种 mismatch_reason。"""
    src = _get_src(InterfaceResultMapper.find_fk_inconsistencies)
    expected = {"ir_missing_fk", "api_missing_fk", "mismatch", "ok"}
    for reason in expected:
        assert f"'{reason}'" in src, (
            f"[{BUG_D6}] find_fk_inconsistencies SQL CASE WHEN 漏 {reason!r}。"
            f"\n当前 3 种漂移原因: ir_missing_fk / api_missing_fk / mismatch + ok 兜底"
        )

@pytest.mark.unit
def test_bug_d6_find_sql_joins_polymorphic_subtype(bug_d6_marker):
    """[BUG-D6] find_fk_inconsistencies SQL 必须 LEFT JOIN interface_case_content_result_api。"""
    src = _get_src(InterfaceResultMapper.find_fk_inconsistencies)
    # JOIN polymorphic 子类表 (api)
    assert "interface_case_content_result_api" in src, (
        f"[{BUG_D6}] find SQL 必须 JOIN interface_case_content_result_api "
        f"才能拿到 polymorphic 子类的 interface_result_id"
    )
    # LEFT JOIN (因为要识别 api_missing_fk: API 那边没记录)
    assert "LEFT JOIN" in src, (
        f"[{BUG_D6}] find SQL 必须 LEFT JOIN, 否则 api_missing_fk 永远不会出现"
    )

@pytest.mark.unit
def test_bug_d6_find_sql_returns_dict_with_4_fields(bug_d6_marker):
    """[BUG-D6] find_fk_inconsistencies 返回的 dict 必须有 4 个字段 (含 mismatch_reason)。"""
    src = _get_src(InterfaceResultMapper.find_fk_inconsistencies)
    # SQL SELECT 必须含 mismatch_reason + interface_result_id + 两边的 fk
    for field in (
        "interface_result_id",
        "ir_content_result_id",
        "api_interface_result_id",
        "mismatch_reason",
    ):
        assert field in src, (
            f"[{BUG_D6}] find_fk_inconsistencies SQL 缺字段 {field!r}"
        )

@pytest.mark.unit
def test_bug_d6_find_sql_case_result_id_filter_with_is_null_escape(bug_d6_marker):
    """[BUG-D6] find_fk_inconsistencies 必须支持 case_result_id=None 扫全表 (用 IS NULL 兜底)。"""
    src = _get_src(InterfaceResultMapper.find_fk_inconsistencies)
    # 标准 pattern: WHERE (xxx) AND (:case_result_id IS NULL OR ...)
    assert ":case_result_id IS NULL" in src, (
        f"[{BUG_D6}] find SQL 必须用 :case_result_id IS NULL 兜底, "
        f"允许 None=全表扫 / int=精确过滤"
    )

@pytest.mark.unit
def test_bug_d6_reconcile_sql_is_update_join(bug_d6_marker):
    """[BUG-D6] reconcile_fk_from_polymorphic 的 SQL 必须是 UPDATE JOIN 覆写 ir.content_result_id。"""
    src = _get_src(InterfaceResultMapper.reconcile_fk_from_polymorphic)
    # UPDATE ... JOIN ... SET ir.content_result_id = api.interface_result_id
    assert "UPDATE interface_result" in src, (
        f"[{BUG_D6}] reconcile 必须是 UPDATE interface_result, 不是只 SELECT"
    )
    assert "SET ir.content_result_id" in src, (
        f"[{BUG_D6}] reconcile 必须 SET ir.content_result_id = api.interface_result_id"
    )
    assert "interface_case_content_result_api" in src, (
        f"[{BUG_D6}] reconcile 必须 JOIN interface_case_content_result_api 当 source of truth"
    )

@pytest.mark.unit
def test_bug_d6_reconcile_sql_case_result_id_filter(bug_d6_marker):
    """[BUG-D6] reconcile SQL 也必须支持 case_result_id 过滤 + IS NULL 兜底。"""
    src = _get_src(InterfaceResultMapper.reconcile_fk_from_polymorphic)
    assert ":case_result_id IS NULL" in src, (
        f"[{BUG_D6}] reconcile 也必须支持 case_result_id=None 全表 / int 过滤"
    )

# ---- 端到端 mock ----

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d6_find_returns_list_of_dicts(bug_d6_marker):
    """[BUG-D6] find_fk_inconsistencies 端到端: session.execute 返回 3 行 → 返 list[dict]。"""
    mock_session = AsyncMock()
    # mock 3 种 mismatch_reason
    row1 = {"interface_result_id": 1, "ir_content_result_id": None,
            "api_interface_result_id": 1, "mismatch_reason": "ir_missing_fk"}
    row2 = {"interface_result_id": 2, "ir_content_result_id": 99,
            "api_interface_result_id": 2, "mismatch_reason": "mismatch"}
    row3 = {"interface_result_id": 3, "ir_content_result_id": 3,
            "api_interface_result_id": None, "mismatch_reason": "api_missing_fk"}
    mock_mapping = MagicMock()
    mock_mapping.all = MagicMock(return_value=[row1, row2, row3])
    mock_result = MagicMock()
    mock_result.mappings = MagicMock(return_value=mock_mapping)
    mock_session.execute = AsyncMock(return_value=mock_result)

    rows = await InterfaceResultMapper.find_fk_inconsistencies(
        case_result_id=42, session=mock_session
    )

    assert len(rows) == 3
    # 3 种 mismatch_reason 都识别了
    reasons = {r["mismatch_reason"] for r in rows}
    assert reasons == {"ir_missing_fk", "mismatch", "api_missing_fk"}, (
        f"[{BUG_D6}] 3 种漂移原因应都被识别, 实际: {reasons}"
    )
    # session.execute 被调, 拿到的 case_result_id=42
    mock_session.execute.assert_awaited_once()
    call_args = mock_session.execute.await_args
    assert call_args.args[1] == {"case_result_id": 42}, (
        f"[{BUG_D6}] case_result_id 应作为参数传入 (允许 None 全表)"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d6_find_returns_empty_list_when_no_drift(bug_d6_marker):
    """[BUG-D6] 没有漂移时, find_fk_inconsistencies 返空 list。"""
    mock_session = AsyncMock()
    mock_mapping = MagicMock()
    mock_mapping.all = MagicMock(return_value=[])
    mock_result = MagicMock()
    mock_result.mappings = MagicMock(return_value=mock_mapping)
    mock_session.execute = AsyncMock(return_value=mock_result)

    rows = await InterfaceResultMapper.find_fk_inconsistencies(session=mock_session)
    assert rows == []

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d6_reconcile_returns_rowcount(bug_d6_marker):
    """[    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_session.execute = AsyncMock(return_value=mock_result)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_scope(s=None):
        yield mock_session

    with patch.object(InterfaceResultMapper, "transaction", fake_scope):
        fixed = await InterfaceResultMapper.reconcile_fk_from_polymorphic(
            case_result_id=42, session=mock_session
        )

    assert fixed == 5, f"[{BUG_D6}] reconcile 应返 rowcount, 实际: {fixed}"
    mock_session.commit.assert_not_awaited()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d6_reconcile_handles_zero_fixes(bug_d6_marker):
    """[    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.execute = AsyncMock(return_value=mock_result)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_scope(s=None):
        yield mock_session

    with patch.object(InterfaceResultMapper, "transaction", fake_scope):
        fixed = await InterfaceResultMapper.reconcile_fk_from_polymorphic(
            session=mock_session
        )

    assert fixed == 0
    mock_session.commit.assert_not_awaited()

# ---- 异常路径 ----

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d6_find_propagates_db_errors(bug_d6_marker):
    """[BUG-D6] find_fk_inconsistencies DB 异常时往外冒, 让调用方处理。"""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("connection lost"))

    with pytest.raises(RuntimeError, match="connection lost"):
        await InterfaceResultMapper.find_fk_inconsistencies(session=mock_session)

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d6_reconcile_propagates_db_errors(bug_d6_marker):
    """[BUG-D6] reconcile_fk_from_polymorphic DB 异常时往外冒, 不静默吞。"""
    mock_session = AsyncMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_scope(s=None):
        yield mock_session

    with patch.object(InterfaceResultMapper, "session_scope", fake_scope):
        with pytest.raises(RuntimeError, match="boom"):
            mock_session.execute = AsyncMock(side_effect=RuntimeError("boom"))
            await InterfaceResultMapper.reconcile_fk_from_polymorphic(
                session=mock_session
            )

# ---- BUG-D4-V2: partial commit 修 ----

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d4_v2_backfill_no_explicit_commit(bug_d6_marker):
    """["""
    src = inspect.getsource(InterfaceResultMapper.backfill_content_result_id_fk)
    # 1. 源码里不能有显式 commit (去掉注释行再查, 避免误命中修复注释里
    #    "await session.commit() 会"中途提交"" 这种描述性引用)
    code_lines = [
        ln for ln in src.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    code_only = "\n".join(code_lines)
    assert "await session.commit()" not in code_only, (
        f"[BUG-D4-V2] backfill_content_result_id_fk 不应再 await session.commit(), "
        f"改用 cls.transaction(session) 让 caller 控制事务边界"
    )
    # 2. 应该用 transaction 不是 session_scope
    assert "cls.transaction(session)" in code_only, (
        f"[BUG-D4-V2] backfill_content_result_id_fk 应改用 cls.transaction(session)"
    )
    assert "cls.session_scope(session)" not in code_only, (
        f"[BUG-D4-V2] backfill_content_result_id_fk 不应再用 session_scope(session)"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d4_v2_reconcile_no_explicit_commit(bug_d6_marker):
    """[BUG-D4-V2] reconcile_fk_from_polymorphic 不再调 await session.commit()。"""
    src = inspect.getsource(InterfaceResultMapper.reconcile_fk_from_polymorphic)
    assert "await session.commit()" not in src, (
        f"[BUG-D4-V2] reconcile_fk_from_polymorphic 不应再 await session.commit(), "
        f"改用 cls.transaction(session)"
    )
    assert "cls.transaction(session)" in src, (
        f"[BUG-D4-V2] reconcile_fk_from_polymorphic 应改用 cls.transaction(session)"
    )
    assert "cls.session_scope(session)" not in src, (
        f"[BUG-D4-V2] reconcile_fk_from_polymorphic 不应再用 session_scope(session)"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d4_v2_backfill_session_none_still_works(bug_d6_marker):
    """[
    用 mock 模拟 transaction() 自管路径 (创建新 session + session.begin())。
    """
    from contextlib import asynccontextmanager

    fake_inner_session = AsyncMock()
    fake_inner_result = MagicMock()
    fake_inner_result.rowcount = 7
    fake_inner_session.execute = AsyncMock(return_value=fake_inner_result)

    @asynccontextmanager
    async def fake_transaction(s=None):
        if s is None:
            # 模拟 transaction() 自管: 创建新 session, begin 自动 commit
            async with AsyncMock() as begin_ctx:
                yield fake_inner_session
        else:
            yield s

    with patch.object(InterfaceResultMapper, "transaction", fake_transaction):
        fixed = await InterfaceResultMapper.backfill_content_result_id_fk(
            case_result_id=42
        )

    assert fixed == 7, f"[BUG-D4-V2] backfill session=None 应返 rowcount, 实际: {fixed}"
    # 内部 session 执行了 UPDATE
    fake_inner_session.execute.assert_awaited_once()
    # 内部 session 的 begin() 会处理 commit, 不是手动 commit
    fake_inner_session.commit.assert_not_awaited()

# ---- 集成: F8B 旧 backfill 仍存在 (D6 不删) ----

@pytest.mark.unit
def test_bug_d6_f8b_backfill_still_exists(bug_d6_marker):
    """[BUG-D6] F8B 的 backfill_content_result_id_fk 必须仍在 (D6 是补充, 不删旧)。"""
    src = _get_src(InterfaceResultMapper.backfill_content_result_id_fk)
    assert "UPDATE interface_result" in src, (
        f"[{BUG_D6}] F8B 的 backfill_content_result_id_fk 必须保留, "
        f"D6 是更全面的 reconcile 兜底"
    )
