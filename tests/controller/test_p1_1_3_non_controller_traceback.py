"""app/ 全仓 (非 controller) 的 except 块也要用 bare raise + log.exception.

覆盖:
- app/mapper/ (P-1-1.1 已覆盖, 本测试跳过 mapper 留给专用测试)
- app/scheduler/
- app/service/
- app/ws/
- app/model/

锁定行为:
- except 块内 `raise e` 改为 `raise`
- except 块内 `log.error(...)` 改为 `log.exception(...)`
- 例外: 非 except 块内的 log.error (业务日志/调试) 保留
"""
import re
from pathlib import Path

import pytest


SCAN_DIRS = [
    "app/scheduler",
    "app/service",
    "app/ws",
    "app/model",
]


def _iter_py() -> list[Path]:
    files: list[Path] = []
    for d in SCAN_DIRS:
        root = Path(d)
        if not root.exists():
            continue
        files.extend(p for p in root.rglob("*.py") if "__pycache__" not in str(p))
    return files


def _collect_except_blocks(text: str) -> list[tuple[int, int]]:
    """收集所有 except 块的行范围 [(start_line, end_line), ...], 1-based."""
    lines = text.splitlines()
    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        s = lines[i].lstrip()
        if not re.match(r"^except\b.*:$", s):
            i += 1
            continue
        except_indent = len(lines[i]) - len(s)
        start = i
        j = i + 1
        while j < len(lines):
            stripped = lines[j].strip()
            if not stripped:
                j += 1
                continue
            cur_indent = len(lines[j]) - len(lines[j].lstrip())
            if cur_indent <= except_indent:
                break
            j += 1
        blocks.append((start + 1, j))
        i = j
    return blocks


# --------------------------------------------------------------------------- #
# 1. 静态扫描: non-controller except 块内不能用 `raise e`
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize("f", _iter_py(), ids=lambda p: str(p))
def test_no_raise_e_in_non_controller(f: Path):
    """non-controller (scheduler/service/ws/model) except 块不能用 `raise e`."""
    text = f.read_text()
    lines = text.splitlines()
    blocks = _collect_except_blocks(text)
    bad: list[tuple[int, str]] = []
    for start, end in blocks:
        for ln in range(start - 1, end):
            if re.match(r"^\s*raise\s+e\b\s*$", lines[ln]):
                bad.append((ln + 1, lines[ln].rstrip()))
    assert not bad, (
        f"{f}: {len(bad)} 处 `raise e` 应改为 bare `raise`:\n"
        + "\n".join(f"  {ln}: {t}" for ln, t in bad[:5])
    )


# --------------------------------------------------------------------------- #
# 2. 静态扫描: non-controller except 块内 log.error 必须改为 log.exception
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize("f", _iter_py(), ids=lambda p: str(p))
def test_no_log_error_in_except_non_controller(f: Path):
    """non-controller except 块内 log.error → log.exception (保留 traceback)."""
    text = f.read_text()
    lines = text.splitlines()
    blocks = _collect_except_blocks(text)
    bad: list[tuple[int, str]] = []
    for start, end in blocks:
        for ln in range(start - 1, end):
            if re.match(r"^\s*log\.error\(", lines[ln]):
                bad.append((ln + 1, lines[ln].rstrip()))
    assert not bad, (
        f"{f}: {len(bad)} 处 except 块内 `log.error` 应改为 `log.exception`:\n"
        + "\n".join(f"  {ln}: {t}" for ln, t in bad[:5])
    )
