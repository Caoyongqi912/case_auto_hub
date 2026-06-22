"""`to_dict`/`map` 必须覆盖 JTI(Joined Table Inheritance)所有列。"""

import pytest

from app.model.interfaceAPIModel.interfaceResultModel import (
    APIStepContentResult,
    GroupStepContentResult,
)
from tests.croe.interface._bug_ids import BUG_M3

@pytest.fixture
def bug_m3_marker():
    return BUG_M3

@pytest.mark.unit
def test_bug_m3_api_step_content_result_to_dict_includes_subclass_field(bug_m3_marker):
    """APIStepContentResult.to_dict() 应包含子类字段 interface_result_id。"""
    obj = APIStepContentResult(
        case_result_id=1,
        task_result_id=2,
        content_id=3,
        content_name="t",
        content_step=1,
        content_type=1,  # STEP_API
        interface_result_id=999,  # 子类字段
    )
    result = obj.to_dict()
    assert result.get("interface_result_id") == 999, (
        f"[{BUG_M3}] to_dict 应包含子类字段 interface_result_id=999,"
        f"实际 {result.get('interface_result_id')!r}"
    )

@pytest.mark.unit
def test_bug_m3_group_step_content_result_to_dict_includes_subclass_fields(bug_m3_marker):
    """GroupStepContentResult.to_dict() 应包含子类字段 total/success/fail。"""
    obj = GroupStepContentResult(
        case_result_id=1,
        content_id=2,
        content_name="g",
        content_step=1,
        content_type=2,  # STEP_API_GROUP
        total_api_num=10,
        success_api_num=8,
        fail_api_num=2,
    )
    result = obj.to_dict()
    for key, expected in [
        ("total_api_num", 10),
        ("success_api_num", 8),
        ("fail_api_num", 2),
    ]:
        assert result.get(key) == expected, (
            f"[{BUG_M3}] to_dict 应包含 {key}={expected},"
            f"实际 {result.get(key)!r}"
        )
