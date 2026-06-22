"""VariableTrans 引用未定义变量时静默返回变量名"""

import os
import pytest
from unittest.mock import patch

from utils.variableTrans import VariableTrans


@pytest.fixture
def vt():
    return VariableTrans()


@pytest.mark.unit
def test_bug_v6_resolve_undefined_var_returns_name_with_warning(vt):
    """核心回归: 缺失变量仍返 var_name, 但 WARNING 出来让运维可见"""
    from utils import log
    with patch.object(log, "warning") as mock_warn:
        result = vt._resolve_vars("user_id")
    assert result == "user_id", f"期望返回 'user_id' 字符串, 实际 {result!r}"
    assert mock_warn.called, "缺失变量未触发 log.warning"
    msg = str(mock_warn.call_args)
    assert "user_id" in msg and "未定义" in msg, (
        f"WARNING 应含 'user_id' 和 '未定义', 实际: {msg}"
    )


@pytest.mark.unit
def test_bug_v6_resolve_defined_var_no_warning(vt):
    """定义了的变量: 不应 WARNING, 直接返真值"""
    from utils import log
    vt._vars["token"] = "abc123"
    with patch.object(log, "warning") as mock_warn:
        result = vt._resolve_vars("token")
    assert result == "abc123", f"期望 'abc123', 实际 {result!r}"
    assert not mock_warn.called, f"已定义变量不应 WARNING, 实际: {mock_warn.call_args_list}"


@pytest.mark.unit
def test_bug_v6_resolve_f_prefix_still_works(vt):
    """$f_ 前缀仍走 faker.value, 不进 V6 警告分支"""
    # faker.value 在 {{$f_name}} 之类会生成随机值, 不进 _vars 也没事
    with patch.object(vt._faker, "value", return_value="MockFaker"):
        result = vt._resolve_vars("$f_name")
    assert result == "MockFaker"


@pytest.mark.unit
def test_bug_v6_resolve_g_prefix_uses_cache(vt):
    """$g_ 前缀走预加载缓存, 不进 V6 警告分支"""
    vt.set_global_vars({"userId": "g_val"})
    result = vt._resolve_vars("$g_userId")
    assert result == "g_val"


@pytest.mark.unit
def test_bug_v6_get_var_undefined_returns_key_with_warning(vt):
    """get_var 同病: 缺失返 key + WARNING"""
    from utils import log
    with patch.object(log, "warning") as mock_warn:
        result = vt.get_var("missing_key")
    assert result == "missing_key", f"期望返 'missing_key', 实际 {result!r}"
    assert mock_warn.called
    msg = str(mock_warn.call_args)
    assert "missing_key" in msg and "未定义" in msg, (
        f"get_var 期望 WARNING 含 'missing_key', 实际: {msg}"
    )


@pytest.mark.unit
def test_bug_v6_get_var_defined_no_warning(vt):
    """get_var 已定义: 不 WARNING"""
    from utils import log
    vt._vars["foo"] = "bar"
    with patch.object(log, "warning") as mock_warn:
        result = vt.get_var("foo")
    assert result == "bar"
    assert not mock_warn.called, f"已定义变量不应 WARNING, 实际: {mock_warn.call_args_list}"


@pytest.mark.unit
def test_bug_v6_strict_mode_raises_keyerror(vt, monkeypatch):
    """VARIABLE_TRANS_STRICT=1 时 _resolve_vars 抛 KeyError, 让 case 立刻挂"""
    from utils import log
    monkeypatch.setenv("VARIABLE_TRANS_STRICT", "1")
    with patch.object(log, "warning"):
        with pytest.raises(KeyError, match="user_id"):
            vt._resolve_vars("user_id")
    with patch.object(log, "warning"):
        with pytest.raises(KeyError, match="missing"):
            vt.get_var("missing")
