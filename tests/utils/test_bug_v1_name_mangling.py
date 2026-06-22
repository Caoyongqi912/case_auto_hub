"""`_VariableTrans__find_g_vars` 触发 name mangling, 子类重写不会被调到。"""

import pytest
from unittest.mock import patch

from utils.variableTrans import VariableTrans
from tests.croe.interface._bug_ids import BUG_V1


@pytest.fixture
def bug_v1_marker():
    return BUG_V1


@pytest.mark.unit
def test_bug_v1_subclass_can_override_resolve_global_var(bug_v1_marker):
    """子类 _resolve_global_var 应被 _resolve_vars 调到。"""

    class MyVT(VariableTrans):
        def _resolve_global_var(self, name):
            return "mocked_value"

    vt = MyVT()
    with patch.object(MyVT, "_resolve_global_var", return_value="mocked_value") as mock_fn:
        result = vt._resolve_vars("$g_xxx")
    mock_fn.assert_called_once_with("g_xxx")
    assert result == "mocked_value", (
        f"[{BUG_V1}] _resolve_vars 应调到子类 _resolve_global_var, 实际 {result!r}"
    )


@pytest.mark.unit
def test_bug_v1_no_dunder_find_g_vars_on_class(bug_v1_marker):
    """VariableTrans 不应再有 __find_g_vars 属性(name mangled 名字)。"""
    cls_dict = VariableTrans.__dict__
    assert "__find_g_vars" not in cls_dict, (
        f"[{BUG_V1}] VariableTrans.__dict__ 不应包含 __find_g_vars"
    )
    # 同步化后全局变量走 _resolve_global_var + _g_vars_cache
    assert "_resolve_global_var" in cls_dict, (
        f"[{BUG_V1}] VariableTrans.__dict__ 应有 _resolve_global_var"
    )


@pytest.mark.unit
def test_bug_v1_resolve_g_var_uses_cache(bug_v1_marker):
    """_resolve_vars('$g_userId') 应从预加载缓存取值。"""
    vt = VariableTrans(global_vars={"userId": "42"})
    result = vt._resolve_vars("$g_userId")
    assert result == "42", f"期望 mocked 42, 实际 {result!r}"
