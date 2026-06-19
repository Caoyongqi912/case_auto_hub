"""
[BUG-P-R1 + P-R2 + P-R3 + P-R4 + P-R5] 5 个 P0 隐藏 BUG 一锅端,
来自 PLAY_REVIEW_2026_06_21。

BUG-P-R1: play_runner.py:execute_case 之前 except 块 raise 抛回去,
        任务级 retry 看不到 case_success=False, 整个 task 直接挂。
        修: except 块只设 case_success=False, 不 raise; finally 仍写结果。

BUG-P-R2: task_runner.py:execute_task 之前 query_case 调了 2 次 (第一次
        结果被覆盖)。修: 删第一次 query。

BUG-P-R3: task_runner.py:__execute_case 之前 init_case_variables 在 retry
        loop 内, 每次 retry 都从 DB 拉同样的 case vars (多 1 次 DB/retry)。
        修: 提到 retry loop 外。

BUG-P-R4: task_runner.py:__execute_case 之前 error_continue 写死 False。
        修: 加 error_continue 到 PlayTaskExecuteParams, 透传给 execute_case。

BUG-P-R5: _base.py:write_result 之前 `if not result.success and not ignore`
        过滤掉 ignore=True 时的失败信息。修: 失败就写错误信息到 case_result。
"""
import inspect
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.play.executor.step_content_strategy._base import StepBaseStrategy
from tests.croe.play._bug_ids import (
    BUG_P_R1, BUG_P_R2, BUG_P_R3, BUG_P_R4, BUG_P_R5,
)


# --------------------------------------------------------------------------- #
# BUG-P-R1: execute_case except 不 raise
# --------------------------------------------------------------------------- #

def test_bug_p_r1_execute_case_except_does_not_raise():
    """[BUG-P-R1] execute_case 的 except 块不应 raise, 任务级 retry 才能拿到
    case_success=False 走重试路径。
    """
    from croe.play.play_runner import PlayRunner

    src = inspect.getsource(PlayRunner.execute_case)

    # 找 except 块 (剥注释)
    except_m = re.search(
        r"except Exception[^:]*:\s*\n(.*?)(?=\n        finally|\n    async def|\Z)",
        src, re.DOTALL
    )
    assert except_m, f"[{BUG_P_R1}] 找不到 except 块"
    except_block = "\n".join(
        ln for ln in except_m.group(1).splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )

    # except 块不应有 raise
    assert "raise" not in except_block, (
        f"[{BUG_P_R1}] except 块不应 raise, 任务级 retry 看不到 case_success。\n"
        f"当前 except 块:\n{except_block}"
    )
    # 应该有 case_success = False
    assert "case_success = False" in except_block, (
        f"[{BUG_P_R1}] except 块应设 case_success = False"
    )


# --------------------------------------------------------------------------- #
# BUG-P-R2: execute_task 单一 query_case
# --------------------------------------------------------------------------- #

def test_bug_p_r2_execute_task_no_duplicate_query_case():
    """[BUG-P-R2] execute_task 函数体 query_case 只应调 1 次 (修前 2 次)。"""
    from croe.play.task_runner import PlayTaskRunner

    src = inspect.getsource(PlayTaskRunner.execute_task)

    # 数 PlayTaskMapper.query_case( 调用次数
    count = len(re.findall(r"PlayTaskMapper\.query_case\s*\(", src))
    assert count == 1, (
        f"[{BUG_P_R2}] execute_task 应只调 1 次 query_case, "
        f"实际 {count} 次。修前调 2 次 (L36-37 + L46-48), "
        f"第一次结果被覆盖, 多 1 次 DB + 数据竞争风险"
    )


# --------------------------------------------------------------------------- #
# BUG-P-R3: init_case_variables 提到 retry loop 外
# --------------------------------------------------------------------------- #

def test_bug_p_r3_init_case_vars_outside_retry_loop():
    """[BUG-P-R3] __execute_case 中 init_case_variables 必须在 retry loop 外,
    每次 retry 不再从 DB 拉 case vars。
    """
    from croe.play.task_runner import PlayTaskRunner

    src = inspect.getsource(PlayTaskRunner._PlayTaskRunner__execute_case)

    # 找 init_case_variables 调用
    init_pos = src.find("init_case_variables")
    # 找 retry loop (for r in range)
    retry_pos = src.find("for r in range(params.retry")
    # 找 case 的 for loop (for play_case in)
    case_pos = src.find("for play_case in play_cases")

    assert init_pos > 0, f"[{BUG_P_R3}] 找不到 init_case_variables 调用"
    assert retry_pos > 0, f"[{BUG_P_R3}] 找不到 retry for 循环"
    assert case_pos > 0, f"[{BUG_P_R3}] 找不到 case for 循环"

    # init_case_variables 必须在 retry loop 之前, 但在 case loop 内
    assert case_pos < init_pos < retry_pos, (
        f"[{BUG_P_R3}] init_case_variables 应在 case loop 内, "
        f"retry loop 外 (避免每次 retry 都拉 DB)。\n"
        f"  case_pos={case_pos}, init_pos={init_pos}, retry_pos={retry_pos}"
    )


# --------------------------------------------------------------------------- #
# BUG-P-R4: error_continue 透传
# --------------------------------------------------------------------------- #

