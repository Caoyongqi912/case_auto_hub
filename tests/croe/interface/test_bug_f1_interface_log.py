"""
BUG-F1 回归测试:runner 不应给 `case_result.interfaceLog` (camelCase) 赋值,
应通过 `finalize_case_result(logs=...)` 写入 `interface_log` 字段。

详见 docs/review/run_interface_case_deep_review.md。

`InterfaceCaseResult.interface_log` 是 SQLAlchemy TEXT 列(snake_case),
runner.py:225 写成 `case_result.interfaceLog = ...` 会在实例上挂一个
"野"属性,既不写库、也不会和列字段同步,极易在调试时被误以为是真字段。
"""
import re
from pathlib import Path

import pytest

from tests.croe.interface._bug_ids import BUG_F1


@pytest.fixture
def bug_f1_marker():
    return BUG_F1


@pytest.mark.unit
def test_bug_f1_runner_no_camelcase_log_assignment(bug_f1_marker):
    """[BUG-F1] runner.py 不应出现 case_result.interfaceLog = ... 这种 camelCase 赋值。"""
    runner_py = Path("croe/interface/runner.py")
    if not runner_py.exists():
        pytest.skip("runner.py 不存在(可能项目布局有变)")

    src = runner_py.read_text()

    # 匹配形如 case_result.interfaceLog = ... / case_result.interfaceLog=...
    pattern = re.compile(r"case_result\.interfaceLog\s*=", re.MULTILINE)
    matches = pattern.findall(src)

    assert not matches, (
        f"[{BUG_F1}] runner.py 仍有 {len(matches)} 处 "
        f"`case_result.interfaceLog = ...` 赋值,应改为通过 "
        f"`result_writer.finalize_case_result(logs=...)` 写入 `interface_log` 列"
    )


@pytest.mark.unit
def test_bug_f1_interface_log_column_exists():
    """`InterfaceCaseResult.interface_log` 列必须存在(snake_case),保证 finalize 能写库。"""
    from app.model.interfaceAPIModel.interfaceResultModel import InterfaceCaseResult

    cols = {c.name for c in InterfaceCaseResult.__table__.columns}
    assert "interface_log" in cols, (
        f"[{BUG_F1}] InterfaceCaseResult 应有 interface_log 列,"
        f"实际有 {sorted(cols)}"
    )
    # 反向: 不应有 camelCase 列
    assert "interfaceLog" not in cols, (
        f"[{BUG_F1}] InterfaceCaseResult 不应有 interfaceLog (camelCase) 列"
    )
