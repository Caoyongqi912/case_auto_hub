"""
step_content_script.py 单测覆盖率补充 (目标 30% → 80%+)。

测 APIScriptContentStrategy.execute 的 5 条主路径:
1. script 为空字符串: extracted_vars=None, 仍写 result
2. script 成功执行: 变量 add_vars, success_num +1, return True
3. ScriptSecurityError 抛出: 兜住, success=False, fail_num +1
4. 普通 Exception 抛出: 兜住, success=False, fail_num +1
5. task_result 透传 + status 写入
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.a_manager import ScriptSecurityError
from croe.interface.executor.step_content.step_content_script import APIScriptContentStrategy
from enums import StepStatusEnum


def _build_ctx(script_text="", task_result=None):
    ctx = MagicMock()
    ctx.index = 1
    ctx.content = MagicMock()
    ctx.content.id = 20
    ctx.content.target_id = 30
    ctx.content.resolved_content_name = "script_step"
    ctx.content.content_desc = "desc"
    ctx.content.script_text = script_text
    ctx.execution_context = MagicMock()
    ctx.execution_context.case_result = MagicMock()
    ctx.execution_context.case_result.id = 100
    ctx.execution_context.case_result.success_num = 0
    ctx.execution_context.case_result.fail_num = 0
    ctx.execution_context.task_result = task_result
    ctx.starter = MagicMock()
    ctx.starter.send = AsyncMock()
    ctx.variable_manager = MagicMock()
    ctx.variable_manager.add_vars = MagicMock()
    ctx.result_writer = MagicMock()
    ctx.result_writer.update_case_progress = AsyncMock()
    return ctx


@pytest.fixture
def strategy():
    return APIScriptContentStrategy(MagicMock())


# --------------------------------------------------------------------------- #
# 1) script 为空
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_script_step_empty_script_text_writes_result(strategy):
    """script_text 为空: extracted_vars=None, 仍写 result, success=True。"""
    ctx = _build_ctx(script_text="")

    with patch(
        "croe.interface.executor.step_content.step_content_script.InterfaceContentStepResultMapper.insert_result",
        new=AsyncMock(),
    ) as mock_insert:
        ret = await strategy.execute(ctx)

    assert ret is True
    mock_insert.assert_called_once()
    call_kwargs = mock_insert.call_args.kwargs
    assert call_kwargs["result"] is True
    assert call_kwargs["status"] == StepStatusEnum.SUCCESS
    assert call_kwargs["script_error"] is None
    assert call_kwargs["script_vars"] == []  # extracted_vars None → 空 list
    # add_vars 不应被调
    ctx.variable_manager.add_vars.assert_not_called()


# --------------------------------------------------------------------------- #
# 2) 成功路径
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_script_step_success_adds_vars(strategy):
    """script 成功: extracted_vars -> add_vars, success_num +1, return True。"""
    ctx = _build_ctx(script_text="x = 1")

    with patch(
        "croe.interface.executor.step_content.step_content_script.ScriptManager"
    ) as MockSM:
        MockSM.return_value.execute = MagicMock(return_value={"k1": "v1", "k2": "v2"})

        with patch(
            "croe.interface.executor.step_content.step_content_script.InterfaceContentStepResultMapper.insert_result",
            new=AsyncMock(),
        ) as mock_insert:
            ret = await strategy.execute(ctx)

    assert ret is True
    assert ctx.execution_context.case_result.success_num == 1
    assert ctx.execution_context.case_result.fail_num == 0
    ctx.variable_manager.add_vars.assert_called_once_with({"k1": "v1", "k2": "v2"})
    call_kwargs = mock_insert.call_args.kwargs
    assert call_kwargs["result"] is True
    assert call_kwargs["status"] == StepStatusEnum.SUCCESS
    # script_vars 转换 [{"key":k, "value":v, "target":11}]
    assert call_kwargs["script_vars"] == [
        {"key": "k1", "value": "v1", "target": 11},
        {"key": "k2", "value": "v2", "target": 11},
    ]


# --------------------------------------------------------------------------- #
# 3) ScriptSecurityError 异常
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_script_step_security_error_caught(strategy):
    """ScriptSecurityError 抛出: 兜住, success=False, fail_num +1。"""
    ctx = _build_ctx(script_text="import os")

    with patch(
        "croe.interface.executor.step_content.step_content_script.ScriptManager"
    ) as MockSM:
        MockSM.return_value.execute = MagicMock(
            side_effect=ScriptSecurityError("禁止 import")
        )

        with patch(
            "croe.interface.executor.step_content.step_content_script.InterfaceContentStepResultMapper.insert_result",
            new=AsyncMock(),
        ) as mock_insert:
            ret = await strategy.execute(ctx)

    assert ret is False
    assert ctx.execution_context.case_result.success_num == 0
    assert ctx.execution_context.case_result.fail_num == 1
    ctx.variable_manager.add_vars.assert_not_called()
    call_kwargs = mock_insert.call_args.kwargs
    assert call_kwargs["result"] is False
    assert call_kwargs["status"] == StepStatusEnum.FAIL
    assert "禁止 import" in call_kwargs["script_error"]
    # starter.send 报告安全错误
    send_msgs = [c.args[0] for c in ctx.starter.send.call_args_list]
    assert any("脚本执行安全错误" in m for m in send_msgs)


# --------------------------------------------------------------------------- #
# 4) 普通 Exception 异常
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_script_step_generic_exception_caught(strategy):
    """普通 Exception 抛出: 兜住, success=False, fail_num +1, script_error=str(e)。"""
    ctx = _build_ctx(script_text="1/0")

    with patch(
        "croe.interface.executor.step_content.step_content_script.ScriptManager"
    ) as MockSM:
        MockSM.return_value.execute = MagicMock(side_effect=ZeroDivisionError("div by zero"))

        with patch(
            "croe.interface.executor.step_content.step_content_script.InterfaceContentStepResultMapper.insert_result",
            new=AsyncMock(),
        ) as mock_insert:
            ret = await strategy.execute(ctx)

    assert ret is False
    assert ctx.execution_context.case_result.fail_num == 1
    call_kwargs = mock_insert.call_args.kwargs
    assert "div by zero" in call_kwargs["script_error"]
    send_msgs = [c.args[0] for c in ctx.starter.send.call_args_list]
    assert any("脚本执行错误" in m for m in send_msgs)


# --------------------------------------------------------------------------- #
# 5) task_result 透传
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_script_step_task_result_id_passed(strategy):
    """task_result 存在: insert_result 收 task_result_id=int。"""
    task_result = MagicMock()
    task_result.id = 555
    ctx = _build_ctx(script_text="", task_result=task_result)

    with patch(
        "croe.interface.executor.step_content.step_content_script.InterfaceContentStepResultMapper.insert_result",
        new=AsyncMock(),
    ) as mock_insert:
        await strategy.execute(ctx)
    call_kwargs = mock_insert.call_args.kwargs
    assert call_kwargs["task_result_id"] == 555
