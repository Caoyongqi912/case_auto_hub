"""app/mapper/ 全部用 bare raise + log.exception, 保留 traceback.

锁定行为:
- except 块内 `raise e` 改为 `raise` (防御性: e 可能被 shadow 改类型)
- except 块内 `log.error(...{e}...)` 改为 `log.exception(...)` (带 traceback)
- 多行 log.error(...) 同样改 log.exception(...)
- 例外: 非 except 块内的 log.error (业务日志/调试) 保留
"""
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


MAPPER_DIR = Path("app/mapper")


def _iter_mapper_py() -> list[Path]:
    return [p for p in MAPPER_DIR.rglob("*.py") if "__pycache__" not in str(p)]


def _in_except_block(lines: list[str], idx: int, except_indent: int) -> bool:
    """检查第 idx 行 (0-based) 是否在某 except 块的体内 (缩进 > except 缩进)."""
    if not lines[idx].strip():
        return True
    cur_indent = len(lines[idx]) - len(lines[idx].lstrip())
    return cur_indent > except_indent


# --------------------------------------------------------------------------- #
# 1. 静态扫描: 全仓 app/mapper/ 不能有 raise e (在 except 块内)
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize("mapper_file", _iter_mapper_py(), ids=lambda p: str(p))
def test_no_raise_e_in_mapper(mapper_file: Path):
    """mapper 的 except 块内不能用 `raise e`, 必须 bare raise 防 shadow."""
    text = mapper_file.read_text()
    lines = text.splitlines()
    bad: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        s = line.lstrip()
        m = re.match(r"^except\b.*:$", s)
        if m:
            except_indent = len(line) - len(s)
            j = i + 1
            while j < len(lines):
                if lines[j].strip() and not _in_except_block(lines, j, except_indent):
                    break
                if re.match(r"^\s*raise\s+e\b\s*$", lines[j]):
                    bad.append((j + 1, lines[j].rstrip()))
                j += 1
    assert not bad, (
        f"{mapper_file}: {len(bad)} 处 `raise e` 应改为 bare `raise`"
        f" (`raise e` 容易因 `e` 被 shadow / 重赋值 成非异常对象而 TypeError; "
        f"bare `raise` 隐式使用 sys.exc_info() 永远 raise 当前 except 异常):\n"
        + "\n".join(f"  {ln}: {t}" for ln, t in bad[:5])
    )


# --------------------------------------------------------------------------- #
# 2. 静态扫描: 全仓 app/mapper/ except 块内 log.error 应改成 log.exception
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize("mapper_file", _iter_mapper_py(), ids=lambda p: str(p))
def test_no_log_error_in_except_mapper(mapper_file: Path):
    """mapper 的 except 块内 log.error 应改 log.exception 带 traceback."""
    text = mapper_file.read_text()
    lines = text.splitlines()
    bad: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        s = line.lstrip()
        m = re.match(r"^except\b.*:$", s)
        if m:
            except_indent = len(line) - len(s)
            j = i + 1
            while j < len(lines):
                if lines[j].strip() and not _in_except_block(lines, j, except_indent):
                    break
                if re.match(r"^\s*log\.error\(", lines[j]):
                    bad.append((j + 1, lines[j].rstrip()))
                j += 1
    assert not bad, (
        f"{mapper_file}: {len(bad)} 处 except 块内 `log.error` "
        f"应改 `log.exception` (loguru 自动带 tb):\n"
        + "\n".join(f"  {ln}: {t}" for ln, t in bad[:5])
    )


# --------------------------------------------------------------------------- #
# 3. 行为证明: `raise e` 在 e 被 shadow 时会 TypeError, bare `raise` 永远安全
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_bare_raise_safe_when_e_is_shadowed():
    """行为证明: `raise e` 在 `e` 被 shadow 时会 TypeError, `raise` 永远安全."""
    # 危险模式: `e` 被改成一个非异常对象, 然后 raise e
    def dangerous_pattern_raise_e():
        try:
            raise ConnectionError("original")
        except Exception as e:
            e = "oops, e 被 shadow 成了字符串"
            raise e  # TypeError: exceptions must derive from BaseException

    # 安全模式: bare raise 不依赖 e
    def safe_pattern_bare_raise():
        try:
            raise ConnectionError("original")
        except Exception as e:
            e = "oops, e 被 shadow 成了字符串"
            raise  # 仍然 raise ConnectionError, 不依赖 e

    # raise e 失败
    with pytest.raises(TypeError) as exc_e:
        dangerous_pattern_raise_e()
    assert "BaseException" in str(exc_e.value) or "str" in str(exc_e.value).lower()

    # bare raise 成功, raise 的是原始 ConnectionError
    with pytest.raises(ConnectionError) as exc_bare:
        safe_pattern_bare_raise()
    assert "original" in str(exc_bare.value)

    # 这就是为什么 mapper 必须用 bare `raise` 而不是 `raise e`:
    # 业务代码可能在 except 块内修改 e, 一旦 `raise e`, 会 raise 一个非预期对象
    # bare `raise` 总是从 sys.exc_info() 拿真实异常, 不受变量修改影响


# --------------------------------------------------------------------------- #
# 4. 行为证明: loguru log.exception 自动带 traceback, log.error 不带
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_log_exception_attaches_traceback_to_log_output():
    """loguru 的 log.exception 在 except 块内自动带 traceback, log.error 不带."""
    import io
    from loguru import logger

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="DEBUG", catch=False)

    try:
        try:
            raise ValueError("simulated")
        except ValueError:
            logger.error("called via log.error")
            logger.exception("called via log.exception")
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    # log.error 不带 traceback
    err_section = output.split("called via log.exception")[0]
    assert "simulated" not in err_section, (
        f"log.error 不应包含 traceback, 但 output 含 'simulated':\n{err_section}"
    )
    # log.exception 带 traceback
    exc_section = output.split("called via log.exception")[1]
    assert "simulated" in exc_section, (
        f"log.exception 应带 traceback, 但 output 不含 'simulated':\n{exc_section}"
    )
    assert "Traceback" in exc_section, (
        f"log.exception 应输出 Traceback 字样, 但 output 没有:\n{exc_section}"
    )
