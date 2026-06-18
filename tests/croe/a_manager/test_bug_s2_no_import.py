"""
BUG-S2 回归测试:ScriptManager 不应允许 import 节点。
import 在 exec 沙箱里虽然不会直接拿到 os/subprocess,但攻击者可以靠
import 加载任意模块,绕过白名单 builtin 控制。

详见 docs/review/run_interface_case_deep_review.md。
"""
import pytest

from croe.a_manager.script_manager import ScriptManager, ScriptSecurityError
from tests.croe.interface._bug_ids import BUG_S2


@pytest.fixture
def bug_s2_marker():
    return BUG_S2


@pytest.mark.security
@pytest.mark.unit
def test_bug_s2_import_blocked(bug_s2_marker):
    """[BUG-S2] import os 应被拦截。"""
    sm = ScriptManager()
    with pytest.raises(ScriptSecurityError):
        sm.execute("import os")


@pytest.mark.security
@pytest.mark.unit
def test_bug_s2_from_import_blocked(bug_s2_marker):
    """[BUG-S2] from os import system 应被拦截。"""
    sm = ScriptManager()
    with pytest.raises(ScriptSecurityError):
        sm.execute("from os import system")
