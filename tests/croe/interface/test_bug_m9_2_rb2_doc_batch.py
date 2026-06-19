"""
[BUG-M9-2 + RB2 + DOC] 3 个 P0 隐藏 BUG 一锅端, 来自 f5d5a8a 后的 code review。

BUG-M9-2: result_writer.write_step_result 写 status="SUCCESS"/"FAIL" 字面量,
   跟 M9 修的 8 个 step_content 不一致, 当 status 列改成 enum 类型时会写错。
   修: 统一走 StepStatusEnum.SUCCESS / .FAIL。

BUG-RB2: InterfaceRunner.run_interface_by_task 漏调 init_global_headers,
   任务执行时 g_headers 永远为 [], 全局 header 全部丢失。
   修: 函数体开头加 await self.init_global_headers()。

BUG-DOC: recompute_case_result_nums 之前 session=None 直接 raise,
   但调用方注释写"自管事务", 实际静默 except 丢对账。
   修: session=None 时开自己的 cls.transaction()。
"""
import inspect
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.croe.interface._bug_ids import BUG_M9_2, BUG_RB2, BUG_DOC


# --------------------------------------------------------------------------- #
# BUG-M9-2: result_writer.write_step_result status 走 enum
# --------------------------------------------------------------------------- #

def test_bug_m9_2_result_writer_status_uses_step_status_enum():
    """[BUG-M9-2] result_writer.write_step_result 的 result_data['status']
    应走 StepStatusEnum.SUCCESS / .FAIL, 不写 "SUCCESS"/"FAIL" 字面量。

    锁住: 当 status 列改成 enum 类型时, 写错值会被静态发现而不是上线炸。
    """
    from croe.interface.writer.result_writer import ResultWriter

    src = inspect.getsource(ResultWriter.write_step_result)

    # 1. status 必须用 StepStatusEnum
    assert "StepStatusEnum" in src, (
        f"[{BUG_M9_2}] write_step_result 应 import 并使用 StepStatusEnum, "
        f"跟 8 个 step_content_*.py 统一"
    )

    # 2. 锁 status= 这一行必须走 enum, 不写 SUCCESS/FAIL 字面量。
    #    只在 result_data = { ... } 块内匹配, 避免误命中 docstring /
    #    修复注释里出现 SUCCESS/FAIL 这两个词。
    block_m = re.search(r"result_data\s*=\s*\{.*?\}", src, re.DOTALL)
    assert block_m, (
        f"[{BUG_M9_2}] 找不到 result_data = {{...}} 块, 源码结构变了"
    )
    block = block_m.group(0)
    assert '"SUCCESS"' not in block, (
        f"[{BUG_M9_2}] result_data 里不应再写 status=\"SUCCESS\" 字面量, "
        f"应为 StepStatusEnum.SUCCESS"
    )
    assert "'SUCCESS'" not in block, (
        f"[{BUG_M9_2}] result_data 里不应再写 status='SUCCESS' 字面量"
    )
    assert '"FAIL"' not in block, (
        f"[{BUG_M9_2}] result_data 里不应再写 status=\"FAIL\" 字面量, "
        f"应为 StepStatusEnum.FAIL"
    )
    assert "'FAIL'" not in block, (
        f"[{BUG_M9_2}] result_data 里不应再写 status='FAIL' 字面量"
    )
    # status 这一行的 RHS 必须是 enum
    status_line_m = re.search(r'[\'"]status[\'"]\s*:\s*([^,\n]+)', block)
    assert status_line_m, f"[{BUG_M9_2}] result_data 缺 status 字段"
    rhs = status_line_m.group(1).strip()
    assert rhs.startswith("StepStatusEnum."), (
        f"[{BUG_M9_2}] result_data['status'] 应为 StepStatusEnum.*, 实际: {rhs!r}"
    )


def test_bug_m9_2_step_content_status_consistency():
    """[BUG-M9-2] 8 个 step_content_*.py 跟 result_writer 的 status 走法应该一致
    (都是 StepStatusEnum)。
    """
    from croe.interface.executor.step_content import (
        step_content_api, step_content_assert, step_content_condition,
        step_content_db, step_content_group, step_content_loop,
        step_content_script, step_content_wait,
    )
    from croe.interface.writer.result_writer import ResultWriter

    strategy_modules = [
        step_content_api, step_content_assert, step_content_condition,
        step_content_db, step_content_group, step_content_loop,
        step_content_script, step_content_wait,
    ]
    for mod in strategy_modules:
        mod_src = inspect.getsource(mod)
        if "status=" in mod_src or "status =" in mod_src:
            assert "StepStatusEnum" in mod_src, (
                f"[{BUG_M9_2}] {mod.__name__} 写 status 但没用 StepStatusEnum, 不一致"
            )

    writer_src = inspect.getsource(ResultWriter.write_step_result)
    assert "StepStatusEnum" in writer_src, (
        f"[{BUG_M9_2}] ResultWriter.write_step_result 必须用 StepStatusEnum"
    )

