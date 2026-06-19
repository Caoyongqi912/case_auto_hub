"""
step_content_condition.py 单测覆盖率补充 (目标 19% → 80%+)。

测 APIConditionContentStrategy.execute 的 5 条主路径:
1. condition 不存在: return False
2. condition 通过, 无子 API: success_num +1, return True
3. condition 通过, 子 API 全成功: success_num +1, return True
4. condition 通过, 子 API 第 N 个失败: fail_num +1, return False
5. condition 不通过: 跳过子步骤, success_num +1, return True
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.interface.executor.step_content.step_content_condition import APIConditionContentStrategy
from enums import InterfaceAPIResultEnum, StepStatusEnum


def _build_ctx(target_id=10, content_id=20, task_result=None):
    ctx = MagicMock()
    ctx.index = 1
    ctx.content = MagicMock()
    ctx.content.id = content_id
    ctx.content.target_id = target_id
    ctx.content.resolved_content_name = "cond_step"
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
    ctx.variable_manager = MagicMock()
    ctx.result_writer = MagicMock()
    ctx.result_writer.write_step_result = AsyncMock()
    ctx.result_writer.write_interface_result = AsyncMock()
    ctx.result_writer.update_step_result = AsyncMock()
    ctx.result_writer.update_case_progress = AsyncMock()
    return ctx


def _build_fake_condition(cond_id=10):
    cond = MagicMock()
    cond.id = cond_id
    return cond


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


@pytest.fixture
def strategy():
    return APIConditionContentStrategy(MagicMock())


# --------------------------------------------------------------------------- #
# 1) condition 不存在
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_condition_step_condition_not_found_returns_false(strategy):
    """condition 不存在: starter.send 警告, return False。"""
    ctx = _build_ctx()

    with patch(
        "croe.interface.executor.step_content.step_content_condition.InterfaceConditionMapper.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        ret = await strategy.execute(ctx)

    assert ret is False
    msg = ctx.starter.send.call_args.args[0]
    assert "未找到条件配置" in msg
    ctx.result_writer.write_step_result.assert_not_called()


# --------------------------------------------------------------------------- #
# 2) condition 通过, 无子 API
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_condition_step_pass_no_child_apis(strategy):
    """condition 通过, 无子 API: success_num +1, return True, update_step_result SUCCESS。"""
    ctx = _build_ctx()
    fake_cond = _build_fake_condition(cond_id=10)
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )

    with patch(
        "croe.interface.executor.step_content.step_content_condition.InterfaceConditionMapper.get_by_id",
        new=AsyncMock(return_value=fake_cond),
    ), patch(
        "croe.interface.executor.step_content.step_content_condition.ConditionManager"
    ) as MockCM, patch(
        "croe.interface.executor.step_content.step_content_condition.InterfaceConditionMapper.query_interfaces_by_condition_id",
        new=AsyncMock(return_value=[]),
    ):
        MockCM.return_value.invoke = AsyncMock(
            return_value=(True, {"key": "k", "value": "v", "operator": "eq"})
        )
        ret = await strategy.execute(ctx)

    assert ret is True
    assert ctx.execution_context.case_result.success_num == 1
    assert ctx.execution_context.case_result.fail_num == 0
    # write_step_result 调 1 次
    ctx.result_writer.write_step_result.assert_called_once()
    # update_step_result 收 result=True, status=SUCCESS
    update_kwargs = ctx.result_writer.update_step_result.call_args.kwargs
    assert update_kwargs["result"] is True
    assert update_kwargs["status"] == StepStatusEnum.SUCCESS


# --------------------------------------------------------------------------- #
# 3) condition 通过, 子 API 全成功
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_condition_step_pass_all_child_apis_succeed(strategy):
    """condition 通过, 2 个子 API 全成功: success_num +1, return True。"""
    ctx = _build_ctx()
    fake_cond = _build_fake_condition(cond_id=10)
    fake_interfaces = [MagicMock(interface_name="i1"), MagicMock(interface_name="i2")]
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )

    with patch(
        "croe.interface.executor.step_content.step_content_condition.InterfaceConditionMapper.get_by_id",
        new=AsyncMock(return_value=fake_cond),
    ), patch(
        "croe.interface.executor.step_content.step_content_condition.ConditionManager"
    ) as MockCM, patch(
        "croe.interface.executor.step_content.step_content_condition.InterfaceConditionMapper.query_interfaces_by_condition_id",
        new=AsyncMock(return_value=fake_interfaces),
    ):
        MockCM.return_value.invoke = AsyncMock(
            return_value=(True, {"key": "k", "value": "v", "operator": "eq"})
        )
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=True))):
            ret = await strategy.execute(ctx)

    assert ret is True
    assert ctx.execution_context.case_result.success_num == 1
    assert ctx.result_writer.write_interface_result.call_count == 2
    # 最终 update_step_result 收 result=True, status=SUCCESS
    final_update = ctx.result_writer.update_step_result.call_args.kwargs
    assert final_update["result"] is True
    assert final_update["status"] == StepStatusEnum.SUCCESS


# --------------------------------------------------------------------------- #
# 4) condition 通过, 子 API 失败
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_condition_step_pass_child_api_fails(strategy):
    """condition 通过, 第 1 个子 API 失败: fail_num +1, result=ERROR, return False。"""
    ctx = _build_ctx()
    fake_cond = _build_fake_condition(cond_id=10)
    fake_interfaces = [MagicMock(interface_name="i1"), MagicMock(interface_name="i2")]
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )

    with patch(
        "croe.interface.executor.step_content.step_content_condition.InterfaceConditionMapper.get_by_id",
        new=AsyncMock(return_value=fake_cond),
    ), patch(
        "croe.interface.executor.step_content.step_content_condition.ConditionManager"
    ) as MockCM, patch(
        "croe.interface.executor.step_content.step_content_condition.InterfaceConditionMapper.query_interfaces_by_condition_id",
        new=AsyncMock(return_value=fake_interfaces),
    ):
        MockCM.return_value.invoke = AsyncMock(
            return_value=(True, {"key": "k", "value": "v", "operator": "eq"})
        )
        with patch.object(strategy.interface_executor, "execute",
                          new=AsyncMock(return_value=_build_step_result(success=False, status=500))):
            ret = await strategy.execute(ctx)

    assert ret is False
    assert ctx.execution_context.case_result.success_num == 0
    assert ctx.execution_context.case_result.fail_num == 1
    assert ctx.execution_context.case_result.result == InterfaceAPIResultEnum.ERROR
    # write_interface_result 只调 1 次 (第 1 个失败就 break)
    assert ctx.result_writer.write_interface_result.call_count == 1
    final_update = ctx.result_writer.update_step_result.call_args.kwargs
    assert final_update["result"] is False
    assert final_update["status"] == StepStatusEnum.FAIL


# --------------------------------------------------------------------------- #
# 5) condition 不通过
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_condition_step_failed_skips_children(strategy):
    """condition 不通过: 跳过子步骤, success_num +1, return True。"""
    ctx = _build_ctx()
    fake_cond = _build_fake_condition(cond_id=10)
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result(cr_id=42)
    )

    with patch(
        "croe.interface.executor.step_content.step_content_condition.InterfaceConditionMapper.get_by_id",
        new=AsyncMock(return_value=fake_cond),
    ), patch(
        "croe.interface.executor.step_content.step_content_condition.ConditionManager"
    ) as MockCM:
        MockCM.return_value.invoke = AsyncMock(
            return_value=(False, {"key": "k", "value": "v", "operator": "eq"})
        )
        ret = await strategy.execute(ctx)

    assert ret is True
    # 注: condition step 自身算成功, 跳过子步骤 (跟 case_result.success_num +1)
    assert ctx.execution_context.case_result.success_num == 1
    assert ctx.execution_context.case_result.fail_num == 0
    # 不调 interface_executor.execute
    strategy.interface_executor.execute.assert_not_called()
    # write_interface_result 不调
    ctx.result_writer.write_interface_result.assert_not_called()
    # update_step_result 收 result=True, status=SUCCESS (跳过的 condition 算成功)
    final_update = ctx.result_writer.update_step_result.call_args.kwargs
    assert final_update["result"] is True
    assert final_update["status"] == StepStatusEnum.SUCCESS
    # starter.send 报告"未通过"
    send_msgs = [c.args[0] for c in ctx.starter.send.call_args_list]
    assert any("未通过" in m for m in send_msgs)


# --------------------------------------------------------------------------- #
# 6) task_result 透传
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_condition_step_task_result_id_passed(strategy):
    """task_result 存在: write_step_result 收 task_result_id=int。"""
    task_result = MagicMock()
    task_result.id = 999
    ctx = _build_ctx(task_result=task_result)
    fake_cond = _build_fake_condition(cond_id=10)
    ctx.result_writer.write_step_result = AsyncMock(
        return_value=_build_fake_content_result()
    )

    with patch(
        "croe.interface.executor.step_content.step_content_condition.InterfaceConditionMapper.get_by_id",
        new=AsyncMock(return_value=fake_cond),
    ), patch(
        "croe.interface.executor.step_content.step_content_condition.ConditionManager"
    ) as MockCM, patch(
        "croe.interface.executor.step_content.step_content_condition.InterfaceConditionMapper.query_interfaces_by_condition_id",
        new=AsyncMock(return_value=[]),
    ):
        MockCM.return_value.invoke = AsyncMock(
            return_value=(True, {"key": "k", "value": "v", "operator": "eq"})
        )
        await strategy.execute(ctx)
    call_kwargs = ctx.result_writer.write_step_result.call_args.kwargs
    assert call_kwargs["task_result_id"] == 999
    # assert_data 写入 (BUG-E11)
    assert call_kwargs["assert_data"] == {"key": "k", "value": "v", "operator": "eq"}
