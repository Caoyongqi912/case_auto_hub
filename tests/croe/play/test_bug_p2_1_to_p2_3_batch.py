"""[BUG-P-2-1 + P-2-2 + P-2-3] 3 个 P2 修复一锅端, 来自 PLAY_REVIEW_2026_06_21 §5。"""

import inspect
import re

import pytest

from tests.croe.play._bug_ids import (
    BUG_P_2_1, BUG_P_2_2, BUG_P_2_3,
)

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def test_bug_p_2_1_no_inline_play_step_group_mapper_import_in_play_case_mapper():
    """[    应在文件顶部 import。"""
    with open("app/mapper/play/playCaseMapper.py", "r", encoding="utf-8") as fp:
        src = fp.read()
    # 排除注释行
    code_only = "\n".join(
        ln for ln in src.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )
    inline_imports = re.findall(
        r"from\s+app\.mapper\.play\.playStepGroupMapper\s+import",
        code_only
    )
    assert len(inline_imports) == 0, (
        f"[{BUG_P_2_1}] playCaseMapper.py 还有 {len(inline_imports)} 处内联 "
        f"`from app.mapper.play.playStepGroupMapper import ...`, 应放文件顶部"
    )

def test_bug_p_2_1_play_step_group_mapper_imported_at_top():
    """[BUG-P-2-1] playCaseMapper.py 顶部应 import PlayStepGroupMapper。"""
    with open("app/mapper/play/playCaseMapper.py", "r", encoding="utf-8") as fp:
        src = fp.read()
    # 找 import 块 (前 30 行, 排除 docstring 之后)
    head = "\n".join(src.splitlines()[:30])
    assert "PlayStepGroupMapper" in head, (
        f"[{BUG_P_2_1}] playCaseMapper.py 顶部未 import PlayStepGroupMapper"
    )

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def test_bug_p_2_2_reload_content_has_deprecation_note():
    """[BUG-P-2-2] reload_content docstring 应有 deprecation 标记。"""
    from app.mapper.play.playCaseMapper import PlayCaseMapper

    src = inspect.getsource(PlayCaseMapper.reload_content)
    assert "死代码" in src or "caller" in src, (
        f"[{BUG_P_2_2}] reload_content docstring 缺 deprecation 说明"
    )

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def test_bug_p_2_3_execute_case_sets_trace_id():
    """[BUG-P-2-3] execute_case 进入时 set_trace_id。"""
    from croe.play.play_runner import PlayRunner

    src = inspect.getsource(PlayRunner.execute_case)
    assert "set_trace_id" in src, (
        f"[{BUG_P_2_3}] execute_case 没 set_trace_id, 多 case 并发日志无法定位"
    )
    # set_trace_id 调用应在函数体前面 (在 case_step_contents fetch 之前)
    # 找 set_trace_id() 调用 (不是 docstring 里说的)
    set_pos = src.find("set_trace_id()")
    fetch_pos = src.find("query_content_steps")
    assert set_pos > 0 and fetch_pos > 0 and set_pos < fetch_pos, (
        f"[{BUG_P_2_3}] set_trace_id() 必须在 query_content_steps 之前 "
        f"(trace_id 提前注入日志, 后面的 query 日志才有 trace) "
        f"(set_pos={set_pos}, fetch_pos={fetch_pos})"
    )

def test_bug_p_2_3_execute_case_clears_trace_id_in_finally():
    """[BUG-P-2-3] execute_case 的 finally 块应 clear_trace_id 防泄漏。"""
    from croe.play.play_runner import PlayRunner

    src = inspect.getsource(PlayRunner.execute_case)
    assert "clear_trace_id" in src, (
        f"[{BUG_P_2_3}] execute_case 没 clear_trace_id, trace_id 会泄漏到下次 case"
    )
    # clear_trace_id 必须在 finally 块里 (或 try 块内, 但 finally 优先)
    assert "finally:" in src, (
        f"[{BUG_P_2_3}] execute_case 缺 finally 块 (clear_trace_id 找不到落脚点)"
    )
    finally_pos = src.find("finally:")
    # clear_trace_id 引用: 找调用点 (有 "(") 而不是 docstring 注释里
    clear_pos = src.find("clear_trace_id()")
    if clear_pos == -1:
        clear_pos = src.find("clear_trace_id")
    assert clear_pos > finally_pos, (
        f"[{BUG_P_2_3}] clear_trace_id 应在 finally 块里 (finally_pos={finally_pos}, clear_pos={clear_pos})"
    )

def test_bug_p_2_3_execute_case_imports_trace_id_helpers():
    """[BUG-P-2-3] play_runner.py 应 import set_trace_id / clear_trace_id。"""
    from croe.play import play_runner

    src = inspect.getsource(play_runner)
    assert "from croe.interface.observability import" in src, (
        f"[{BUG_P_2_3}] play_runner 没从 croe.interface.observability "
        f"import set_trace_id / clear_trace_id"
    )
    assert "set_trace_id" in src and "clear_trace_id" in src, (
        f"[{BUG_P_2_3}] play_runner 缺 set_trace_id / clear_trace_id 引用"
    )
