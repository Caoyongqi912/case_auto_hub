"""
step_content_api.py 单测覆盖率补充 (目标 31% → 80%+)。

测 APIStepContentStrategy.execute 的 4 条主路径:
1. interface 不存在 → return False
2. interface 存在, success=True → success_num +1, return True
3. interface 存在, success=False → fail_num +1, result=ERROR, return False
4. execution_context.task_result 有/无 → task_result_id 正确传
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.interface.executor.step_content.step_content_api import APIStepContentStrategy
from enums import InterfaceAPIResultEnum


def _build_ctx(target_id=10, content_id=20, task_result=None):
    ctx = MagicMock()
    ctx.index = 1
    ctx.content = MagicMock()
    ctx.content.id = content_id
    ctx.content.target_id = target_id
    ctx.content.resolved_content_name = "api_step"
    ctx.content.content_desc = "desc"
    ctx.execution_context = MagicMock()
    ctx.execution_context.case_result = MagicMock()
    ctx.execution_context.case_result.id = 100
    ctx.execution_context.case_result.success_num = 0
    ctx.execution_context.case_result.fail_num = 0
    ctx.execution_context.case_result.result = None
    ctx.execution_context.task_result = task_result
    ctx.starter = MagicMock()
    ctx.starter.send = AsyncMock()
    ctx.result_writer = MagicMock()
    ctx.result_writer.write_interface_result = AsyncMock()
    ctx.result_writer.write_step_result = AsyncMock()
    ctx.result_writer.update_case_progress = AsyncMock()
    return ctx


def _build_step_result_dict(success=True, status=200, error=None):
    """对齐 interface_executor._build_result 的真实字段名。"""
    return {
        "interface_id": 10,
        "interface_name": "test",
        "interface_uid": "u1",
        "interface_desc": "desc",
        "starter_id": 1,
        "starter_name": "admin",
        "request_url": "http://x",
        "request_method": "GET",
        "request_params": None,
        "request_body_type": None,
        "request_json": None,
        "request_data": None,
        "request_headers": None,
        "extracts": [],
        "asserts": [],
        "running_env_id": 1,
        "running_env_name": "test",
        "response_status": status,
        "response_text": "{}",
        "response_headers": {},
        "use_time": "50.0",
        "result": success,
        "start_time": MagicMock(),
    }


def _build_interface_result(ir_id=999, success=True, use_time="50.0"):
    ir = MagicMock()
    ir.id = ir_id
    ir.start_time = MagicMock()
    ir.use_time = use_time
    ir.result = success
    return ir


@pytest.fixture
def strategy():
    return APIStepContentStrategy(MagicMock())


# --------------------------------------------------------------------------- #
# 1) interface 不存在
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_api_step_interface_not_found_returns_false(strategy):
    """interface 找不到: return False, 不调 execute, 不写 result。"""
    ctx = _build_ctx(target_id=999)

    with patch("croe.interface.executor.step_content.step_content_api.InterfaceMapper.get_by_id",
               AsyncMock(return_value=None)):
        ret = await strategy.execute(ctx)
        assert ret is False
        ctx.starter.send.assert_called_once()
        msg = ctx.starter.send.call_args.args[0]
        assert "未找到接口" in msg
        ctx.result_writer.write_interface_result.assert_not_called()
        ctx.result_writer.write_step_result.assert_not_called()
        ctx.result_writer.update_case_progress.assert_not_called()


# --------------------------------------------------------------------------- #
# 2) success 路径
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_api_step_success_path(strategy):
    """interface 存在, success=True: success_num +1, return True, result 不变。"""
    ctx = _build_ctx()
    fake_interface = MagicMock()
    step_result = _build_step_result_dict(success=True, status=200)

    with patch("croe.interface.executor.step_content.step_content_api.InterfaceMapper.get_by_id",
               AsyncMock(return_value=fake_interface)):
        with patch.object(strategy.interface_executor, "execute", AsyncMock(return_value=step_result)):
            ctx.result_writer.write_interface_result = AsyncMock(
                return_value=_build_interface_result(ir_id=123, success=True)
            )
            ret = await strategy.execute(ctx)

            assert ret is True
            assert ctx.execution_context.case_result.success_num == 1
            assert ctx.execution_context.case_result.fail_num == 0
            # result 仍为 None (成功时不设 ERROR)
            assert ctx.execution_context.case_result.result is None
            ctx.result_writer.write_interface_result.assert_called_once()
            kwargs = ctx.result_writer.write_interface_result.call_args.kwargs
            assert kwargs["immediate"] is True
            ctx.result_writer.write_step_result.assert_called_once()
            sr_kwargs = ctx.result_writer.write_step_result.call_args.kwargs
            assert sr_kwargs["success"] is True
            assert sr_kwargs["interface_result_id"] == 123


# --------------------------------------------------------------------------- #
# 3) failure 路径
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_api_step_failure_path(strategy):
    """interface 存在, success=False: fail_num +1, result=ERROR, return False。"""
    ctx = _build_ctx()
    fake_interface = MagicMock()
    step_result = _build_step_result_dict(success=False, status=500)

    with patch("croe.interface.executor.step_content.step_content_api.InterfaceMapper.get_by_id",
               AsyncMock(return_value=fake_interface)):
        with patch.object(strategy.interface_executor, "execute", AsyncMock(return_value=step_result)):
            ctx.result_writer.write_interface_result = AsyncMock(
                return_value=_build_interface_result(ir_id=124, success=False)
            )
            ret = await strategy.execute(ctx)

            assert ret is False
            assert ctx.execution_context.case_result.success_num == 0
            assert ctx.execution_context.case_result.fail_num == 1
            assert ctx.execution_context.case_result.result == InterfaceAPIResultEnum.ERROR


# --------------------------------------------------------------------------- #
# 4) task_result 存在 / 不存在
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_api_step_with_task_result_passes_id(strategy):
    """task_result 存在: write_step_result 收 task_result_id=int。"""
    task_result = MagicMock()
    task_result.id = 555
    ctx = _build_ctx(task_result=task_result)
    fake_interface = MagicMock()
    step_result = _build_step_result_dict(success=True)

    with patch("croe.interface.executor.step_content.step_content_api.InterfaceMapper.get_by_id",
               AsyncMock(return_value=fake_interface)):
        with patch.object(strategy.interface_executor, "execute", AsyncMock(return_value=step_result)):
            ctx.result_writer.write_interface_result = AsyncMock(
                return_value=_build_interface_result()
            )
            await strategy.execute(ctx)
            sr_kwargs = ctx.result_writer.write_step_result.call_args.kwargs
            assert sr_kwargs["task_result_id"] == 555


@pytest.mark.asyncio
@pytest.mark.unit
async def test_api_step_no_task_result_passes_none(strategy):
    """task_result 为 None: write_step_result 收 task_result_id=None。"""
    ctx = _build_ctx(task_result=None)
    fake_interface = MagicMock()
    step_result = _build_step_result_dict(success=True)

    with patch("croe.interface.executor.step_content.step_content_api.InterfaceMapper.get_by_id",
               AsyncMock(return_value=fake_interface)):
        with patch.object(strategy.interface_executor, "execute", AsyncMock(return_value=step_result)):
            ctx.result_writer.write_interface_result = AsyncMock(
                return_value=_build_interface_result()
            )
            await strategy.execute(ctx)
            sr_kwargs = ctx.result_writer.write_step_result.call_args.kwargs
            assert sr_kwargs["task_result_id"] is None
