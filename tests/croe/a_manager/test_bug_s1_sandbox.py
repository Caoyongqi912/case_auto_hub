"""
BUG-S1 回归测试:ScriptManager 应当拦截 getattr/setattr/链式调用等
沙箱逃逸手段。

详见 docs/review/run_interface_case_deep_review.md。
原版 _validate_ast 只对 ast.Call.func 是 ast.Name 时检查
DISALLOWED_ATTRS,getattr/setattr 这类"函数名看起来无害"
的函数会绕过;另外 obj.__xxx 双下划线属性访问也应拒绝。
"""
import pytest

from croe.a_manager.script_manager import ScriptManager, ScriptSecurityError
from tests.croe.interface._bug_ids import BUG_S1


@pytest.fixture
def bug_s1_marker():
    return BUG_S1


@pytest.mark.security
@pytest.mark.unit
def test_bug_s1_getattr_call_to_dunder_blocked(bug_s1_marker):
    """[BUG-S1] getattr(obj, '__class__') 应被拦截。"""
    sm = ScriptManager()
    with pytest.raises(ScriptSecurityError):
        sm.execute('x = getattr("", "__class__")')


@pytest.mark.security
@pytest.mark.unit
def test_bug_s1_setattr_call_blocked(bug_s1_marker):
    """[BUG-S1] setattr 也应被拦截(防止修改内置对象属性)。"""
    sm = ScriptManager()
    with pytest.raises(ScriptSecurityError):
        sm.execute('setattr(str, "x", 1)')


@pytest.mark.security
@pytest.mark.unit
def test_bug_s1_attribute_access_to_dunder_blocked(bug_s1_marker):
    """[BUG-S1] 直接 obj.__class__ 也应被拦截(确保未被破坏)。"""
    sm = ScriptManager()
    with pytest.raises(ScriptSecurityError):
        sm.execute('x = "".__class__')


@pytest.mark.security
@pytest.mark.unit
def test_bug_s1_chained_dunder_call_blocked(bug_s1_marker):
    """[BUG-S1] 链式调用 getattr(...).xxx 也应被拦截。"""
    sm = ScriptManager()
    with pytest.raises(ScriptSecurityError):
        sm.execute('getattr("", "__class__").__bases__')
