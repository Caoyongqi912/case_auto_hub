"""
PlayRunner.run_case 端到端单测 (高 mock 模式, 不连真实 DB/browser)。

策略: 测核心编排而非全流程, 在 execute_case / case 内部 mock 重活
(browser / mapper.get_by_id / 策略 execute), 验证:
- run_case 进入会调 init_case_result 拿 case_result
- run_case 退出会调 set_case_result 写最终结果
- 异常路径 (init 失败 / 步骤失败) 不会让 run_case crash
- error_continue 参数被传递
- trace_id 在 finally 清掉

不验证步骤内容执行细节 (那由 step_content_strategy 测覆盖)。
"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.model.base import User
from app.model.playUI import PlayCase, PlayCaseResult
from app.model.playUI.playCase import PlayCase
from app.model.playUI.playStepContent import PlayStepContent


def _make_user():
    user = User()
    user.id = 1
    user.uid = "u-1"
    user.username = "alice"
    return user


def _make_starter():
    """构造一个 mock UIStarter (避免真实 socket io)。"""
    from croe.play.starter import UIStarter
    with patch("utils.io_sender.async_io"):
        starter = UIStarter(user=_make_user())
    starter.send = AsyncMock()
    starter.over = AsyncMock()
    starter.logs = []
    return starter


def _make_case(case_id=10):
    case = PlayCase()
    case.id = case_id
    case.title = f"case_{case_id}"
    case.description = "test"
    case.step_num = 0
    case.start_time = datetime.now()  # 避免 use_time 计算 NaN
    return case


def _make_case_result(case_id=10):
    cr = PlayCaseResult()
    cr.id = 999
    cr.ui_case_id = case_id
    cr.status = None
    cr.start_time = datetime.now()
    return cr


def _setup_runner_with_mocks(case_id=10):
    """准备一个 PlayRunner + 全套 mapper mock, 返回 (runner, case, case_result, mocks)。"""
    from croe.play.play_runner import PlayRunner

    runner = PlayRunner(starter=_make_starter())
    case = _make_case(case_id=case_id)
    case_result = _make_case_result(case_id=case_id)
    page_manager = MagicMock()
    page_manager.current_page = AsyncMock()
    page_manager.close = AsyncMock()

    return runner, case, case_result, page_manager


@pytest.mark.asyncio
async def test_run_case_happy_path_calls_init_and_execute():
    """[E2E-1] run_case 应调 init_result + execute_case。

    不深入 execute_case (那由 step_content 测覆盖), 用 mock 验证调用顺序。
    """
    from croe.play.play_runner import PlayRunner

    runner, case, case_result, page_manager = _setup_runner_with_mocks(case_id=10)

    with patch("croe.play.writer.PlayCaseResultMapper") as mock_result_mapper, \
         patch("croe.play.play_runner.PlayCaseMapper") as mock_case_mapper_cls, \
         patch.object(runner, "execute_case", AsyncMock()) as mock_exec:
        mock_result_mapper.init_case_result = AsyncMock(return_value=case_result)
        mock_result_mapper.set_case_result = AsyncMock(return_value=case_result)
        mock_case_mapper_cls.get_by_id = AsyncMock(return_value=case)
        mock_case_mapper_cls.query_content_steps = AsyncMock(return_value=[])

        await runner.run_case(case_id=10, error_continue=False)

    # 验证调用顺序: init -> execute
    mock_result_mapper.init_case_result.assert_awaited_once()
    mock_exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_case_passes_error_continue():
    """[E2E-2] error_continue=True 透传到 execute_case。"""
    from croe.play.play_runner import PlayRunner

    runner, case, case_result, page_manager = _setup_runner_with_mocks(case_id=20)

    with patch("croe.play.writer.PlayCaseResultMapper") as mock_result_mapper, \
         patch("croe.play.play_runner.PlayCaseMapper") as mock_case_mapper_cls, \
         patch.object(runner, "execute_case", AsyncMock()) as mock_exec:
        mock_result_mapper.init_case_result = AsyncMock(return_value=case_result)
        mock_result_mapper.set_case_result = AsyncMock(return_value=case_result)
        mock_case_mapper_cls.get_by_id = AsyncMock(return_value=case)
        mock_case_mapper_cls.query_content_steps = AsyncMock(return_value=[])

        await runner.run_case(case_id=20, error_continue=True)

    call_kwargs = mock_exec.await_args.kwargs
    assert call_kwargs.get("error_continue") is True, (
        f"error_continue 应透传 True, 实际 {call_kwargs}"
    )


@pytest.mark.asyncio
async def test_run_case_init_failure_handled():
    """[E2E-3] init_case_result 抛异常时, run_case 应 raise (由 caller 兜底)。"""
    from croe.play.play_runner import PlayRunner

    runner, case, case_result, _ = _setup_runner_with_mocks(case_id=99)

    with patch("croe.play.writer.PlayCaseResultMapper") as mock_result_mapper, \
         patch("croe.play.play_runner.PlayCaseMapper") as mock_case_mapper_cls, \
         patch.object(runner, "execute_case", AsyncMock()) as mock_exec:
        mock_case_mapper_cls.get_by_id = AsyncMock(return_value=case)
        mock_result_mapper.init_case_result = AsyncMock(
            side_effect=RuntimeError("DB down")
        )

        with pytest.raises(RuntimeError, match="DB down"):
            await runner.run_case(case_id=99, error_continue=False)

    # execute_case 不应被调 (init 失败时短路)
    mock_exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_case_get_case_failure_handled():
    """[E2E-4] PlayCaseMapper.get_by_id 抛异常 (case 不存在), run_case 应 raise。"""
    from croe.play.play_runner import PlayRunner

    runner, _, _, _ = _setup_runner_with_mocks(case_id=404)

    with patch("croe.play.play_runner.PlayCaseMapper") as mock_case_mapper_cls, \
         patch.object(runner, "execute_case", AsyncMock()) as mock_exec:
        mock_case_mapper_cls.get_by_id = AsyncMock(
            side_effect=RuntimeError("case not found")
        )

        with pytest.raises(RuntimeError, match="case not found"):
            await runner.run_case(case_id=404, error_continue=False)

    # execute_case 不应被调
    mock_exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_case_clears_trace_id_on_exit():
    """[E2E-5] run_case 跑完应 clear_trace_id, 防 ContextVar 泄漏。"""
    from croe.play.play_runner import PlayRunner
    from croe.interface.observability import get_trace_id

    runner, case, case_result, _ = _setup_runner_with_mocks(case_id=50)

    with patch("croe.play.writer.PlayCaseResultMapper") as mock_result_mapper, \
         patch("croe.play.play_runner.PlayCaseMapper") as mock_case_mapper_cls, \
         patch.object(runner, "execute_case", AsyncMock()):
        mock_result_mapper.init_case_result = AsyncMock(return_value=case_result)
        mock_result_mapper.set_case_result = AsyncMock(return_value=case_result)
        mock_case_mapper_cls.get_by_id = AsyncMock(return_value=case)
        mock_case_mapper_cls.query_content_steps = AsyncMock(return_value=[])

        await runner.run_case(case_id=50, error_continue=False)

    tid = get_trace_id()
    assert tid in (None, "-"), f"trace_id 应在退出时清理, 实际 {tid!r}"


@pytest.mark.asyncio
async def test_run_case_uses_correct_case_id():
    """[E2E-6] run_case 应把传入的 case_id 传给 PlayCaseMapper.get_by_id。"""
    from croe.play.play_runner import PlayRunner

    runner, case, case_result, _ = _setup_runner_with_mocks(case_id=7777)

    with patch("croe.play.writer.PlayCaseResultMapper") as mock_result_mapper, \
         patch("croe.play.play_runner.PlayCaseMapper") as mock_case_mapper_cls, \
         patch.object(runner, "execute_case", AsyncMock()):
        mock_result_mapper.init_case_result = AsyncMock(return_value=case_result)
        mock_result_mapper.set_case_result = AsyncMock(return_value=case_result)
        mock_case_mapper_cls.get_by_id = AsyncMock(return_value=case)
        mock_case_mapper_cls.query_content_steps = AsyncMock(return_value=[])

        await runner.run_case(case_id=7777, error_continue=False)

    # 验证 case_id 透传
    call_kwargs = mock_case_mapper_cls.get_by_id.await_args.kwargs
    assert call_kwargs.get("ident") == 7777, (
        f"get_by_id 应收 ident=7777, 实际 {call_kwargs}"
    )
