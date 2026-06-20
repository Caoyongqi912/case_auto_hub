"""BUG-M6 回归测试: InterfaceCaseContentResult 不应使用 with_polymorphic='*'。"""

import pytest

from app.model.interfaceAPIModel.interfaceResultModel import InterfaceCaseContentResult
from tests.croe.interface._bug_ids import BUG_M6

@pytest.fixture
def bug_m6_marker():
    return BUG_M6

@pytest.mark.unit
def test_bug_m6_no_wildcard_polymorphic(bug_m6_marker):
    """[BUG-M6] InterfaceCaseContentResult 不应有 with_polymorphic='*'。"""
    mapper_args = dict(InterfaceCaseContentResult.__mapper_args__)
    assert mapper_args.get("with_polymorphic") != "*", (
        f"[{BUG_M6}] InterfaceCaseContentResult 仍带 with_polymorphic='*', "
        f"会导致每次 SELECT 都自动 JOIN 8 个子类表, 带宽/内存/DB 计划都浪费"
    )

@pytest.mark.unit
def test_bug_m6_polymorphic_on_unchanged(bug_m6_marker):
    """[BUG-M6] polymorphic_on=content_type 必须保留, 这是 M5 修复的根基。"""
    mapper_args = dict(InterfaceCaseContentResult.__mapper_args__)
    assert "polymorphic_on" in mapper_args, (
        f"[{BUG_M6}] polymorphic_on 必须在, 否则多态根本起不来"
    )
    assert mapper_args["polymorphic_on"].key == "content_type", (
        f"[{BUG_M6}] polymorphic_on 应绑定到 content_type 列"
    )

@pytest.mark.unit
def test_bug_m6_polymorphic_identity_unchanged(bug_m6_marker):
    """[BUG-M6] polymorphic_identity=None 是基类默认值, 不能误删。"""
    mapper_args = dict(InterfaceCaseContentResult.__mapper_args__)
    assert "polymorphic_identity" in mapper_args, (
        f"[{BUG_M6}] polymorphic_identity 必须在, 基类默认 None"
    )