def test_bug_p_r4_task_params_has_error_continue():
    """[BUG-P-R4] PlayTaskExecuteParams 必须有 error_continue 字段。"""
    from croe.play.task_runner import PlayTaskExecuteParams
    import dataclasses

    fields = {f.name for f in dataclasses.fields(PlayTaskExecuteParams)}
    assert "error_continue" in fields, (
        f"[{BUG_P_R4}] PlayTaskExecuteParams 应有 error_continue 字段, "
        f"实际: {fields}"
    )


def test_bug_p_r4_execute_case_called_with_error_continue_param():
    """[BUG-P-R4] __execute_case 调 execute_case 时必须传 error_continue 参数,
    不能写死 False。
    """
    from croe.play.task_runner import PlayTaskRunner

    src = inspect.getsource(PlayTaskRunner._PlayTaskRunner__execute_case)

    # 找 execute_case 调用, 验 error_continue=... (不是写死字面值)
    call_m = re.search(
        r"play_runner\.execute_case\s*\((.*?)\)",
        src, re.DOTALL
    )
    assert call_m, f"[{BUG_P_R4}] 找不到 execute_case 调用"
    call_args = call_m.group(1)

    # 必须有 error_continue=... (不能是 error_continue=False 字面值, 因为
    # 即便字面值跟修前一样, 也至少说明参数透传了, 跟 params 解耦)
    assert "error_continue" in call_args, (
        f"[{BUG_P_R4}] execute_case 调用应传 error_continue 参数, "
        f"不能写死 False。当前调用:\n{call_args}"
    )
    # 应该传 params.error_continue (从 PlayTaskExecuteParams 拿)
    assert "params.error_continue" in call_args, (
        f"[{BUG_P_R4}] error_continue 应从 params 透传 (params.error_continue), "
        f"不能写死 False"
    )


# --------------------------------------------------------------------------- #
# BUG-P-R5: ignore 步骤也写失败信息
# --------------------------------------------------------------------------- #

def test_bug_p_r5_ignored_step_writes_error_info():
    """[BUG-P-R5] write_result 失败时应写 set_error_step_info, 不管 ignore 标志。

    修前: `if not result.success and not ignore` — ignore=True 失败信息丢失。
    修后: `if not result.success` — 失败就写, ignore 步骤也能查失败信息。
    """
    from croe.play.executor.step_content_strategy._base import StepBaseStrategy

    src = inspect.getsource(StepBaseStrategy.write_result)

    # 剥注释后, 找 `if not result.success` 行 (避免误命中修复注释里
    # 引用 "and not ignore" 描述"修了什么")
    code_lines = [
        ln for ln in src.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    code_only = "\n".join(code_lines)

    # 找 `if not result.success` (在代码行, 不在注释)
    if_m = re.search(r"if\s+not\s+result\.success[^:]*:", code_only)
    assert if_m, f"[{BUG_P_R5}] 找不到 'if not result.success' 行"

    cond = if_m.group(0)
    assert "and not ignore" not in cond, (
        f"[{BUG_P_R5}] 'if not result.success' 不应再带 'and not ignore' "
        f"(ignore 时失败信息会丢失), 应该失败就写 set_error_step_info"
    )

    # 后面应调 set_error_step_info
    after_if_pos = if_m.end()
    after_block = code_only[after_if_pos:after_if_pos + 200]
    assert "set_error_step_info" in after_block, (
        f"[{BUG_P_R5}] 'if not result.success' 之后应调 set_error_step_info, "
        f"写错误信息到 case_result"
    )


class _TestStrategy(StepBaseStrategy):
    """P-R5 端到端用, 具体子类让 abstract 能实例化。"""
    async def execute(self, step_context):
        return True


@pytest.mark.asyncio
async def test_bug_p_r5_ignored_step_writes_error_info_end_to_end():
    """[BUG-P-R5] 端到端: 步骤失败 + ignore=True 时, set_error_step_info 仍被调。"""
    from croe.play.executor.step_content_strategy._base import StepBaseStrategy
    from croe.play.executor.play_method.result_types import StepExecutionResult

    strategy = _TestStrategy()
    strategy.to_screenshot = AsyncMock(return_value=None)  # 避免真截图

    # mock context
    mock_step_content = MagicMock()
    mock_step_content.id = 1
    mock_step_content.content_name = "test_step"
    mock_step_content.content_desc = "test"
    mock_step_content.content_type = "STEP_PLAY"

    ctx = MagicMock()
    ctx.index = 1
    ctx.play_step_content = mock_step_content
    ctx.starter = MagicMock()
    ctx.starter.userId = 1
    ctx.starter.username = "test"
    ctx.play_step_result_writer = MagicMock()
    ctx.play_step_result_writer.add_content_result = AsyncMock()
    ctx.play_case_result_writer = MagicMock()
    ctx.play_case_result_writer.set_error_step_info = AsyncMock()

    result = StepExecutionResult(
        success=False,  # 失败
        message="element not found",
    )

    import datetime
    await strategy.write_result(
        result=result,
        start_time=datetime.datetime.now(),
        step_context=ctx,
        ignore=True,  # 但被 ignore
    )

    # P-R5 修复: 即便 ignore=True, set_error_step_info 仍被调
    ctx.play_case_result_writer.set_error_step_info.assert_awaited()
