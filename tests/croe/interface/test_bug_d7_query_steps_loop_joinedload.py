"""[BUG-D7] query_steps_result joinedload 漏 LoopStepContentResult.interface_results"""

import ast
import inspect
import re
import pytest

def _get_query_steps_result_src() -> str:
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceContentStepResultMapper
    return inspect.getsource(InterfaceContentStepResultMapper.query_steps_result)

def _extract_joinedload_lines(src: str):
    """提取所有 joinedload(poly.X.Y) 子句里的 'X.Y' 标识"""
    pattern = re.compile(r"joinedload\(\s*poly\.(\w+)\.(\w+)\s*\)")
    return pattern.findall(src)

def test_bug_d7_loop_joinedload_present_in_query():
    """
    核心回归: query_steps_result 必须 joinedload poly.LoopStepContentResult.interface_results
    """
    src = _get_query_steps_result_src()
    joinedloads = _extract_joinedload_lines(src)
    # 期望至少包含 Loop.interface_results
    assert ("LoopStepContentResult", "interface_results") in joinedloads, (
        f"[BUG-D7] query_steps_result 漏 joinedload(poly.LoopStepContentResult.interface_results)。"
        f"\n当前 joinedload 列表: {joinedloads}"
        f"\n→ 加上: joinedload(poly.LoopStepContentResult.interface_results),"
        f"\n  否则循环步骤的 to_dict() 拿不到 interface_results, data 永远是 []"
    )

def test_bug_d7_all_parent_subtype_relationships_joinedload():
    """
    防再次漏: 列出所有有 interface_result(s) relationship 的 parent subtype,
    query_steps_result 必须对每个都 joinedload。
    """
    from app.model.interfaceAPIModel.interfaceResultModel import (
        APIStepContentResult,
        GroupStepContentResult,
        ConditionStepContentResult,
        ScriptStepContentResult,
        DBStepContentResult,
        WaitStepContentResult,
        AssertStepContentResult,
        LoopStepContentResult,
    )
    from enums.CaseEnum import CaseStepContentType

    PARENT_STEP_TYPES = {
        CaseStepContentType.STEP_API_GROUP,
        CaseStepContentType.STEP_API_CONDITION,
        CaseStepContentType.STEP_LOOP,
    }

    # 找出所有 parent subtype + 它们有的 relationship
    expected = []
    for cls in (
        APIStepContentResult, GroupStepContentResult, ConditionStepContentResult,
        ScriptStepContentResult, DBStepContentResult, WaitStepContentResult,
        AssertStepContentResult, LoopStepContentResult,
    ):
        # 取 polymorphic_identity 决定它对应哪个 content_type
        pid = cls.__mapper_args__.get("polymorphic_identity")
        if pid not in PARENT_STEP_TYPES:
            continue
        # 找该 class 上所有 relationship (filter 掉非 relationship 属性)
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            attr = getattr(cls, attr_name, None)
            if not hasattr(attr, "property"):
                continue
            prop = attr.property
            # relationship 类型
            from sqlalchemy.orm import RelationshipProperty
            if not isinstance(prop, RelationshipProperty):
                continue
            expected.append((cls.__name__, attr_name))

    joinedloads = _extract_joinedload_lines(_get_query_steps_result_src())

    for cls_name, rel_name in expected:
        assert (cls_name, rel_name) in joinedloads, (
            f"[BUG-D7] query_steps_result 漏 joinedload({cls_name}.{rel_name})。"
            f"\n所有 parent subtype relationship: {expected}"
            f"\n当前 joinedload 列表: {joinedloads}"
        )

def test_bug_d7_loop_model_has_interface_results_relationship():
    """
    配套防御: 锁住 LoopStepContentResult 仍然有 interface_results relationship。
    万一以后 model 重构不小心删掉, 这条会爆。
    """
    from app.model.interfaceAPIModel.interfaceResultModel import LoopStepContentResult
    from sqlalchemy.orm import RelationshipProperty

    rel = getattr(LoopStepContentResult, "interface_results", None)
    assert rel is not None, "LoopStepContentResult.interface_results relationship 没了"
    assert isinstance(rel.property, RelationshipProperty), (
        "LoopStepContentResult.interface_results 不是 RelationshipProperty"
    )
    # 指向 InterfaceResult
    assert rel.property.mapper.class_.__name__ == "InterfaceResult"
