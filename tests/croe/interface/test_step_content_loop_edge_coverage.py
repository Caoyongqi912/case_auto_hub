"""
step_content_loop.py 边角覆盖率补充 (目标 93% -> 100%)。

针对未测的 9 行 (149-150, 288, 291, 348, 351, 367-373):
1. _execute_api_step write_interface_result 异常兜底 (line 149-150)
2. _execute_loop_items 子步骤失败 + loop_interval sleep (line 288, 291)
3. _execute_loop_condition 子步骤失败 + loop_interval sleep (line 348, 351)
4. _execute_loop_condition 断言失败 continue (line 367-373)
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.interface.executor.step_content.step_content_loop import APILoopContentStrategy
from enums.CaseEnum import LoopTypeEnum
from enums import StepStatusEnum


def _build_ctx(target_id=10, content_id=20):
    ctx = MagicMock()
    ctx.index = 1
    ctx.content = MagicMock()
    ctx.content.id = content_id
    ctx.content.target_id = target_id
    ctx.content.resolved_content_name = "loop_step"
    ctx.content.content_desc = "desc"
    ctx.execution_context = MagicMock()
    ctx.execution_context.case_result = MagicMock()
    ctx.execution_context.case_result.id = 100
    ctx.execution_context.case_result.success_num = 0
    ctx.execution_context.case_result.fail_num = 0
    ctx.execution_context.case_result.result = None
    ctx.execution_context.task_result = None
    ctx.starter = MagicMock()
    ctx.starter.send = AsyncMock()
    ctx.variable_manager = MagicMock()
    ctx.variable_manager.trans = AsyncMock(side_effect=lambda x: x)
    ctx.result_writer = MagicMock()
    ctx.result_writer.write_step_result = AsyncMock()
    ctx.result_writer.write_interface_result = AsyncMock()
    ctx.result_writer.update_step_result = AsyncMock()
    ctx.result_writer.update_case_progress = AsyncMock()
    return ctx


def _build_fake_content_result(cr_id=999):
    cr = MagicMock()
    cr.id = cr_id
    return cr


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


def _build_fake_loop(loop_type=LoopTypeEnum.LoopTimes, loop_times=2, loop_items=None, max_loop=10, interval=0, key="x", value="1", operate=0):
    loop = MagicMock()
    loop.id = 10
    loop.loop_type = loop_type
    loop.loop_times = loop_times
    loop.loop_items = loop_items
    loop.max_loop = max_loop
    loop.loop_interval = interval
    loop.loop_item_key = "item"
    loop.key = key
    loop.value = value
    loop.operate = operate
    return loop


@pytest.fixture
def strategy():
    return APILoopContentStrategy(MagicMock())


# --------------------------------------------------------------------------- #
# 1) _execute_api_step write_interface_result 抛异常 -> log.error 兜底不阻塞
#    (line 149-150)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_api_step_write_interface_result_exception_logged_not_raised(strategy):
    """_execute_api_step 里 result_writer.write_interface_result 抛异常
    时只 log.error, 不阻塞流程, success/fail 计数仍正确。
    """
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(return_value=_build_fake_content_result(cr_id=42))
    # write_interface_result 每次调用都炸
    ctx.result_writer.write_interface_result = AsyncMock(side_effect=RuntimeError("DB down"))

    fake_loop = _build_fake_loop(loop_type=LoopTypeEnum.LoopTimes, loop_times=1, interval=0)
    fake_api_step = MagicMock()
    fake_api_step.interface_name = "i1"

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[fake_api_step]),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.log"
    ) as mock_log:
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=True))):
            ret = await strategy.execute(ctx)

    # 成功执行, 不因 write_interface_result 失败而崩
    assert ret is True
    # log.error 被调过 1 次, 错误消息含 "写入接口结果失败"
    mock_log.error.assert_called_once()
    err_msg = mock_log.error.call_args.args[0]
    assert "写入接口结果失败" in err_msg
    assert "DB down" in err_msg
    # 成功数仍 +1
    assert ctx.execution_context.case_result.success_num == 1


# --------------------------------------------------------------------------- #
# 2) _execute_loop_items: 子步骤失败 + loop_interval sleep
#    (line 288: all_success=False; line 291: asyncio.sleep)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_items_child_failure_and_interval_sleep(strategy):
    """LoopItems: 2 items × 1 api, 第 1 个失败 -> all_success=False;
    loop_interval=1 -> 每轮 asyncio.sleep(1)。
    """
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(return_value=_build_fake_content_result(cr_id=42))
    fake_loop = _build_fake_loop(
        loop_type=LoopTypeEnum.LoopItems,
        loop_items=json.dumps(["a", "b"]),
        interval=1,
    )
    fake_api_step = MagicMock()
    fake_api_step.interface_name = "i1"

    call_count = [0]
    async def fake_execute(interface, env):
        call_count[0] += 1
        return _build_step_result(success=(call_count[0] != 1))  # 第 1 次失败

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[fake_api_step]),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.asyncio.sleep",
        new=AsyncMock(),
    ) as mock_sleep:
        with patch.object(strategy.interface_executor, "execute", side_effect=fake_execute):
            ret = await strategy.execute(ctx)

    # 1 个失败 -> all_success=False -> return False
    assert ret is False
    # 2 个 item 都 sleep 一次 -> sleep 调 2 次
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(1)
    # success_count=1, fail_count=1
    final_update = ctx.result_writer.update_step_result.call_args.kwargs
    assert final_update["success_count"] == 1
    assert final_update["fail_count"] == 1
    assert final_update["result"] is False
    assert final_update["status"] == StepStatusEnum.FAIL


# --------------------------------------------------------------------------- #
# 3) _execute_loop_condition: 子步骤失败 + loop_interval sleep
#    (line 348: all_success=False; line 351: asyncio.sleep)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_condition_child_failure_and_interval_sleep(strategy):
    """LoopCondition: max_loop=2, 1 api, 第 1 轮 api 失败 -> all_success=False;
    loop_interval=1 -> 每轮 asyncio.sleep; 断言始终不通过, 跑完 max_loop 退出。
    """
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(return_value=_build_fake_content_result(cr_id=42))
    fake_loop = _build_fake_loop(
        loop_type=LoopTypeEnum.LoopCondition,
        max_loop=2,
        interval=1,
        key="x", value="1", operate=0,
    )
    fake_api_step = MagicMock()
    fake_api_step.interface_name = "i1"

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[fake_api_step]),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.asyncio.sleep",
        new=AsyncMock(),
    ) as mock_sleep, patch(
        "croe.interface.executor.step_content.step_content_loop.MyAsserts.option",
        side_effect=AssertionError("never match"),
    ):
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=False))):
            ret = await strategy.execute(ctx)

    # api 全失败 -> all_success=False -> return False
    assert ret is False
    # 2 轮 * 1 api = 2 次 write_interface_result
    assert ctx.result_writer.write_interface_result.call_count == 2
    # 每轮 sleep 一次 -> 2 次
    assert mock_sleep.call_count == 2
    # fail_count=2, success_count=0
    final_update = ctx.result_writer.update_step_result.call_args.kwargs
    assert final_update["fail_count"] == 2
    assert final_update["success_count"] == 0
    assert final_update["result"] is False


# --------------------------------------------------------------------------- #
# 4) _execute_loop_condition: 断言失败 -> starter.send + continue
#    (line 367-373)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_condition_assertion_failure_continues_loop(strategy):
    """LoopCondition: max_loop=3, 第 1 次断言失败 -> starter.send 报 "断言失败"
    + continue; 第 2 次断言通过 -> break。
    """
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(return_value=_build_fake_content_result(cr_id=42))
    fake_loop = _build_fake_loop(
        loop_type=LoopTypeEnum.LoopCondition,
        max_loop=3,
        interval=0,
        key="x", value="1", operate=0,
    )
    fake_api_step = MagicMock()
    fake_api_step.interface_name = "i1"

    call_count = [0]
    def fake_assert(assertOpt, expect, actual, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise AssertionError("first round fail")
        # 第 2 次不抛 -> break

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[fake_api_step]),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.MyAsserts.option",
        side_effect=fake_assert,
    ):
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=True))):
            ret = await strategy.execute(ctx)

    # 第 2 轮断言通过 -> break -> return True
    assert ret is True
    # 跑了 2 轮 (第 1 轮失败 continue, 第 2 轮 break)
    assert ctx.result_writer.write_interface_result.call_count == 2
    # 第 1 轮失败时 starter.send 包含 "断言失败" 消息
    send_msgs = [c.args[0] for c in ctx.starter.send.call_args_list]
    assert any("断言失败" in m for m in send_msgs), f"未找到 '断言失败' 消息: {send_msgs}"
    # success_num +1
    assert ctx.execution_context.case_result.success_num == 1