# --------------------------------------------------------------------------- #
# BUG-RB2: run_interface_by_task 调 init_global_headers
# --------------------------------------------------------------------------- #

def test_bug_rb2_run_interface_by_task_calls_init_global_headers():
    """[BUG-RB2] run_interface_by_task 函数体必须调 init_global_headers(),
    跟另外 3 个入口对齐。否则任务执行时全局 header 永远丢失。
    """
    from croe.interface.runner import InterfaceRunner

    src = inspect.getsource(InterfaceRunner.run_interface_by_task)

    # 必须在 for attempt 循环之前调 init_global_headers
    init_pos = src.find("init_global_headers")
    assert init_pos > 0, (
        f"[{BUG_RB2}] run_interface_by_task 漏调 init_global_headers(), "
        f"任务执行时 g_headers 永远为 []"
    )

    # 必须在 for attempt 循环之前
    for_pos = src.find("for attempt in range")
    assert for_pos > init_pos, (
        f"[{BUG_RB2}] init_global_headers 应在 for attempt 循环之前, "
        f"实际 for_pos={for_pos}, init_pos={init_pos}"
    )

    # 必须 await self.init_global_headers()
    assert "await self.init_global_headers" in src, (
        f"[{BUG_RB2}] 必须 await self.init_global_headers()"
    )


def test_bug_rb2_all_four_entries_init_global_headers():
    """[BUG-RB2] 4 个执行入口 (try_interface / try_group / run_interface_case /
    run_interface_by_task) 全部应调 init_global_headers, 行为一致。
    """
    from croe.interface.runner import InterfaceRunner

    for method_name in (
        "try_interface", "try_group", "run_interface_case", "run_interface_by_task"
    ):
        method = getattr(InterfaceRunner, method_name)
        src = inspect.getsource(method)
        assert "init_global_headers" in src, (
            f"[{BUG_RB2}] {method_name} 漏调 init_global_headers, "
            f"4 个入口行为不一致"
        )


# --------------------------------------------------------------------------- #
# BUG-DOC: recompute_case_result_nums session=None 不再 raise
# --------------------------------------------------------------------------- #

def test_bug_doc_recompute_session_none_no_longer_raises():
    """[BUG-DOC] session=None 之前 raise ValueError, 但调用方 (result_writer.py:367)
    注释写"自管事务", 实际静默 except 丢对账。改: session=None 走自己的 transaction()。
    """
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper

    src = inspect.getsource(InterfaceCaseResultMapper.recompute_case_result_nums)

    # 1. 不应有 raise ValueError("...external session...")
    assert "raise ValueError" not in src, (
        f"[{BUG_DOC}] session=None 不应再 raise ValueError, "
        f"改走 if session is None: async with cls.transaction() as session"
    )

    # 2. 必须有 if session is None 分支调 cls.transaction()
    assert "if session is None" in src, (
        f"[{BUG_DOC}] 必须有 if session is None 分支"
    )
    assert "cls.transaction()" in src, (
        f"[{BUG_DOC}] session=None 走 cls.transaction() 自管事务"
    )


@pytest.mark.asyncio
async def test_bug_doc_recompute_with_external_session_uses_it():
    """[BUG-DOC] session 传进来时复用外部 session (D4 哲学一致)。
    """
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper

    # mock: 直接调 mapper 不走 DB, 验证 session 传进 _do_query
    mock_session = AsyncMock()
    mock_row = MagicMock()
    mock_row.total = 3
    mock_row.success = 2
    mock_row.fail = 1
    mock_result = MagicMock()
    mock_result.one = MagicMock(return_value=mock_row)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch.object(
        InterfaceCaseResultMapper, "update_by_id", new=AsyncMock()
    ) as mock_update:
        result = await InterfaceCaseResultMapper.recompute_case_result_nums(
            case_result_id=42,
            session=mock_session,
        )

    # 外部 session 走通
    assert result == {"total": 3, "success": 2, "fail": 1}
    mock_update.assert_awaited_once()
    # update_by_id 必须用同一 session (D4 风格)
    kwargs = mock_update.await_args.kwargs
    assert kwargs.get("session") is mock_session, (
        f"[{BUG_DOC}] 外部 session 传进来时, update_by_id 必须复用同 session"
    )
