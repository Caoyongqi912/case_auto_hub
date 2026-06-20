"""BUG-M6-hotfix 回归测试: 需要子类列的查询必须显式 with_polymorphic。"""

import pytest
import re
from pathlib import Path

from app.model.interfaceAPIModel.interfaceResultModel import (
    InterfaceCaseContentResult,
    APIStepContentResult,
    GroupStepContentResult,
    ConditionStepContentResult,
    ScriptStepContentResult,
    DBStepContentResult,
    WaitStepContentResult,
    AssertStepContentResult,
    LoopStepContentResult,
)
from tests.croe.interface._bug_ids import BUG_M6

ALL_8_SUBCLASSES = [
    APIStepContentResult,
    GroupStepContentResult,
    ConditionStepContentResult,
    ScriptStepContentResult,
    DBStepContentResult,
    WaitStepContentResult,
    AssertStepContentResult,
    LoopStepContentResult,
]

@pytest.fixture
def bug_m6_marker():
    return BUG_M6

@pytest.mark.unit
def test_bug_m6_base_model_no_wildcard(bug_m6_marker):
    """[BUG-M6] 基类的 __mapper_args__ 不应有 with_polymorphic='*'。"""
    mapper_args = dict(InterfaceCaseContentResult.__mapper_args__)
    assert mapper_args.get("with_polymorphic") != "*", (
        f"[{BUG_M6}] InterfaceCaseContentResult 仍带 with_polymorphic='*', "
        f"应删, 改在需要的查询里显式 with_polymorphic"
    )

@pytest.mark.unit
def test_bug_m6_query_steps_result_uses_with_polymorphic(bug_m6_marker):
    """[BUG-M6-hotfix] query_steps_result 必须显式 with_polymorphic。"""
    import inspect
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceContentStepResultMapper
    src = inspect.getsource(InterfaceContentStepResultMapper.query_steps_result)
    assert "with_polymorphic" in src, (
        f"[{BUG_M6}] query_steps_result 必须显式 with_polymorphic, "
        f"否则 to_dict() 访问子类列时 session 已关会报 "
        f"'is not bound to a Session'"
    )

@pytest.mark.unit
def test_bug_m6_query_steps_result_lists_all_subclasses(bug_m6_marker):
    """
    [    """
    import inspect
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceContentStepResultMapper
    src = inspect.getsource(InterfaceContentStepResultMapper.query_steps_result)

    for cls in ALL_8_SUBCLASSES:
        assert cls.__name__ in src, (
            f"[{BUG_M6}] query_steps_result 的 with_polymorphic 必须列出 "
            f"{cls.__name__}, 漏掉的话该类型 step 的 to_dict() 会失败"
        )

@pytest.mark.unit
def test_bug_m6_query_steps_result_joinedload_uses_poly(bug_m6_marker):
    """
    [    """
    import inspect
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceContentStepResultMapper
    src = inspect.getsource(InterfaceContentStepResultMapper.query_steps_result)
    # 用 poly.APIStepContentResult 形式
    assert "poly.APIStepContentResult" in src, (
        f"[{BUG_M6}] joinedload 必须用 poly.APIStepContentResult, "
        f"不能用原 APIStepContentResult, 否则根实体不对会报错"
    )
    assert "poly.GroupStepContentResult" in src
    assert "poly.ConditionStepContentResult" in src
    # 不能用裸的 APIStepContentResult.interface_result (会失败)
    assert "joinedload(APIStepContentResult.interface_result)" not in src, (
        f"[{BUG_M6}] joinedload 不能用裸 APIStepContentResult.interface_result, "
        f"必须用 poly.APIStepContentResult.interface_result"
    )

@pytest.mark.unit
def test_bug_m6_to_dict_needs_subclass_columns(bug_m6_marker):
    """
    [    """
    import inspect
    from app.model.interfaceAPIModel.interfaceResultModel import InterfaceCaseContentResult
    src = inspect.getsource(InterfaceCaseContentResult.to_dict)
    # 必须包含 self_and_descendants 反射
    assert "self_and_descendants" in src, (
        f"[{BUG_M6}] BaseModel.to_dict() 应该用 self_and_descendants 反射"
    )
    # 必须有 getattr(self, col.name)
    assert "getattr(self" in src, (
        f"[{BUG_M6}] to_dict() 应该用 getattr 访问子类列"
    )
