"""
step_content_wait.py 单测覆盖率补充 (目标 44% → 80%+)。

测 APIWaitContentStrategy.execute 的 5 条主路径:
1. wait_time 正常正数: sleep + success_num +1 + return True
2. wait_time 为 None: 视作 0, 不 sleep, 仍 success
3. wait_time 负数: 视作 0, 不 sleep, 仍 success
4. task_result 透传
5. status=StepStatusEnum.SUCCESS 写入
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.interface.executor.step_content.step_content_wait import APIWaitContentStrategy
from enums import StepStatusEnum


def _build_ctx(wait_time=1, task_result=None):
    ctx = MagicMock()
    ctx.index = 3
    ctx.content = MagicMock()
    ctx.content.id = 30
    ctx.content.resolved_content_name = "wait_step"
    ctx.content.content_desc = "desc"
    ctx.content.wait_time = wait_time
    ctx.execution_context = MagicMock()
    ctx.execution_context.case_result = MagicMock()
    ctx.execution_context.case_result.id = 100
    ctx.execution_context.case_result.success_num = 0
    ctx.execution_context.case_result.fail_num = 0
    ctx.execution_context.task_result = task_result
    ctx.starter = MagicMock()
    ctx.starter.send = AsyncMock()
    ctx.result_writer = MagicMock()
    ctx.result_writer.update_case_progress = AsyncMock()
    return ctx


@pytest.fixture
def strategy():
    return APIWaitContentStrategy(MagicMock())


# --------------------------------------------------------------------------- #
# 1) wait_time 正常正数
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_wait_step_normal_wait_time(strategy):
    """wait_time=1: sleep(1), success_num +1, return True。"""
    ctx = _build_ctx(wait_time=1)

    with patch("croe.interface.executor.step_content.step_content_wait.asyncio.sleep",
               new=AsyncMock()) as mock_sleep, \
         patch("croe.interface.executor.step_content.step_content_wait.InterfaceContentStepResultMapper.insert_result",
               AsyncMock()) as mock_insert:
        ret = await strategy.execute(ctx)

        assert ret is True
        mock_sleep.assert_awaited_once_with(1)
        assert ctx.execution_context.case_result.success_num == 1
        mock_insert.assert_called_once()
        call_kwargs = mock_insert.call_args.kwargs
        assert call_kwargs["wait_seconds"] == 1
        assert call_kwargs["status"] == StepStatusEnum.SUCCESS
        # starter.send 报告等待时长
        send_msgs = [c.args[0] for c in ctx.starter.send.call_args_list]
        assert any("等待 1 秒" in m for m in send_msgs)


# --------------------------------------------------------------------------- #
# 2) wait_time 为 None → 视作 0
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_wait_step_none_wait_time(strategy):
    """wait_time=None: sleep(0), 仍成功。"""
    ctx = _build_ctx(wait_time=None)

    with patch("croe.interface.executor.step_content.step_content_wait.asyncio.sleep",
               new=AsyncMock()) as mock_sleep, \
         patch("croe.interface.executor.step_content.step_content_wait.InterfaceContentStepResultMapper.insert_result",
               AsyncMock()) as mock_insert:
        ret = await strategy.execute(ctx)

        assert ret is True
        mock_sleep.assert_awaited_once_with(0)
        call_kwargs = mock_insert.call_args.kwargs
        assert call_kwargs["wait_seconds"] == 0


# --------------------------------------------------------------------------- #
# 3) wait_time 负数 → 视作 0
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_wait_step_negative_wait_time_clamped_to_zero(strategy):
    """wait_time=-5: 视作 0, sleep(0), 仍成功。"""
    ctx = _build_ctx(wait_time=-5)

    with patch("croe.interface.executor.step_content.step_content_wait.asyncio.sleep",
               new=AsyncMock()) as mock_sleep, \
         patch("croe.interface.executor.step_content.step_content_wait.InterfaceContentStepResultMapper.insert_result",
               AsyncMock()) as mock_insert:
        ret = await strategy.execute(ctx)

        assert ret is True
        mock_sleep.assert_awaited_once_with(0)
        call_kwargs = mock_insert.call_args.kwargs
        assert call_kwargs["wait_seconds"] == 0


# --------------------------------------------------------------------------- #
# 4) task_result 透传
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_wait_step_task_result_id_passed(strategy):
    """task_result 存在: insert_result 收 task_result_id=int。"""
    task_result = MagicMock()
    task_result.id = 777
    ctx = _build_ctx(wait_time=1, task_result=task_result)

    with patch("croe.interface.executor.step_content.step_content_wait.asyncio.sleep",
               new=AsyncMock()), \
         patch("croe.interface.executor.step_content.step_content_wait.InterfaceContentStepResultMapper.insert_result",
               AsyncMock()) as mock_insert:
        await strategy.execute(ctx)
        call_kwargs = mock_insert.call_args.kwargs
        assert call_kwargs["task_result_id"] == 777


# --------------------------------------------------------------------------- #
# 5) wait_seconds=0 边界
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_wait_step_zero_wait_seconds(strategy):
    """wait_time=0: sleep(0), wait_seconds=0 写入。"""
    ctx = _build_ctx(wait_time=0)

    with patch("croe.interface.executor.step_content.step_content_wait.asyncio.sleep",
               new=AsyncMock()) as mock_sleep, \
         patch("croe.interface.executor.step_content.step_content_wait.InterfaceContentStepResultMapper.insert_result",
               AsyncMock()) as mock_insert:
        ret = await strategy.execute(ctx)

        assert ret is True
        mock_sleep.assert_awaited_once_with(0)
        assert mock_insert.call_args.kwargs["wait_seconds"] == 0
        assert ctx.execution_context.case_result.success_num == 1
