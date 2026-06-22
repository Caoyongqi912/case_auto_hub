"""`interface_case_name` / `interface_case_desc` 长度不足。"""

import pytest
from sqlalchemy import String

from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceCaseResult
from tests.croe.interface._bug_ids import BUG_M2

@pytest.fixture
def bug_m2_marker():
    return BUG_M2

@pytest.mark.unit
def test_bug_m2_case_result_name_length_supports_case_title(bug_m2_marker):
    """interface_case_name 长度应 >= case_title 长度。"""
    case_title_col = InterfaceCase.__table__.columns["case_title"]
    case_result_name_col = InterfaceCaseResult.__table__.columns["interface_case_name"]

    assert isinstance(case_title_col.type, String), "case_title 必须是 String 列"
    assert isinstance(case_result_name_col.type, String), "interface_case_name 必须是 String 列"

    case_title_len = case_title_col.type.length
    case_result_len = case_result_name_col.type.length

    assert case_result_len >= case_title_len, (
        f"[{BUG_M2}] interface_case_name 长度 ({case_result_len}) "
        f"必须 >= case_title 长度 ({case_title_len}),否则长标题会 Data too long"
    )

@pytest.mark.unit
def test_bug_m2_case_result_desc_length_supports_case_desc(bug_m2_marker):
    """interface_case_desc 长度应 >= case_desc 长度。"""
    case_desc_col = InterfaceCase.__table__.columns["case_desc"]
    case_result_desc_col = InterfaceCaseResult.__table__.columns["interface_case_desc"]

    assert isinstance(case_desc_col.type, String)
    assert isinstance(case_result_desc_col.type, String)

    case_desc_len = case_desc_col.type.length
    case_result_desc_len = case_result_desc_col.type.length

    assert case_result_desc_len >= case_desc_len, (
        f"[{BUG_M2}] interface_case_desc 长度 ({case_result_desc_len}) "
        f"必须 >= case_desc 长度 ({case_desc_len}),否则长描述会 Data too long"
    )
