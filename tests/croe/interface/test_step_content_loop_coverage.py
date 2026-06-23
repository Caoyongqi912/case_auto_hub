"""
step_content_loop.py 单测覆盖率补充 (目标 18% → 80%+)。

测 APILoopContentStrategy 的 5 条主路径:
1. loop 不存在: return False
2. loop_steps 为空: 写完 result 即返 True
3. LoopTimes 全成功 / 失败
4. LoopItems JSON 解析 + 全成功
5. LoopCondition 断言通过 break / 断言失败 continue
6. 未知 loop_type: log.warning + return False
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.interface.executor.step_content.step_content_loop import APILoopContentStrategy
from enums.CaseEnum import LoopTypeEnum
from enums import InterfaceAPIResultEnum, StepStatusEnum


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
    ctx.variable_manager.trans = MagicMock(side_effect=lambda x: x)  # identity
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
    ir = MagicMock()
    ir.result = success
    ir.response_status = status
    return ir


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
# 1) loop 不存在
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_step_loop_not_found_returns_false(strategy):
    """loop 不存在: starter.send 警告, log.warning, return False。"""
    ctx = _build_ctx()

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=None),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.log"
    ) as mock_log:
        ret = await strategy.execute(ctx)

    assert ret is False
    msg = ctx.starter.send.call_args.args[0]
    assert "未找到循环配置" in msg
    mock_log.warning.assert_called_once()
    warn_msg = mock_log.warning.call_args.args[0]
    assert "未找到循环配置" in warn_msg


# --------------------------------------------------------------------------- #
# 2) loop_steps 为空
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_step_empty_loop_steps_returns_true_after_creating_result(strategy):
    """loop_steps 为空: 写完 content_result 立即 return True。"""
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )
    fake_loop = _build_fake_loop(loop_type=LoopTypeEnum.LoopTimes)

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[]),
    ):
        ret = await strategy.execute(ctx)

    assert ret is True
    ctx.result_writer.write_step_result.assert_called_once()
    # 不调 update_step_result (loop_steps 为空, 直接 return, 没进 _update_loop_result)
    ctx.result_writer.update_step_result.assert_not_called()


# --------------------------------------------------------------------------- #
# 3) LoopTimes 全成功
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_step_loop_times_all_success(strategy):
    """LoopTimes=2, 1 个 api_step, 全成功: success_num +1, return True。"""
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )
    fake_loop = _build_fake_loop(loop_type=LoopTypeEnum.LoopTimes, loop_times=2, interval=0)
    fake_api_step = MagicMock()
    fake_api_step.interface_name = "i1"

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[fake_api_step]),
    ):
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=True))):
            ret = await strategy.execute(ctx)

    assert ret is True
    # 2 次循环 × 1 个 api = 2 次 write_interface_result
    assert ctx.result_writer.write_interface_result.call_count == 2
    assert ctx.execution_context.case_result.success_num == 1
    assert ctx.execution_context.case_result.fail_num == 0
    final_update = ctx.result_writer.update_step_result.call_args.kwargs
    assert final_update["result"] is True
    assert final_update["status"] == StepStatusEnum.SUCCESS
    assert final_update["loop_count"] == 2
    assert final_update["success_count"] == 2
    assert final_update["fail_count"] == 0


# --------------------------------------------------------------------------- #
# 4) LoopTimes 有失败
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_step_loop_times_with_failure(strategy):
    """LoopTimes=2, 第 2 次失败: fail_num +1, return False, result=ERROR。"""
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )
    fake_loop = _build_fake_loop(loop_type=LoopTypeEnum.LoopTimes, loop_times=2, interval=0)
    fake_api_step = MagicMock()
    fake_api_step.interface_name = "i1"

    call_count = [0]
    async def fake_execute(interface, env, temp_var=None):
        call_count[0] += 1
        return _build_step_result(success=(call_count[0] == 1))  # 第 1 次成功, 第 2 次失败

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[fake_api_step]),
    ):
        with patch.object(strategy.interface_executor, "execute", side_effect=fake_execute):
            ret = await strategy.execute(ctx)

    assert ret is False
    assert ctx.execution_context.case_result.fail_num == 1
    assert ctx.execution_context.case_result.result == InterfaceAPIResultEnum.ERROR
    final_update = ctx.result_writer.update_step_result.call_args.kwargs
    assert final_update["result"] is False
    assert final_update["status"] == StepStatusEnum.FAIL
    assert final_update["success_count"] == 1
    assert final_update["fail_count"] == 1


# --------------------------------------------------------------------------- #
# 5) LoopItems JSON 解析
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_step_loop_items_json_all_success(strategy):
    """LoopItems='["a","b","c"]' JSON 解析, 1 api_step × 3 items: 全成功。"""
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )
    fake_loop = _build_fake_loop(
        loop_type=LoopTypeEnum.LoopItems,
        loop_items=json.dumps(["a", "b", "c"]),
        interval=0,
    )
    fake_api_step = MagicMock()
    fake_api_step.interface_name = "i1"

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[fake_api_step]),
    ):
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=True))):
            ret = await strategy.execute(ctx)

    assert ret is True
    # 3 items × 1 api = 3 次
    assert ctx.result_writer.write_interface_result.call_count == 3
    final_update = ctx.result_writer.update_step_result.call_args.kwargs
    assert final_update["loop_count"] == 3
    assert final_update["success_count"] == 3
    # loop_items 应传入
    assert final_update["loop_items"] == ["a", "b", "c"]


# --------------------------------------------------------------------------- #
# 6) LoopItems CSV fallback (非 JSON)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_step_loop_items_csv_fallback(strategy):
    """LoopItems='a,b,c' 不是 JSON, fallback split(','): 3 items。"""
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )
    fake_loop = _build_fake_loop(
        loop_type=LoopTypeEnum.LoopItems,
        loop_items="a,b,c",
        interval=0,
    )
    fake_api_step = MagicMock()
    fake_api_step.interface_name = "i1"

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[fake_api_step]),
    ):
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=True))):
            ret = await strategy.execute(ctx)

    assert ret is True
    final_update = ctx.result_writer.update_step_result.call_args.kwargs
    assert final_update["loop_count"] == 3


# --------------------------------------------------------------------------- #
# 7) LoopItems 空 items
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_step_loop_items_empty_returns_true(strategy):
    """LoopItems='[]' 空 items: success_num +1, return True。"""
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )
    fake_loop = _build_fake_loop(
        loop_type=LoopTypeEnum.LoopItems,
        loop_items="[]",
        interval=0,
    )

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[MagicMock(interface_name="i1")]),
    ):
        ret = await strategy.execute(ctx)

    assert ret is True
    final_update = ctx.result_writer.update_step_result.call_args.kwargs
    assert final_update["loop_count"] == 0


# --------------------------------------------------------------------------- #
# 8) LoopCondition 断言通过 break
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_step_loop_condition_assertion_pass_breaks(strategy):
    """LoopCondition 断言通过: break, success_num +1。"""
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )
    fake_loop = _build_fake_loop(
        loop_type=LoopTypeEnum.LoopCondition,
        max_loop=5,
        interval=0,
        key="x", value="1", operate=0,  # assume operate=0 是 eq
    )
    fake_api_step = MagicMock()
    fake_api_step.interface_name = "i1"

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[fake_api_step]),
    ):
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=True))), \
             patch("croe.interface.executor.step_content.step_content_loop.MyAsserts.option") as mock_assert:
            ret = await strategy.execute(ctx)

    # mock_assert 不抛 → 断言通过 → break
    assert ret is True
    assert ctx.execution_context.case_result.success_num == 1
    # max_loop=5, 但只跑了 1 次就 break
    assert ctx.result_writer.write_interface_result.call_count == 1


# --------------------------------------------------------------------------- #
# 9) 未知 loop_type
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_step_unknown_loop_type_returns_false(strategy):
    """未知 loop_type: log.warning + return False。"""
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )
    fake_loop = _build_fake_loop(loop_type=999)  # 不在 LoopTypeEnum 里

    with patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.get_by_id",
        new=AsyncMock(return_value=fake_loop),
    ), patch(
        "croe.interface.executor.step_content.step_content_loop.InterfaceLoopMapper.query_interfaces_by_loop_id",
        new=AsyncMock(return_value=[MagicMock(interface_name="i1")]),
    ):
        ret = await strategy.execute(ctx)

    assert ret is False


# --------------------------------------------------------------------------- #
# 10) loop_interval > 0 触发 asyncio.sleep
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_loop_step_loop_interval_triggers_sleep(strategy):
    """loop_interval=1: 每轮后 asyncio.sleep(1)。"""
    ctx = _build_ctx()
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )
    fake_loop = _build_fake_loop(
        loop_type=LoopTypeEnum.LoopTimes, loop_times=2, interval=1,
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
    ) as mock_sleep:
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=True))):
            ret = await strategy.execute(ctx)

    assert ret is True
    # 2 次循环都 sleep, 至少 2 次
    assert mock_sleep.call_count >= 2
