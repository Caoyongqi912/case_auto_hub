"""BUG-D5 回归测试: query_steps 不应有 5 个死 joinedload。"""

import inspect
import re

import pytest

from app.mapper.interfaceApi.interfaceCaseMapper import InterfaceCaseMapper
from tests.croe.interface._bug_ids import BUG_D5

@pytest.fixture
def bug_d5_marker():
    return BUG_D5

@pytest.mark.unit
def test_bug_d5_query_steps_no_joinedload_options(bug_d5_marker):
    """[BUG-D5] query_steps 的 .options() 不应包含 joinedload(relationship)。"""
    src = inspect.getsource(InterfaceCaseMapper.query_steps)
    # 死代码: 5 个关系 joinedload
    dead_joinedloads = [
        "joinedload(APIStepContent.interface_api)",
        "joinedload(ConditionStepContent.interface_condition)",
        "joinedload(LoopStepContent.interface_loop)",
        "joinedload(GroupStepContent.interface_group)",
        "joinedload(DBStepContent.db_execute)",
    ]
    for dead in dead_joinedloads:
        assert dead not in src, (
            f"[{BUG_D5}] {dead} 是死代码 (5 个 step strategy 都不用), "
            f"5x LEFT JOIN 行宽膨胀, 应删"
        )

@pytest.mark.unit
def test_bug_d5_query_steps_no_joinedload_import(bug_d5_marker):
    """[BUG-D5] interfaceCaseMapper 不再 import joinedload (没人用了)。"""
    import app.mapper.interfaceApi.interfaceCaseMapper as m
    src = inspect.getsource(m)
    # 如果以后又用, 再加回
    assert "from sqlalchemy.orm import joinedload" not in src, (
        f"[{BUG_D5}] interfaceCaseMapper 不再需要 joinedload, 应删 import"
    )

@pytest.mark.unit
def test_bug_d5_query_steps_no_options_clause(bug_d5_marker):
    """[BUG-D5] query_steps 不应在执行体里有 .options() 子句 (注释不算)。"""
    src = inspect.getsource(InterfaceCaseMapper.query_steps)
    # 去掉所有 # 注释行, 再检查
    code_lines = [l for l in src.split("\n") if not l.strip().startswith("#")]
    code = "\n".join(code_lines)
    # 死代码: 5 个 relationship joinedload 都被删了, .options() 也应跟着删
    assert ".options(" not in code, (
        f"[{BUG_D5}] query_steps 不应有 .options(), "
        f"因为没东西需要预加载 (5 个 step strategy 都不读 relationship)"
    )
