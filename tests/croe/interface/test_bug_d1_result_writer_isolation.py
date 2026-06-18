"""
BUG-D1 回归测试:每个 `InterfaceRunner` 应持有独立的 `ResultWriter` 实例,
不能共享模块级单例(否则并发 case 时 api_result_cache /
content_result_cache 会互相污染)。

详见 docs/review/run_interface_case_deep_review.md。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from croe.interface.runner import InterfaceRunner
from tests.croe.interface._bug_ids import BUG_D1


@pytest.fixture
def bug_d1_marker():
    return BUG_D1


def _make_starter():
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.username = "u"
    starter.userId = 1
    starter.uid = "u-1"
    starter.logs = []
    starter.over = AsyncMock()
    return starter


@pytest.mark.unit
def test_bug_d1_two_runners_have_independent_result_writers(bug_d1_marker):
    """[BUG-D1] 两个 InterfaceRunner 应当有不同的 result_writer 实例。"""
    r1 = InterfaceRunner(starter=_make_starter())
    r2 = InterfaceRunner(starter=_make_starter())

    assert hasattr(r1, "result_writer"), (
        f"[{BUG_D1}] InterfaceRunner 应持有 result_writer 属性"
    )
    assert r1.result_writer is not r2.result_writer, (
        f"[{BUG_D1}] 两个 runner 的 result_writer 必须是不同实例,"
        f"否则并发会污染缓存"
    )
    assert r1.result_writer.api_result_cache is not r2.result_writer.api_result_cache, (
        f"[{BUG_D1}] api_result_cache 也必须是独立 list"
    )
    # 互相 mutate 互不影响
    r1.result_writer.api_result_cache.append("A")
    r2.result_writer.api_result_cache.append("B")
    assert r1.result_writer.api_result_cache == ["A"]
    assert r2.result_writer.api_result_cache == ["B"]


@pytest.mark.unit
def test_bug_d1_result_writer_has_clear_cache():
    """[BUG-D1] ResultWriter 应当提供 clear_cache 用于释放缓存。"""
    r = InterfaceRunner(starter=_make_starter())
    assert hasattr(r.result_writer, "clear_cache"), (
        f"[{BUG_D1}] ResultWriter 应有 clear_cache 方法"
    )
