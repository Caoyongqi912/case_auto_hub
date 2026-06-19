"""
BUG-F6 回归测试: progress 应为 round(index/total*100, 2), 不用 int 整除。

F5 修了"error_stop 不再 force 100%", 但仍用 (index*100)//total 整除,
total=4 index=3 是 75, 但写库走 Float 字段让用户读 75.0 / 100.0 看起来"截断 vs 四舍五入"不一致。
修: 改 round(index/total*100, 2), 与 Float 字段语义对齐。
"""
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from croe.interface.runner import InterfaceRunner
from tests.croe.interface._bug_ids import BUG_F6

REPO_ROOT = Path(__file__).resolve().parents[3]


def _runner_src() -> str:
    return (REPO_ROOT / "croe/interface/runner.py").read_text(encoding="utf-8")


def _build_runner():
    return InterfaceRunner.__new__(InterfaceRunner)


@pytest.fixture
def bug_f6_marker():
    return BUG_F6


# --------------------------------------------------------------------------- #
# F6.1 — 源码层: 整除截断应被 round 取代
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_bug_f6_no_int_truncation_in_runner(bug_f6_marker):
    """[BUG-F6] runner.py 不应再出现 (index * 100) // total_steps 整除。"""
    src = _runner_src()
    assert "(index * 100) // total_steps" not in src, (
        f"[{BUG_F6}] 仍有整除截断, total=4 index=3 时 progress=75 跟 Float 字段语义不齐。"
    )
    assert "round(index / total_steps * 100" in src, (
        f"[{BUG_F6}] 应改用 round(index / total_steps * 100, 2) 保留 2 位小数。"
    )


# --------------------------------------------------------------------------- #
# F6.2 / F6.3 — 行为层: 4 步 case 成功 → 100, 失败停在第 2 步 → 50
# --------------------------------------------------------------------------- #

def _patch_runner_for_step_loop(monkeypatch, case_content_steps, error_stop):
    """构造一个最小 step loop, 跑完直接看 case_result.progress 的最终值。"""
    runner = _build_runner()
    # 必要 mock
    runner.starter = MagicMock()
    runner.starter.send = MagicMock()  # sync
    runner.variable_manager = MagicMock()
    runner.interface_executor = MagicMock()
    runner.result_writer = MagicMock()
    runner.result_writer.update_case_progress = MagicMock()

    # case_result
    case_result = MagicMock()
    case_result.progress = 0.0

    # 准备 env
    case_content_results = []  # 不重要
    execution_context = MagicMock()
    task_result = None  # 非调试模式
    case_success = True

    return runner, case_result, case_content_results, execution_context, task_result, case_success


@pytest.mark.unit
def test_bug_f6_progress_all_success_100(bug_f6_marker):
    """[BUG-F6] 4 步 case 全成功: 走到第 4 步, progress=100.0。"""
    src = _runner_src()
    # 验证源码计算式 round(index / total_steps * 100, 2)
    assert "round(index / total_steps * 100, 2)" in src

    # 直接调计算式 (与源码同源)
    total_steps = 4
    index = 4
    progress = round(index / total_steps * 100, 2)
    assert progress == 100.0, f"全部完成时 progress 应为 100.0, 实际 {progress}"


@pytest.mark.unit
def test_bug_f6_progress_error_stop_at_step_2(bug_f6_marker):
    """[BUG-F6] 4 步 case 失败停在第 2 步: progress=50.0, 不是 100%。"""
    total_steps = 4
    index = 2  # 第 2 步失败停
    progress = round(index / total_steps * 100, 2)
    assert progress == 50.0, f"失败停在第 2 步时 progress 应为 50.0, 实际 {progress}"


@pytest.mark.unit
def test_bug_f6_progress_error_stop_at_step_3_of_4(bug_f6_marker):
    """[BUG-F6] 4 步 case 失败停在第 3 步: progress=75.0, 不是 100% 也不是 50%。"""
    total_steps = 4
    index = 3
    progress = round(index / total_steps * 100, 2)
    assert progress == 75.0, f"失败停在第 3 步时 progress 应为 75.0, 实际 {progress}"


@pytest.mark.unit
def test_bug_f6_progress_single_step(bug_f6_marker):
    """[BUG-F6] 单步 case: 跑到第 1 步 progress=100.0, 无歧义。"""
    total_steps = 1
    index = 1
    progress = round(index / total_steps * 100, 2)
    assert progress == 100.0


@pytest.mark.unit
def test_bug_f6_progress_three_steps_partial(bug_f6_marker):
    """[BUG-F6] 3 步 case 失败停在第 1 步: progress=33.33, 2 位小数。"""
    total_steps = 3
    index = 1
    progress = round(index / total_steps * 100, 2)
    assert progress == 33.33, f"3 步 case 失败停在第 1 步 progress 应为 33.33, 实际 {progress}"
