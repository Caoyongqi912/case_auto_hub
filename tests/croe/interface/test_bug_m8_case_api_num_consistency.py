"""
BUG-M8 回归测试: InterfaceCase.case_api_num 必须跟实际 step 关联数对账。

详见 docs/review/run_interface_case_deep_review.md。

根因: ±1/±N 散落在 5+ 个同步点 (associate_* + copy_step + remove_step),
任何一处漏写/多写都让 case_api_num 跟实际 step 数对不上, 比如:
- 移除 GROUP 时 -1 写死, 但 group 内部含 N 个 API, 实际应 -N
- 批量操作中途失败, 部分 ±1 没回滚, 字段永久错位

修法: 加 `recompute_case_api_num` classmethod, 事务末尾兜底对账:
- COUNT(*) FROM interface_case_content_association WHERE case_id=?
- UPDATE interface_case SET case_api_num=? WHERE id=?

任何漂移都会被纠正, 而不用逐个去替换 ±1/±N 同步点。
"""
import pytest
import re
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from app.mapper.interfaceApi.interfaceCaseMapper import InterfaceCaseMapper
from tests.croe.interface._bug_ids import BUG_M8


@pytest.fixture
def bug_m8_marker():
    return BUG_M8


def _mock_session_with_actual_count(actual_count: int) -> MagicMock:
    """
    构造一个 mock session:
    - SELECT 返回带 .all() 的结果 (长度 = actual_count)
    - UPDATE 不需要返回值
    """
    session = MagicMock()
    # 区分 select 和 update 通过 stmt 字符串
    select_result = MagicMock()
    select_result.all = MagicMock(return_value=[object()] * actual_count)
    update_result = MagicMock()

    async def fake_execute(stmt):
        s = str(stmt).upper()
        if "UPDATE" in s:
            return update_result
        return select_result

    # 用 AsyncMock 包装 fake_expose, 让它有 call_count / call_args_list
    session.execute = AsyncMock(side_effect=fake_execute)
    return session


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_m8_recompute_writes_actual_count(bug_m8_marker):
    """[BUG-M8] recompute_case_api_num 应 COUNT 关联表 + UPDATE 字段。"""
    session = _mock_session_with_actual_count(3)

    result = await InterfaceCaseMapper.recompute_case_api_num(case_id=42, session=session)

    assert result == 3, f"[{BUG_M8}] 应返回实际 step 数 3, 实际 {result}"
    assert session.execute.call_count == 2, (
        f"[{BUG_M8}] recompute 应执行 2 条 SQL (COUNT + UPDATE), "
        f"实际 {session.execute.call_count} 条"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_m8_recompute_corrects_drift(bug_m8_marker):
    """
    [BUG-M8] 即使 case_api_num 漂移, recompute 后必须跟实际 step 数一致。

    场景: case_api_num=10 (历史漂移), 实际只有 2 个 step,
    recompute 后应写回 2, 而不是 10+1=11。
    """
    session = _mock_session_with_actual_count(actual_count=2)

    result = await InterfaceCaseMapper.recompute_case_api_num(case_id=99, session=session)

    assert result == 2, f"[{BUG_M8}] 漂移场景应纠正为 2, 实际 {result}"
    # 第二次 execute (UPDATE) 的 stmt 应包含 case_api_num
    update_call_args = session.execute.call_args_list[1]
    update_stmt = update_call_args[0][0]
    compiled = str(update_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "case_api_num" in compiled, (
        f"[{BUG_M8}] UPDATE 语句应设置 case_api_num, 实际: {compiled}"
    )


@pytest.mark.unit
def test_bug_m8_callers_pass_session(bug_m8_marker):
    """
    [BUG-M8] 7 个同步点的事务末尾都应调 recompute (跟现有 session 同事务)。

    用 grep 静态检查所有 call site 都传了 session, 跟前面的 ±N update 共享事务。
    """
    mapper_path = Path("app/mapper/interfaceApi/interfaceCaseMapper.py")
    text = mapper_path.read_text(encoding="utf-8")

    call_pattern = re.compile(r"recompute_case_api_num\s*\(\s*case_id\s*,\s*session\s*\)")
    calls = call_pattern.findall(text)
    helper_def_pattern = re.compile(
        r"async def recompute_case_api_num\s*\(\s*cls\s*,\s*case_id\s*,\s*session\s*"
    )
    helper_defs = helper_def_pattern.findall(text)
    call_count = len(calls) - len(helper_defs)
    assert call_count == 7, (
        f"[{BUG_M8}] 应在 7 个事务末尾调 recompute (associate_interfaces/groups/"
        f"condition/loop/db + copy_step + remove_step), 实际 {call_count} 个"
    )
