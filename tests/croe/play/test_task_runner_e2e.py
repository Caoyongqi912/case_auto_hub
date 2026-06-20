"""
PlayTaskRunner.execute_task 端到端单测 (高 mock 模式)。

策略: mock PlayTaskMapper / PlayCaseMapper / PlayTaskResultWriter,
验证 execute_task 的核心编排:
- 拿 task + 拿 case list
- init_result 失败时不能挂整 task (P-3-1 修复锁)
- __execute_case 异常时仍调 write_final_result + notify
- retry 透传

不验证 case 内部执行 (那由 PlayRunner / step_content 测覆盖)。
"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.model.base import User
from app.model.playUI import PlayCase, PlayCaseResult, PlayTask, PlayTaskResult
from croe.play.task_runner import PlayTaskExecuteParams, PlayTaskRunner


def _make_user():
    user = User()
    user.id = 1
    user.uid = "u-1"
    user.username = "alice"
    return user


def _make_starter():
    from croe.play.starter import UIStarter
    with patch("utils.io_sender.async_io"):
        starter = UIStarter(user=_make_user())
    starter.send = AsyncMock()
    starter.over = AsyncMock()
    starter.logs = []
    return starter


def _make_task(task_id=1):
    """构造 PlayTask mock (避开 desc property 无 setter)。"""
    task = MagicMock(spec=PlayTask)
    task.id = task_id
    task.title = f"task_{task_id}"
    task.desc = "test task"
    return task


def _make_task_result(task_id=1):
    tr = PlayTaskResult()
    tr.id = 100
    tr.task_id = task_id
    tr.status = None
    tr.success_number = 0
    tr.fail_number = 0
    return tr


@pytest.mark.asyncio
async def test_execute_task_happy_path_runs_all_cases():
    """[E2E-T1] 跑 1 task + 3 cases 全 SUCCESS。"""
    runner = PlayTaskRunner(starter=_make_starter())
    task = _make_task(task_id=1)
    task_result = _make_task_result(task_id=1)
    cases = [PlayCase() for _ in range(3)]
    for i, c in enumerate(cases, 1):
        c.id = i
        c.title = f"case_{i}"
        c.step_num = 0

    params = PlayTaskExecuteParams(task_id=1, retry=0)

    with patch("croe.play.task_runner.PlayTaskMapper") as mock_task_mapper, \
         patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
        mock_task_mapper.get_by_id = AsyncMock(return_value=task)
        mock_task_mapper.query_case = AsyncMock(return_value=cases)
        mock_writer = MagicMock()
        mock_writer.init_result = AsyncMock(return_value=task_result)
        mock_writer.write_final_result = AsyncMock()
        mock_writer_cls.return_value = mock_writer

        # mock 内部 __execute_case 让它直接成功
        with patch.object(runner, "_PlayTaskRunner__execute_case", AsyncMock()) as mock_exec:
            await runner.execute_task(params)

    # init_result 必被调
    mock_writer.init_result.assert_awaited_once()
    # write_final_result 在 finally 被调
    mock_writer.write_final_result.assert_awaited_once()
    # 内部 case 执行被调
    mock_exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_task_init_result_failure_returns_cleanly():
    """[E2E-T2] P-3-1 锁: init_result 抛异常时, task 不挂 (return, 不 raise)。"""
    runner = PlayTaskRunner(starter=_make_starter())
    task = _make_task(task_id=2)
    cases = [PlayCase()]
    cases[0].id = 1
    cases[0].title = "case_1"
    cases[0].step_num = 0

    params = PlayTaskExecuteParams(task_id=2, retry=0)

    with patch("croe.play.task_runner.PlayTaskMapper") as mock_task_mapper, \
         patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
        mock_task_mapper.get_by_id = AsyncMock(return_value=task)
        mock_task_mapper.query_case = AsyncMock(return_value=cases)
        mock_writer = MagicMock()
        mock_writer.init_result = AsyncMock(side_effect=RuntimeError("DB down"))
        mock_writer_cls.return_value = mock_writer

        # 不应抛
        await runner.execute_task(params)

    # write_final_result 不应被调 (init 失败时短路)
    mock_writer.write_final_result.assert_not_called()


@pytest.mark.asyncio
async def test_execute_task_no_cases_returns_early():
    """[E2E-T3] task 没 case 时, 直接 return, 不调 init_result。"""
    runner = PlayTaskRunner(starter=_make_starter())
    task = _make_task(task_id=3)
    params = PlayTaskExecuteParams(task_id=3, retry=0)

    with patch("croe.play.task_runner.PlayTaskMapper") as mock_task_mapper, \
         patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
        mock_task_mapper.get_by_id = AsyncMock(return_value=task)
        mock_task_mapper.query_case = AsyncMock(return_value=[])  # 空

        # 不应抛
        await runner.execute_task(params)

    # init_result 不应被调
    mock_writer_cls.assert_not_called()


@pytest.mark.asyncio
async def test_execute_task_execute_case_failure_still_writes_final_result():
    """[E2E-T4] __execute_case 抛异常时, finally 仍调 write_final_result。"""
    runner = PlayTaskRunner(starter=_make_starter())
    task = _make_task(task_id=4)
    task_result = _make_task_result(task_id=4)
    cases = [PlayCase()]
    cases[0].id = 1
    cases[0].title = "case_1"
    cases[0].step_num = 0

    params = PlayTaskExecuteParams(task_id=4, retry=0)

    with patch("croe.play.task_runner.PlayTaskMapper") as mock_task_mapper, \
         patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
        mock_task_mapper.get_by_id = AsyncMock(return_value=task)
        mock_task_mapper.query_case = AsyncMock(return_value=cases)
        mock_writer = MagicMock()
        mock_writer.init_result = AsyncMock(return_value=task_result)
        mock_writer.write_final_result = AsyncMock()
        mock_writer_cls.return_value = mock_writer

        # 内部 __execute_case 抛
        with patch.object(
            runner, "_PlayTaskRunner__execute_case",
            AsyncMock(side_effect=RuntimeError("case crashed")),
        ):
            # 不应抛 (execute_task 内部 try/except + finally)
            await runner.execute_task(params)

    # write_final_result 在 finally 仍被调
    mock_writer.write_final_result.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_task_supports_uid_based_task_id():
    """[E2E-T5] task_id 是字符串 (uid) 时, 应调 get_by_uid 而非 get_by_id。"""
    runner = PlayTaskRunner(starter=_make_starter())
    task = _make_task(task_id=5)
    task.uid = "task-uid-abc"
    task_result = _make_task_result(task_id=5)

    params = PlayTaskExecuteParams(task_id="task-uid-abc", retry=0)

    with patch("croe.play.task_runner.PlayTaskMapper") as mock_task_mapper, \
         patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
        mock_task_mapper.get_by_id = AsyncMock()
        mock_task_mapper.get_by_uid = AsyncMock(return_value=task)
        mock_task_mapper.query_case = AsyncMock(return_value=[])
        mock_writer = MagicMock()
        mock_writer.init_result = AsyncMock(return_value=task_result)
        mock_writer.write_final_result = AsyncMock()
        mock_writer_cls.return_value = mock_writer

        await runner.execute_task(params)

    # 用 uid 调 get_by_uid
    mock_task_mapper.get_by_uid.assert_awaited_once()
    mock_task_mapper.get_by_uid.assert_awaited_with(uid="task-uid-abc")
    # 不应调 get_by_id
    mock_task_mapper.get_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_execute_task_passes_retry_to_internal_execute():
    """[E2E-T6] params.retry 透传到内部 __execute_case。"""
    runner = PlayTaskRunner(starter=_make_starter())
    task = _make_task(task_id=6)
    task_result = _make_task_result(task_id=6)
    cases = [PlayCase()]
    cases[0].id = 1
    cases[0].title = "case_1"
    cases[0].step_num = 0

    params = PlayTaskExecuteParams(task_id=6, retry=3, retry_interval=5)

    with patch("croe.play.task_runner.PlayTaskMapper") as mock_task_mapper, \
         patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
        mock_task_mapper.get_by_id = AsyncMock(return_value=task)
        mock_task_mapper.query_case = AsyncMock(return_value=cases)
        mock_writer = MagicMock()
        mock_writer.init_result = AsyncMock(return_value=task_result)
        mock_writer.write_final_result = AsyncMock()
        mock_writer_cls.return_value = mock_writer

        with patch.object(
            runner, "_PlayTaskRunner__execute_case", AsyncMock()
        ) as mock_exec:
            await runner.execute_task(params)

    # retry 应透传
    call_kwargs = mock_exec.await_args.kwargs
    assert call_kwargs.get("params") is params, "params 应原样透传"
    assert call_kwargs["params"].retry == 3, f"retry 应为 3, 实际 {call_kwargs['params'].retry}"


@pytest.mark.asyncio
async def test_execute_task_with_notify_id_calls_notify():
    """[E2E-T7] params.notify_id 有值时, finally 应调 __notify_report。"""
    runner = PlayTaskRunner(starter=_make_starter())
    task = _make_task(task_id=7)
    task_result = _make_task_result(task_id=7)
    cases = [PlayCase()]
    cases[0].id = 1
    cases[0].title = "case_1"
    cases[0].step_num = 0

    params = PlayTaskExecuteParams(task_id=7, retry=0, notify_id=42)

    with patch("croe.play.task_runner.PlayTaskMapper") as mock_task_mapper, \
         patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
        mock_task_mapper.get_by_id = AsyncMock(return_value=task)
        mock_task_mapper.query_case = AsyncMock(return_value=cases)
        mock_writer = MagicMock()
        mock_writer.init_result = AsyncMock(return_value=task_result)
        mock_writer.write_final_result = AsyncMock()
        mock_writer_cls.return_value = mock_writer

        with patch.object(
            runner, "_PlayTaskRunner__execute_case", AsyncMock()
        ), patch.object(
            runner, "_PlayTaskRunner__notify_report", AsyncMock()
        ) as mock_notify:
            await runner.execute_task(params)

    mock_notify.assert_awaited_once_with(42, task_result)
