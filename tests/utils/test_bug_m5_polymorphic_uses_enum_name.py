"""BUG-M5 回归测试:`content_type` 列必须存 enum NAME 而不是 int value,"""

import inspect

import pytest
from sqlalchemy import Enum, Integer

from enums.CaseEnum import CaseStepContentType
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
)
from app.model.interfaceAPIModel.interfaceResultModel import (
    InterfaceCaseContentResult,
)
from tests.croe.interface._bug_ids import BUG_M5

@pytest.fixture
def bug_m5_marker():
    return BUG_M5

def _content_type_column(model):
    """从模型上拿 content_type Column 对象, 不用走 SQLAlchemy inspect, 直接读 attribute。"""
    from sqlalchemy import inspect as sa_inspect
    mapper = sa_inspect(model)
    return mapper.columns["content_type"]

@pytest.mark.unit
def test_bug_m5_contents_uses_enum_type_not_integer(bug_m5_marker):
    """[BUG-M5] InterfaceCaseContents.content_type 必须用 Enum, 不能是 Integer。"""
    col = _content_type_column(InterfaceCaseContents)
    assert isinstance(col.type, Enum), (
        f"[{BUG_M5}] InterfaceCaseContents.content_type 应为 Enum, "
        f"实际是 {type(col.type).__name__} (重排枚举会炸库)"
    )
    assert not isinstance(col.type, Integer), (
        f"[{BUG_M5}] content_type 不应是 Integer, 实际是 Integer"
    )
    # 必须用 CaseStepContentType 做枚举
    assert col.type.enum_class is CaseStepContentType, (
        f"[{BUG_M5}] Enum 应绑 CaseStepContentType, "
        f"实际 {col.type.enum_class!r}"
    )

@pytest.mark.unit
def test_bug_m5_result_uses_enum_type_not_integer(bug_m5_marker):
    """[BUG-M5] InterfaceCaseContentResult.content_type 必须用 Enum, 不能是 Integer。"""
    col = _content_type_column(InterfaceCaseContentResult)
    assert isinstance(col.type, Enum), (
        f"[{BUG_M5}] InterfaceCaseContentResult.content_type 应为 Enum, "
        f"实际是 {type(col.type).__name__}"
    )
    assert col.type.enum_class is CaseStepContentType

@pytest.mark.unit
def test_bug_m5_enum_uses_native_enum_false_for_portability(bug_m5_marker):
    """[BUG-M5] Enum 必须 native_enum=False + length, 才能跨 MySQL 5/8 兼容。"""
    col = _content_type_column(InterfaceCaseContents)
    assert col.type.native_enum is False, (
        f"[{BUG_M5}] native_enum=False 跨 MySQL 版本兼容, 实际是 {col.type.native_enum}"
    )
    assert col.type.length is not None and col.type.length > 0, (
        f"[{BUG_M5}] Enum 必须 length>0 供 VARCHAR 存储, 实际 length={col.type.length}"
    )

@pytest.mark.unit
def test_bug_m5_polymorphic_on_still_uses_content_type(bug_m5_marker):
    """[BUG-M5] polymorphic_on 仍然挂在 content_type 上, 跟改 Column 类型不冲突。"""
    mapper_args = InterfaceCaseContents.__mapper_args__
    assert "polymorphic_on" in mapper_args, (
        f"[{BUG_M5}] polymorphic_on 必须保留, 否则多态失效"
    )
    # polymorphic_on 应当是 content_type 这个 Column
    pol_on = mapper_args["polymorphic_on"]
    pol_col = pol_on.key if hasattr(pol_on, "key") else None
    assert pol_col == "content_type", (
        f"[{BUG_M5}] polymorphic_on 应挂在 content_type, 实际挂 {pol_col!r}"
    )
