"""BUG-F4 回归测试:`init_interface_case_vars` 不应静默吞错。"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from croe.interface.runner import InterfaceRunner
from tests.croe.interface._bug_ids import BUG_F4

@pytest.fixture
def bug_f4_marker():
    return BUG_F4

def _make_starter():
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.username = "u"
    starter.userId = 1
    starter.uid = "u-1"
    starter.logs = []
    starter.over = AsyncMock()
    return starter

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f4_mapper_error_does_not_silently_sink(bug_f4_marker):
    """[BUG-F4] mapper 抛错时,失败要可见(starter.send + log.exception),不抛。"""
    runner = InterfaceRunner(starter=_make_starter())

    with patch(
        "app.mapper.interfaceApi.interfaceVarsMapper.InterfaceVarsMapper.query_by",
        new=AsyncMock(side_effect=RuntimeError("DB connection lost")),
    ), patch("utils.log.exception") as mock_exc:
        # 不应抛 — 后续步骤仍要能跑
        await runner.init_interface_case_vars(interface_case_id=1)

    # 1. 应当走 log.exception(带 traceback),而不是 log.error
    assert mock_exc.called, (
        f"[{BUG_F4}] 失败时应当用 log.exception 记录 traceback,"
        f"而不是裸 log.error"
    )

    # 2. 应当把失败信息发到 starter.send,让用户在前端看到
    send_msgs = [str(c.args[0]) for c in runner.starter.send.call_args_list if c.args]
    assert any("失败" in m or "失败" in m or "变量" in m for m in send_msgs), (
        f"[{BUG_F4}] 失败时应当 starter.send 通知用户,"
        f"实际 send 调用: {send_msgs}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f4_mapper_error_does_not_crash_subsequent_steps(bug_f4_marker):
    """[BUG-F4] 失败时不应抛,这样调用方能继续(后续步骤仍跑)。"""
    runner = InterfaceRunner(starter=_make_starter())

    with patch(
        "app.mapper.interfaceApi.interfaceVarsMapper.InterfaceVarsMapper.query_by",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ), patch("utils.log.exception"):
        # 不应抛
        try:
            await runner.init_interface_case_vars(interface_case_id=1)
        except Exception as e:
            pytest.fail(
                f"[{BUG_F4}] init_interface_case_vars 不应向外抛错,"
                f"这样后续步骤无法继续。实际抛: {type(e).__name__}: {e}"
            )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f4_happy_path_still_works(bug_f4_marker):
    """[BUG-F4] 正常路径不应被破坏。"""
    runner = InterfaceRunner(starter=_make_starter())

    fake_var = MagicMock()
    fake_var.key = "x"
    fake_var.value = "1"

    with patch(
        "app.mapper.interfaceApi.interfaceVarsMapper.InterfaceVarsMapper.query_by",
        new=AsyncMock(return_value=[fake_var]),
    ):
        await runner.init_interface_case_vars(interface_case_id=1)

    # 变量应当被加到 manager
    assert runner.variable_manager.vars._vars.get("x") == "1", (
        f"[{BUG_F4}] 正常路径变量没被加进 manager,"
        f"实际 _vars: {runner.variable_manager.vars._vars}"
    )
    # 应当 send 一个成功的消息
    send_msgs = [str(c.args[0]) for c in runner.starter.send.call_args_list if c.args]
    assert any("初始化业务用例变量" in m for m in send_msgs), (
        f"[{BUG_F4}] 正常路径应 send '初始化业务用例变量',"
        f"实际: {send_msgs}"
    )
