"""BUG-M7 回归测试: result 列 enum/bool 类型安全。"""

import pytest

from enums.InterfaceEnum import (
    InterfaceAPIResultEnum,
    InterfaceAPIStatusEnum,
)
from tests.croe.interface._bug_ids import BUG_M7

@pytest.fixture
def bug_m7_marker():
    return BUG_M7

@pytest.mark.unit
def test_bug_m7_interface_case_result_enum_removed(bug_m7_marker):
    """[BUG-M7] 旧的 str 型 InterfaceCaseResultEnum 必须不存在, 防止同名不同值陷阱。"""
    from enums import InterfaceEnum as ie_mod
    assert not hasattr(ie_mod, "InterfaceCaseResultEnum"), (
        "InterfaceCaseResultEnum (str 值) 已删除: "
        "跟 InterfaceAPIResultEnum (bool 值) 同名不同值, 会导致 result 列静默写反"
    )

@pytest.mark.unit
def test_bug_m7_api_result_enum_values_are_bool(bug_m7_marker):
    """[BUG-M7] InterfaceAPIResultEnum 成员值必须为 bool, 跟 Boolean 列对得上。"""
    assert InterfaceAPIResultEnum.SUCCESS is True
    assert InterfaceAPIResultEnum.ERROR is False
    # 防回归: 不允许赋值成 str
    assert isinstance(InterfaceAPIResultEnum.SUCCESS, bool)
    assert isinstance(InterfaceAPIResultEnum.ERROR, bool)

@pytest.mark.unit
def test_bug_m7_result_flag_helper_normalizes(bug_m7_marker):
    """[BUG-M7] _result_flag_to_bool 接受 bool/str/None, 统一返回 bool。"""
    from croe.interface.writer.result_writer import _result_flag_to_bool

    # bool 原样
    assert _result_flag_to_bool(True) is True
    assert _result_flag_to_bool(False) is False

    # str (历史 InterfaceCaseResultEnum 值, 假设哪天被恢复, 至少不会写反)
    assert _result_flag_to_bool("ERROR") is False
    assert _result_flag_to_bool("FAIL") is False
    assert _result_flag_to_bool("false") is False
    assert _result_flag_to_bool("0") is False
    assert _result_flag_to_bool("SUCCESS") is True
    assert _result_flag_to_bool("OK") is True
    assert _result_flag_to_bool("") is False

    # None 保守
    assert _result_flag_to_bool(None) is False

    # 兜底
    assert _result_flag_to_bool(0) is False
    assert _result_flag_to_bool(1) is True
    assert _result_flag_to_bool(["x"]) is True

@pytest.mark.unit
def test_bug_m7_status_enum_unchanged(bug_m7_marker):
    """[BUG-M7] 字符串状态用 InterfaceAPIStatusEnum, 跟 result 列分开。"""
    # 这是删除 InterfaceCaseResultEnum 之后, 唯一剩的 str 状态枚举
    assert InterfaceAPIStatusEnum.RUNNING == "RUNNING"
    assert InterfaceAPIStatusEnum.OVER == "OVER"
    # 写 result 列时千万别用 str, 但 status 列 (String) 可以
