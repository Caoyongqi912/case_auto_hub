"""
BUG-D2 回归测试:`bulk_insert_results` 不应静默丢数据。

原版对缺 content_type / 未知 content_type 的 item 静默 `continue`，
调用方只看到 `total_inserted`，根本不知道丢了多少。

修复后:
- 缺 content_type 视为编程错误,直接抛 ValueError (跟 insert_result 一致)
- 未知 content_type 走 skip,末尾 WARNING 输出原因 + 返回 (inserted, skipped) 元组
- 调用方 (result_writer) 区分 inserted / skipped 并分别 log

详见 docs/review/run_interface_case_deep_review.md。
"""
import contextlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from enums.CaseEnum import CaseStepContentType
from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceContentStepResultMapper,
)
from tests.croe.interface._bug_ids import BUG_D2

MAPPER_LOGGER = "app.mapper.interfaceApi.interfaceResultMapper"


@pytest.fixture
def bug_d2_marker():
    return BUG_D2


def _valid_item(content_type=CaseStepContentType.STEP_API, content_id=100):
    return {
        "content_type": content_type,
        "content_id": content_id,
        "content_name": f"step-{content_id}",
        "content_step": 1,
        "interface_result_id": content_id,
    }


def _fake_session():
    """返回一个 AsyncMock 的 session, 用于 D2 测试。"""
    s = AsyncMock()
    s.add_all = MagicMock()
    s.flush = AsyncMock()
    return s


def _patch_transaction(fake_session):
    """把 cls.transaction() mock 成一个 async ctx mgr,内部 yield fake_session。"""
    @contextlib.asynccontextmanager
    async def _tx():
        yield fake_session
    return patch.object(InterfaceContentStepResultMapper, "transaction", _tx)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d2_empty_returns_zero_zero(bug_d2_marker):
    """[BUG-D2] 空输入应当返回 (0, 0)。"""
    inserted, skipped = await InterfaceContentStepResultMapper.bulk_insert_results(
        [], session=_fake_session()
    )
    assert inserted == 0, f"[{BUG_D2}] empty 应 inserted=0, 实际 {inserted}"
    assert skipped == 0, f"[{BUG_D2}] empty 应 skipped=0, 实际 {skipped}"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d2_missing_content_type_raises(bug_d2_marker):
    """[BUG-D2] 缺 content_type 应抛 ValueError(编程错误,不静默吞)。"""
    bad = {"content_id": 1, "content_name": "no-ct"}  # 没 content_type
    with pytest.raises(ValueError, match="content_type"):
        await InterfaceContentStepResultMapper.bulk_insert_results(
            [bad], session=_fake_session()
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d2_unknown_content_type_is_counted_and_logged(bug_d2_marker):
    """[BUG-D2] 未知 content_type 应当被计入 skipped 并 WARNING 输出。"""
    unknown = {
        "content_type": 9999,  # 一定不在 RESULT_TYPE_MAP 里
        "content_id": 1,
        "content_name": "alien",
    }
    fake_session = AsyncMock()
    fake_session.add_all = MagicMock()
    fake_session.flush = AsyncMock()

    with _patch_transaction(fake_session), patch("utils.log.warning") as mock_warn:
        inserted, skipped = await InterfaceContentStepResultMapper.bulk_insert_results(
            [unknown], session=fake_session
        )

    assert inserted == 0, f"[{BUG_D2}] 未知 type 不应被 inserted, 实际 {inserted}"
    assert skipped == 1, f"[{BUG_D2}] 未知 type 应被 skipped=1, 实际 {skipped}"
    # WARNING 必须出现且提到 "跳过" + content_name "alien"
    assert mock_warn.called, f"[{BUG_D2}] 应当 WARNING 输出被跳过的 item 详情"
    warn_msg = " ".join(str(c.args[0]) for c in mock_warn.call_args_list)
    assert "跳过" in warn_msg, f"[{BUG_D2}] WARNING 应含 '跳过', 实际: {warn_msg}"
    assert "alien" in warn_msg, f"[{BUG_D2}] WARNING 应含 content_name 'alien', 实际: {warn_msg}"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d2_mix_valid_and_unknown(bug_d2_marker):
    """[BUG-D2] 合法 + 未知混在一起,合法的不被牵连。"""
    good = _valid_item(content_id=1)
    good2 = _valid_item(content_id=2)
    unknown = {
        "content_type": 9999,
        "content_id": 3,
        "content_name": "alien",
    }
    fake_session = AsyncMock()
    fake_session.add_all = MagicMock()
    fake_session.flush = AsyncMock()

    with _patch_transaction(fake_session), patch("utils.log.warning") as mock_warn:
        inserted, skipped = await InterfaceContentStepResultMapper.bulk_insert_results(
            [good, unknown, good2], session=fake_session
        )

    assert inserted == 2, f"[{BUG_D2}] 2 条合法应 inserted=2, 实际 {inserted}"
    assert skipped == 1, f"[{BUG_D2}] 1 条未知应 skipped=1, 实际 {skipped}"
    # add_all 应当只为 STEP_API 那组调用 (2 条),不被未知污染
    add_all_calls = fake_session.add_all.call_args_list
    total_added = sum(len(c.args[0]) for c in add_all_calls)
    assert total_added == 2, f"[{BUG_D2}] 只应 add_all 2 条合法 item, 实际 {total_added}"
    # 未知的那条也应被 WARNING
    assert mock_warn.called, f"[{BUG_D2}] mix 场景下未知 type 应触发 WARNING"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d2_all_valid_no_warning(bug_d2_marker):
    """[BUG-D2] 全部合法不应产生 WARNING。"""
    items = [_valid_item(content_id=i) for i in range(3)]
    fake_session = AsyncMock()
    fake_session.add_all = MagicMock()
    fake_session.flush = AsyncMock()

    with _patch_transaction(fake_session), patch("utils.log.warning") as mock_warn:
        inserted, skipped = await InterfaceContentStepResultMapper.bulk_insert_results(
            items, session=fake_session
        )

    assert inserted == 3, f"[{BUG_D2}] 应 inserted=3, 实际 {inserted}"
    assert skipped == 0, f"[{BUG_D2}] 应 skipped=0, 实际 {skipped}"
    # 全部合法不应触发 "跳过" 相关的 WARNING (mock_warn 可能被其它代码调用,
    # 这里只看消息含 "跳过" 的)
    skip_warns = [
        c for c in mock_warn.call_args_list
        if "跳过" in str(c.args[0] if c.args else "")
    ]
    assert not skip_warns, (
        f"[{BUG_D2}] 全部合法不应触发 skip 警告, 实际: "
        f"{[c.args for c in skip_warns]}"
    )
