"""BUG-P-1-1.2 回归测试: app/controller/ 全部用 bare raise + log.exception, 保留 traceback.

锁定行为:
- except 块内 `raise e` 改为 `raise` (防御性: e 可能被 shadow 改类型)
- except 块内 `log.error(...{e}...)` 改为 `log.exception(...)` (带 traceback)
- 多行 log.error(...) 同样改 log.exception(...)
- 例外: 非 except 块内的 log.error (业务日志/调试) 保留

本测试与 tests/mapper/test_p1_1_1_mapper_traceback.py 配套, 覆盖 controller 层.
"""
import re
from pathlib import Path

import pytest


CONTROLLER_DIR = Path("app/controller")


def _iter_controller_py() -> list[Path]:
    return [p for p in CONTROLLER_DIR.rglob("*.py") if "__pycache__" not in str(p)]


def _collect_except_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """收集所有 except 块的行范围 [(start_line, end_line), ...], 1-based."""
    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        s = lines[i].lstrip()
        m = re.match(r"^except\b.*:$", s)
        if not m:
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
# 1. 静态扫描: controller except 块内不能用 `raise e`
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize("controller_file", _iter_controller_py(), ids=lambda p: str(p))
def test_no_raise_e_in_controller(controller_file: Path):
    """[BUG-P-1-1.2] controller 的 except 块内不能用 `raise e`, 必须 bare raise 防 shadow."""
    text = controller_file.read_text()
    lines = text.splitlines()
    blocks = _collect_except_blocks(lines)
    bad: list[tuple[int, str]] = []
    for start, end in blocks:
        for ln in range(start - 1, end):
            if re.match(r"^\s*raise\s+e\b\s*$", lines[ln]):
                bad.append((ln + 1, lines[ln].rstrip()))
    assert not bad, (
        f"[BUG-P-1-1.2] {controller_file}: {len(bad)} 处 `raise e` 应改为 bare `raise`"
        f" (`raise e` 容易因 `e` 被 shadow / 重赋值 成非异常对象而 TypeError; "
        f"bare `raise` 隐式使用 sys.exc_info() 永远 raise 当前 except 异常):\n"
        + "\n".join(f"  {ln}: {t}" for ln, t in bad[:5])
    )


# --------------------------------------------------------------------------- #
# 2. 静态扫描: controller except 块内 log.error 必须改为 log.exception
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize("controller_file", _iter_controller_py(), ids=lambda p: str(p))
def test_no_log_error_in_except(controller_file: Path):
    """[BUG-P-1-1.2] controller 的 except 块内不能用 `log.error`, 必须用 `log.exception` 保留 traceback."""
    text = controller_file.read_text()
    lines = text.splitlines()
    blocks = _collect_except_blocks(lines)
    bad: list[tuple[int, str]] = []
    for start, end in blocks:
        for ln in range(start - 1, end):
            if re.match(r"^\s*log\.error\(", lines[ln]):
                bad.append((ln + 1, lines[ln].rstrip()))
    assert not bad, (
        f"[BUG-P-1-1.2] {controller_file}: {len(bad)} 处 except 块内 `log.error` 应改为 `log.exception`"
        f" (loguru 的 `log.error` 不附加 Traceback, `log.exception` 才会; "
        f"用 `log.error` 排障时看不到调用链):\n"
        + "\n".join(f"  {ln}: {t}" for ln, t in bad[:5])
    )


# --------------------------------------------------------------------------- #
# 3. 行为证明: interfaceController 导出 YAML 异常分支
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_interfaceController_export_yaml_uses_log_exception_and_bare_raise():
    """[BUG-P-1-1.2] 回归 interfaceController 导出 YAML: log.exception + bare raise."""
    from pathlib import Path as _P
    src = (_P("app/controller/interface/interfaceController.py")).read_text()
    idx = src.find("导出YAML失败")
    assert idx != -1, "expected 导出YAML失败 log message in interfaceController.py"
    # 看前 80 字符 (含 log.exception 关键字) 和后 80 字符 (含 raise 关键字)
    pre = src[max(0, idx - 60):idx]
    post = src[idx:idx + 120]
    assert "log.exception" in pre, (
        f"导出YAML 异常分支应使用 log.exception, 上下文: {pre!r}"
    )
    assert re.search(r"^\s*raise\s*$", post, re.MULTILINE), (
        f"导出YAML 异常分支应使用 bare raise, 上下文: {post!r}"
    )
    # 反向断言: 修过的代码确实不再含 log.error
    assert "log.error" not in post.split("导出YAML失败", 1)[0] + "导出YAML失败" + post.split("导出YAML失败", 1)[1][:120], (
        "导出YAML 异常分支应不含 log.error"
    )


# --------------------------------------------------------------------------- #
# 4. 行为证明: case_plan.delete_permanent 异常分支
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_case_plan_delete_permanent_uses_log_exception():
    """[BUG-P-1-1.2] 回归 case_plan.delete_permanent: log.exception 而非 log.error."""
    from pathlib import Path as _P
    src = (_P("app/controller/test_case/case_plan.py")).read_text()
    idx = src.find("delete_permanent: case 还被其他计划引用")
    assert idx != -1, "expected delete_permanent log message in case_plan.py"
    pre = src[max(0, idx - 60):idx]
    assert "log.exception" in pre, (
        f"delete_permanent 异常分支应使用 log.exception, 上下文: {pre!r}"
    )
