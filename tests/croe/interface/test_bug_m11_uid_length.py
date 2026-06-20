"""BUG-M11 回归测试:`*_uid` 字段长度应与 `BaseModel.uid` (50) 对齐。"""

import pytest
from sqlalchemy import String

from app.model.interfaceAPIModel.interfaceResultModel import (
    InterfaceResult,
    InterfaceCaseResult,
    InterfaceTaskResult,
)
from app.model.basic import BaseModel
from tests.croe.interface._bug_ids import BUG_M11

@pytest.fixture
def bug_m11_marker():
    return BUG_M11

@pytest.mark.unit
def test_bug_m11_uid_columns_at_least_base_uid_length(bug_m11_marker):
    """[BUG-M11] 所有 *_uid 列长度应 >= BaseModel.uid 长度(50)。"""
    base_uid_col = InterfaceResult.__table__.columns["uid"]  # BaseModel 是 abstract,借具体子类拿列
    assert isinstance(base_uid_col.type, String)
    base_uid_len = base_uid_col.type.length
    assert base_uid_len == 50, f"BaseModel.uid 长度应为 50,实际 {base_uid_len}"

    for model, col_name in [
        (InterfaceResult, "interface_uid"),
        (InterfaceCaseResult, "interface_case_uid"),
        (InterfaceTaskResult, "task_uid"),
    ]:
        col = model.__table__.columns.get(col_name)
        if col is None:
            continue
        assert isinstance(col.type, String), f"{model.__name__}.{col_name} 必须为 String"
        col_len = col.type.length
        assert col_len >= base_uid_len, (
            f"[{BUG_M11}] {model.__name__}.{col_name} 长度 ({col_len}) "
            f"必须 >= BaseModel.uid 长度 ({base_uid_len})"
        )
