"""
BUG-M3 回归测试:`to_dict`/`map` 必须覆盖 JTI(Joined Table Inheritance)所有列。

详见 docs/review/run_interface_case_deep_review.md。

V2 报告原文只指出 BaseModel.to_dict 只用 self.__table__.columns,
但实际触发面更广 — 任何"先写基础字段再循环子类 mapper"的 to_dict
(包括 InterfaceCaseContentResult.to_dict)只要过滤条件用
'mapper.local_table.name != self.__tablename__',在子类实例上就会
把自己跳过,导致子类列丢失。

所以测试要两条:
- BaseModel 子类直接调用:验证 inspect 版本能拿到 JTI 全部列
- InterfaceCaseContentResult 子类(如 APIStepContentResult):验证子类
  独有列(interface_result_id / total_api_num 等)被包含
"""
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
    """[BUG-M3] APIStepContentResult.to_dict() 应包含子类字段 interface_result_id。"""
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
    """[BUG-M3] GroupStepContentResult.to_dict() 应包含子类字段 total/success/fail。"""
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
