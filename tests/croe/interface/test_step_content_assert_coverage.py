"""
step_content_assert.py 单测覆盖率补充 (目标 38% → 80%+)。

测 APIAssertsContentStrategy.execute 的 4 条主路径:
1. assert_list 为空: 直接 return True
2. assert_list 有, 全成功: success_num +1, return True
3. assert_list 有, 部分失败: fail_num +1, return True (跟 E10 修复前不同, 这里始终 return True)
4. AssertionError 抛出: 异常被兜住, return False
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.interface.executor.step_content.step_content_assert import APIAssertsContentStrategy
from enums import StepStatusEnum


def _build_ctx(assert_list=None, task_result=None):
    ctx = MagicMock()
    ctx.index = 2
    ctx.content = MagicMock()
    ctx.content.id = 20
    ctx.content.resolved_content_name = "assert_step"
    ctx.content.content_desc = "desc"
    ctx.content.assert_list = assert_list
    ctx.execution_context = MagicMock()
    ctx.execution_context.case_result = MagicMock()
    ctx.execution_context.case_result.id = 100
    ctx.execution_context.case_result.success_num = 0
    ctx.execution_context.case_result.fail_num = 0
    ctx.execution_context.task_result = task_result
    ctx.starter = MagicMock()
    ctx.starter.send = AsyncMock()
    ctx.variable_manager = MagicMock()
    ctx.variable_manager.variables = {"k": "v"}
    ctx.result_writer = MagicMock()
    ctx.result_writer.update_case_progress = AsyncMock()
    return ctx


@pytest.fixture
def strategy():
    return APIAssertsContentStrategy(MagicMock())


# --------------------------------------------------------------------------- #
# 1) assert_list 为空
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_assert_step_empty_assert_list_returns_true(strategy):
    """assert_list 为空: starter.send 警告, return True, 不写 result。"""
    ctx = _build_ctx(assert_list=[])

    ret = await strategy.execute(ctx)
    assert ret is True
    # 警告消息
    ctx.starter.send.assert_called_once()
    msg = ctx.starter.send.call_args.args[0]
    assert "未配置断言" in msg
    # counter 不动
    assert ctx.execution_context.case_result.success_num == 0
    assert ctx.execution_context.case_result.fail_num == 0


# --------------------------------------------------------------------------- #
# 2) 全成功
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_assert_step_all_pass(strategy):
    """assert_list 有, 全成功: success_num +1, return True。"""
    ctx = _build_ctx(assert_list=[{"key": "k", "value": "v", "operator": "eq"}])

    with patch("croe.interface.executor.step_content.step_content_assert.AssertManager") as MockAM:
        mock_mgr = MockAM.return_value
        mock_mgr.assert_content_list = AsyncMock(
            return_value=([{"key": "k", "result": True}], True)
        )
        with patch("croe.interface.executor.step_content.step_content_assert.InterfaceContentStepResultMapper.insert_result",
                   AsyncMock()) as mock_insert:
            ret = await strategy.execute(ctx)

            assert ret is True
            assert ctx.execution_context.case_result.success_num == 1
            assert ctx.execution_context.case_result.fail_num == 0
            mock_insert.assert_called_once()
            call_kwargs = mock_insert.call_args.kwargs
            assert call_kwargs["assert_result"] is True
            assert call_kwargs["status"] == StepStatusEnum.SUCCESS


# --------------------------------------------------------------------------- #
# 3) 部分失败
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_assert_step_partial_fail(strategy):
    """assert_list 有, 部分失败: fail_num +1, 仍 return True (写入 result 后再返)。"""
    ctx = _build_ctx(assert_list=[{"key": "k", "value": "v", "operator": "eq"}])

    with patch("croe.interface.executor.step_content.step_content_assert.AssertManager") as MockAM:
        mock_mgr = MockAM.return_value
        mock_mgr.assert_content_list = AsyncMock(
            return_value=([{"key": "k", "result": False}], False)
        )
        with patch("croe.interface.executor.step_content.step_content_assert.InterfaceContentStepResultMapper.insert_result",
                   AsyncMock()) as mock_insert:
            ret = await strategy.execute(ctx)

            # 注: assert_strategy 写完 result 后仍 return True (不算 step 失败,
            # 失败信息存在 result 里, case_result.fail_num 已 +1)
            assert ret is True
            assert ctx.execution_context.case_result.success_num == 0
            assert ctx.execution_context.case_result.fail_num == 1
            call_kwargs = mock_insert.call_args.kwargs
            assert call_kwargs["assert_result"] is False
            assert call_kwargs["status"] == StepStatusEnum.FAIL


# --------------------------------------------------------------------------- #
# 4) AssertionError 异常被兜住
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_assert_step_assertion_error_caught(strategy):
    """AssertManager.assert_content_list 抛 AssertionError: 异常被兜, return False。"""
    ctx = _build_ctx(assert_list=[{"key": "k", "value": "v"}])

    with patch("croe.interface.executor.step_content.step_content_assert.AssertManager") as MockAM:
        mock_mgr = MockAM.return_value
        mock_mgr.assert_content_list = AsyncMock(side_effect=AssertionError("断言失败"))
        ret = await strategy.execute(ctx)

        assert ret is False
        # starter.send 报告异常
        send_calls = [c.args[0] for c in ctx.starter.send.call_args_list]
        assert any("断言异常" in m for m in send_calls), (
            f"应有断言异常消息, 实际 {send_calls}"
        )


# --------------------------------------------------------------------------- #
# 5) task_result 透传
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_assert_step_task_result_id_passed(strategy):
    """task_result 存在: insert_result 收 task_result_id=int。"""
    task_result = MagicMock()
    task_result.id = 888
    ctx = _build_ctx(assert_list=[{"k": "v"}], task_result=task_result)

    with patch("croe.interface.executor.step_content.step_content_assert.AssertManager") as MockAM:
        mock_mgr = MockAM.return_value
        mock_mgr.assert_content_list = AsyncMock(return_value=([], True))
        with patch("croe.interface.executor.step_content.step_content_assert.InterfaceContentStepResultMapper.insert_result",
                   AsyncMock()) as mock_insert:
            await strategy.execute(ctx)
            call_kwargs = mock_insert.call_args.kwargs
            assert call_kwargs["task_result_id"] == 888
