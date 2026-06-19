"""
[BUG-D6] InterfaceResult <-> APIStepContentResult 双向 FK 漂移检测 + reconcile

根因: InterfaceResult.content_result_id 跟 APIStepContentResult.interface_result_id
是同一 1:1 关系的两个方向, 任何一边漏更新就漂。F8B 只处理
'ir_missing_fk' (ir.content_result_id IS NULL) 这一种, 还有
'mismatch' 跟 'api_missing_fk' 两种漂移没处理。

修法: 加 2 个 mapper 方法 (不删 FK, 那是大改), 一查一修:
  - find_fk_inconsistencies: 扫出 3 种 mismatch_reason
  - reconcile_fk_from_polymorphic: 用 polymorphic 子类 FK 覆写 IR.content_result_id

本测试不接真实 DB, 用 mock + AST 锁住:
1. session=None 必须抛 (D4 风格)
2. find_fk_inconsistencies 的 SQL 含 3 种 mismatch_reason
3. find_fk_inconsistencies 返回的 dict 字段名跟 SQL 一致
4. reconcile_fk_from_polymorphic 的 SQL 是 UPDATE JOIN
5. reconcile 返回 rowcount
6. case_result_id 过滤: :case_result_id IS NULL 兜底 + 子查询
7. 异常路径: DB 异常往外冒
"""
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


# ---- session=None 强制 (D4 风格) ----

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
    """[BUG-D6] reconcile_fk_from_polymorphic 端到端: 返 rowcount。"""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_session.execute = AsyncMock(return_value=mock_result)

    # mock 整个 session_scope 上下文管理器
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_scope(s=None):
        yield mock_session

    with patch.object(InterfaceResultMapper, "session_scope", fake_scope):
        fixed = await InterfaceResultMapper.reconcile_fk_from_polymorphic(
            case_result_id=42, session=mock_session
        )

    assert fixed == 5, f"[{BUG_D6}] reconcile 应返 rowcount, 实际: {fixed}"
    # commit 必须调
    mock_session.commit.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d6_reconcile_handles_zero_fixes(bug_d6_marker):
    """[BUG-D6] reconcile 没找到漂移 (rowcount=0) 时返 0 不崩。"""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.execute = AsyncMock(return_value=mock_result)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_scope(s=None):
        yield mock_session

    with patch.object(InterfaceResultMapper, "session_scope", fake_scope):
        fixed = await InterfaceResultMapper.reconcile_fk_from_polymorphic(
            session=mock_session
        )

    assert fixed == 0
    # 没 commit 也行 (PyMySQL 行为, 无 UPDATE 不需要 commit), 但调用不崩
    mock_session.commit.assert_awaited()


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


# ---- 集成: F8B 旧 backfill 仍存在 (D6 不删) ----

@pytest.mark.unit
def test_bug_d6_f8b_backfill_still_exists(bug_d6_marker):
    """[BUG-D6] F8B 的 backfill_content_result_id_fk 必须仍在 (D6 是补充, 不删旧)。"""
    src = _get_src(InterfaceResultMapper.backfill_content_result_id_fk)
    assert "UPDATE interface_result" in src, (
        f"[{BUG_D6}] F8B 的 backfill_content_result_id_fk 必须保留, "
        f"D6 是更全面的 reconcile 兜底"
    )
