"""ScriptManager 不应允许 import 节点。"""

import pytest

from croe.a_manager.script_manager import ScriptManager, ScriptSecurityError
from tests.croe.interface._bug_ids import BUG_S2

@pytest.fixture
def bug_s2_marker():
    return BUG_S2

@pytest.mark.security
@pytest.mark.unit
def test_bug_s2_import_blocked(bug_s2_marker):
    """import os 应被拦截。"""
    sm = ScriptManager()
    with pytest.raises(ScriptSecurityError):
        sm.execute("import os")

@pytest.mark.security
@pytest.mark.unit
def test_bug_s2_from_import_blocked(bug_s2_marker):
    """from os import system 应被拦截。"""
    sm = ScriptManager()
    with pytest.raises(ScriptSecurityError):
        sm.execute("from os import system")
