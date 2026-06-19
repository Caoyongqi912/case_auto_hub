"""
step_content_group.py 单测覆盖率补充 (目标 27% → 80%+)。

测 APIGroupContentStrategy.execute 的 4 条主路径:
1. interface_list 为空: return True
2. 全部 success: success_num +1, return True, update_step_result 收到 SUCCESS
3. 第一个就 fail: 跳出 loop, fail_num +1, result=ERROR, return False
4. task_result 透传
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.interface.executor.step_content.step_content_group import APIGroupContentStrategy
from enums import InterfaceAPIResultEnum, StepStatusEnum


def _build_ctx(target_id=10, content_id=20, task_result=None):
    ctx = MagicMock()
    ctx.index = 1
    ctx.content = MagicMock()
    ctx.content.id = content_id
    ctx.content.target_id = target_id
    ctx.content.resolved_content_name = "group_step"
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
    ctx.result_writer.write_step_result = AsyncMock()
    ctx.result_writer.write_interface_result = AsyncMock()
    ctx.result_writer.update_step_result = AsyncMock()
    ctx.result_writer.update_case_progress = AsyncMock()
    return ctx


def _build_step_result(success=True, status=200):
    return {
        "result": success,
        "interface_id": 1, "interface_uid": "u", "interface_name": "n",
        "interface_desc": "d", "starter_id": 1, "starter_name": "u",
        "request_url": "http://x", "request_method": "GET",
        "request_params": None, "request_body_type": None,
        "request_json": None, "request_data": None, "request_headers": None,
        "extracts": [], "asserts": [],
        "running_env_id": 1, "running_env_name": "test",
        "response_status": status, "response_text": "{}",
        "response_headers": {}, "use_time": "1.0",
        "start_time": MagicMock(),
    }


def _build_fake_content_result(cr_id=999):
    cr = MagicMock()
    cr.id = cr_id
    return cr


@pytest.fixture
def strategy():
    return APIGroupContentStrategy(MagicMock())


# --------------------------------------------------------------------------- #
# 1) interface_list 为空
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_group_step_empty_interface_list_returns_true(strategy):
    """interface_list 为空: return True, 不调任何 write。"""
    ctx = _build_ctx()

    with patch(
        "croe.interface.executor.step_content.step_content_group.InterfaceGroupMapper.query_association_interfaces",
        new=AsyncMock(return_value=[]),
    ):
        ret = await strategy.execute(ctx)

    assert ret is True
    ctx.result_writer.write_step_result.assert_not_called()
    ctx.result_writer.write_interface_result.assert_not_called()
    ctx.result_writer.update_step_result.assert_not_called()
    ctx.result_writer.update_case_progress.assert_not_called()


# --------------------------------------------------------------------------- #
# 2) 全部 success
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_group_step_all_success(strategy):
    """3 个 interface 全成功: success_num +1, return True, status=SUCCESS。"""
    ctx = _build_ctx()
    interfaces = [MagicMock(), MagicMock(), MagicMock()]
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )

    with patch(
        "croe.interface.executor.step_content.step_content_group.InterfaceGroupMapper.query_association_interfaces",
        new=AsyncMock(return_value=interfaces),
    ):
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=True, status=200))):
            ret = await strategy.execute(ctx)

    assert ret is True
    assert ctx.execution_context.case_result.success_num == 1
    assert ctx.execution_context.case_result.fail_num == 0
    # write_step_result 调 1 次 (父 content_result)
    ctx.result_writer.write_step_result.assert_called_once()
    # write_interface_result 调 N 次 (每个子 interface)
    assert ctx.result_writer.write_interface_result.call_count == 3
    # update_step_result 收 status=SUCCESS, success_api_num=3, fail_api_num=0
    update_kwargs = ctx.result_writer.update_step_result.call_args.kwargs
    assert update_kwargs["result"] is True
    assert update_kwargs["status"] == StepStatusEnum.SUCCESS
    assert update_kwargs["success_api_num"] == 3
    assert update_kwargs["fail_api_num"] == 0
    assert update_kwargs["total_api_num"] == 3


# --------------------------------------------------------------------------- #
# 3) 第一个就 fail
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_group_step_first_interface_fails_break(strategy):
    """第 1 个 interface fail: 跳出 loop, fail_num +1, result=ERROR, return False。"""
    ctx = _build_ctx()
    interfaces = [MagicMock(), MagicMock(), MagicMock()]
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )

    with patch(
        "croe.interface.executor.step_content.step_content_group.InterfaceGroupMapper.query_association_interfaces",
        new=AsyncMock(return_value=interfaces),
    ):
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=False, status=500))):
            ret = await strategy.execute(ctx)

    assert ret is False
    assert ctx.execution_context.case_result.success_num == 0
    assert ctx.execution_context.case_result.fail_num == 1
    assert ctx.execution_context.case_result.result == InterfaceAPIResultEnum.ERROR
    # write_interface_result 只调 1 次 (第 1 个失败就 break)
    assert ctx.result_writer.write_interface_result.call_count == 1
    update_kwargs = ctx.result_writer.update_step_result.call_args.kwargs
    assert update_kwargs["result"] is False
    assert update_kwargs["status"] == StepStatusEnum.FAIL
    assert update_kwargs["success_api_num"] == 0
    assert update_kwargs["fail_api_num"] == 1


# --------------------------------------------------------------------------- #
# 4) 第二个 fail (前 1 个成功)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_group_step_second_interface_fails_break(strategy):
    """第 2 个 interface fail: 第 1 个算 success_api_num, 第 2 个后 break。"""
    ctx = _build_ctx()
    interfaces = [MagicMock(), MagicMock(), MagicMock()]
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )

    call_count = [0]
    async def fake_execute(interface, env):
        call_count[0] += 1
        # 第 1 次 success, 第 2 次 fail, 第 3 次不调 (因为 break)
        return _build_step_result(success=(call_count[0] == 1), status=200 if call_count[0] == 1 else 500)

    with patch(
        "croe.interface.executor.step_content.step_content_group.InterfaceGroupMapper.query_association_interfaces",
        new=AsyncMock(return_value=interfaces),
    ):
        with patch.object(strategy.interface_executor, "execute", side_effect=fake_execute):
            ret = await strategy.execute(ctx)

    assert ret is False
    assert ctx.execution_context.case_result.fail_num == 1
    update_kwargs = ctx.result_writer.update_step_result.call_args.kwargs
    assert update_kwargs["success_api_num"] == 1
    assert update_kwargs["fail_api_num"] == 1
    # write_interface_result 只调 2 次 (第 2 个失败 break)
    assert ctx.result_writer.write_interface_result.call_count == 2


# --------------------------------------------------------------------------- #
# 5) task_result 透传
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_group_step_task_result_id_passed(strategy):
    """task_result 存在: write_step_result 收 task_result_id=int。"""
    task_result = MagicMock()
    task_result.id = 666
    ctx = _build_ctx(task_result=task_result)
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result()
    )

    with patch(
        "croe.interface.executor.step_content.step_content_group.InterfaceGroupMapper.query_association_interfaces",
        new=AsyncMock(return_value=[MagicMock()]),
    ):
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=True))):
            await strategy.execute(ctx)
    call_kwargs = ctx.result_writer.write_step_result.call_args.kwargs
    assert call_kwargs["task_result_id"] == 666
