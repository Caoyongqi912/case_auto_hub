"""BUG-M1 回归测试:`InterfaceCaseContents.target_id` 不应是 ClassVar。"""

import pytest

from app.model.interfaceAPIModel.contents import APIStepContent
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
)
from tests.croe.interface._bug_ids import BUG_M1

@pytest.fixture
def bug_m1_marker():
    """标记当前测试对应的 BUG 编号,方便报告。"""
    return BUG_M1

@pytest.mark.security
@pytest.mark.unit
def test_bug_m1_api_step_content_to_dict_contains_target_id(bug_m1_marker):
    """BUG-M1: APIStepContent.to_dict() 应包含 target_id 的真实值,而非 None。"""
    # Arrange:直接构造一个内存中的 APIStepContent
    content = APIStepContent(
        target_id=42,
        content_name="测试API",
        content_type=1,
    )
    # Act
    result = content.to_dict()

    # Assert
    assert result.get("target_id") == 42, (
        f"[{BUG_M1}] to_dict 应当返回 target_id=42,实际得到 {result.get('target_id')!r}"
    )

@pytest.mark.security
@pytest.mark.unit
def test_bug_m1_base_class_has_no_classvar_target_id(bug_m1_marker):
    """BUG-M1: 基类不应把 target_id 声明为 ClassVar,会遮蔽子类的 Column 定义。"""
    # Arrange / Act
    has_classvar = "target_id" in InterfaceCaseContents.__dict__

    # Assert
    assert not has_classvar, (
        f"[{BUG_M1}] InterfaceCaseContents.__dict__ 不应包含 target_id "
        f"(当前值: {InterfaceCaseContents.__dict__.get('target_id')!r}),"
        f"应让每个子类自行定义 Column。"
    )
