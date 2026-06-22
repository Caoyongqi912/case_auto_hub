"""`__find_g_vars` 触发 name mangling,子类重写不会被调到。"""

import pytest
from unittest.mock import AsyncMock, patch

from utils.variableTrans import VariableTrans
from tests.croe.interface._bug_ids import BUG_V1

@pytest.fixture
def bug_v1_marker():
    return BUG_V1

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_v1_subclass_can_override_find_g_vars(bug_v1_marker):
    """子类 _find_g_vars 应被 _resolve_vars 调到。"""

    class MyVT(VariableTrans):
        async def _find_g_vars(self, name):
            return "mocked_value"

    vt = MyVT()
    # _resolve_vars 走 $g_ 前缀分支
    with patch.object(MyVT, "_find_g_vars", new=AsyncMock(return_value="mocked_value")):
        result = await vt._resolve_vars("$g_xxx")
    assert result == "mocked_value", (
        f"[{BUG_V1}] _resolve_vars 应调到子类 _find_g_vars,实际 {result!r}"
    )

@pytest.mark.unit
def test_bug_v1_no_dunder_find_g_vars_on_class(bug_v1_marker):
    """VariableTrans 不应再有 __find_g_vars 属性(name mangled 名字)。"""
    cls_dict = VariableTrans.__dict__
    assert "__find_g_vars" not in cls_dict, (
        f"[{BUG_V1}] VariableTrans.__dict__ 不应包含 __find_g_vars"
    )
    assert "_find_g_vars" in cls_dict, (
        f"[{BUG_V1}] VariableTrans.__dict__ 应有 _find_g_vars"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_v1_resolve_g_var_calls_find_g_vars(bug_v1_marker):
    """_resolve_vars('g_xxx') 应最终走到 _find_g_vars。"""
    vt = VariableTrans()

    with patch.object(
        VariableTrans, "_find_g_vars", new=AsyncMock(return_value="42")
    ) as mock_fn:
        result = await vt._resolve_vars("$g_userId")
    mock_fn.assert_awaited_once()
    assert result == "42", f"期望 mocked 42,实际 {result!r}"
