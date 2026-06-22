"""删 `__allow_unmapped__ = True` 不应导致 model 注册失败。"""

from pathlib import Path

import pytest

from app.model.interfaceAPIModel.interfaceResultModel import InterfaceCaseContentResult
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
)
from tests.croe.interface._bug_ids import BUG_M10

REPO_ROOT = Path(__file__).resolve().parents[3]

def _src(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")

@pytest.fixture
def bug_m10_marker():
    return BUG_M10

# --------------------------------------------------------------------------- #
# M10.1 / M10.2 - 源码层: 0 处 __allow_unmapped__ = True
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_bug_m10_no_allow_unmapped_in_result_model(bug_m10_marker):
    """interfaceResultModel.py 不应再出现 __allow_unmapped__ = True。"""
    src = _src("app/model/interfaceAPIModel/interfaceResultModel.py")
    assert "__allow_unmapped__" not in src, (
        f"[{BUG_M10}] __allow_unmapped__ = True 仍然在 interfaceResultModel.py 中, "
        "会让 SQLAlchemy 2.0 跳过注解到 Column 的转换 (declarative class 不需要)。"
    )

@pytest.mark.unit
def test_bug_m10_no_allow_unmapped_in_contents_model(bug_m10_marker):
    """interfaceCaseContentsModel.py 不应再出现 __allow_unmapped__ = True。"""
    src = _src("app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py")
    assert "__allow_unmapped__" not in src, (
        f"[{BUG_M10}] __allow_unmapped__ = True 仍然在 interfaceCaseContentsModel.py 中。"
    )

@pytest.mark.unit
def test_bug_m10_models_still_register_normally(bug_m10_marker):
    """删 __allow_unmapped__ 后 model 仍能正常建表 / 字段映射。"""
    # 基类 __table__ 存在 + 关键列存在, 说明 declarative mapping 没被破坏
    base_table = InterfaceCaseContentResult.__table__
    assert base_table.name == "interface_case_content_result"
    assert "case_result_id" in base_table.columns
    assert "content_type" in base_table.columns
    assert "id" in base_table.columns

    content_table = InterfaceCaseContents.__table__
    assert content_table.name == "interface_case_step_content"
    assert "content_type" in content_table.columns
    assert "content_type" in content_table.columns

    # mapped class 不应是 Unmapped (说明注解到 Column 的转换正常)
    assert hasattr(InterfaceCaseContentResult, "__mapper__")
    assert hasattr(InterfaceCaseContents, "__mapper__")
    assert InterfaceCaseContentResult.__mapper__.columns["case_result_id"].name == "case_result_id"
    assert InterfaceCaseContents.__mapper__.columns["content_type"].name == "content_type"
