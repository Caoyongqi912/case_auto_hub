"""page_case_results / query_case_result 是 dead code, 删了不破坏。"""

import re
from pathlib import Path

import pytest

from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper
from tests.croe.interface._bug_ids import BUG_N2

REPO_ROOT = Path(__file__).resolve().parents[3]

def _src(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")

@pytest.fixture
def bug_n2_marker():
    return BUG_N2

# --------------------------------------------------------------------------- #
# N2.1 - 源码层: 这两个方法不存在了
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_bug_n2_page_case_results_removed_from_mapper(bug_n2_marker):
    """InterfaceCaseResultMapper.page_case_results 已删。"""
    assert not hasattr(InterfaceCaseResultMapper, "page_case_results"), (
        f"[{BUG_N2}] page_case_results 还在, 应删除 (dead code)。"
    )

@pytest.mark.unit
def test_bug_n2_query_case_result_removed_from_mapper(bug_n2_marker):
    """InterfaceCaseResultMapper.query_case_result 已删。"""
    assert not hasattr(InterfaceCaseResultMapper, "query_case_result"), (
        f"[{BUG_N2}] query_case_result 还在, 应删除 (dead code)。"
    )

# --------------------------------------------------------------------------- #
# N2.2 - 源码层: 全项目 0 caller (除已删的定义本身)
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_bug_n2_no_caller_in_croe_app(bug_n2_marker):
    """[
    例外: 删掉的方法定义本身 (interfaceResultMapper.py) 跟本测试文件
    (BUD-N2 自己提的回归) 不算 caller。
    """
    # 扫 croe/ + app/ 下所有 .py 文件
    bad_callers = []
    skip_files = {
        "tests/croe/interface/test_bug_n2_delete_dead_code.py",  # 本测试文件
    }
    for sub in ("croe", "app"):
        root = REPO_ROOT / sub
        for py in root.rglob("*.py"):
            if "__pycache__" in str(py):
                continue
            rel = str(py.relative_to(REPO_ROOT))
            if rel in skip_files:
                continue
            if rel == "app/mapper/interfaceApi/interfaceResultMapper.py":
                continue
            src = py.read_text(encoding="utf-8")
            # 注释里提的方法名不算 caller, 只查代码行 (非 # 开头)
            code_lines = [ln for ln in src.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
            code_blob = "\n".join(code_lines)
            for bad in ("page_case_results", "query_case_result"):
                if bad in code_blob:
                    bad_callers.append(f"{rel}: {bad}")
    assert not bad_callers, (
        f"[{BUG_N2}] 发现 caller, dead code 删了会破坏它们: {bad_callers}"
    )

# --------------------------------------------------------------------------- #
# N2.3 - 文档层: D9 注释里还提到, 但功能已切到 get_by_id, 锁住不回归
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_bug_n2_d9_comment_still_recommends_get_by_id(bug_n2_marker):
    """删方法后, 注释仍指引"请用 get_by_id 替代", 防止新代码误加。"""
    src = _src("app/mapper/interfaceApi/interfaceResultMapper.py")
    assert "list_by_filter" in src or "get_by_id" in src, (
        "注释里应指引替代方案 (get_by_id / list_by_filter)。"
    )
