"""task_runner.py 单元测试覆盖"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.play.task_runner import PlayTaskRunner, PlayTaskExecuteParams

# --------------------------------------------------------------------------- #
# PlayTaskExecuteParams
# --------------------------------------------------------------------------- #

class TestPlayTaskExecuteParams:
    """PlayTaskExecuteParams dataclass 默认值测试。"""

    def test_required_task_id(self):
        """task_id 是必填。"""
        p = PlayTaskExecuteParams(task_id=1)
        assert p.task_id == 1

    def test_optional_defaults(self):
        """可选字段默认值: retry=0, retry_interval=0, notify_id=None, variables=None,
        error_continue=False。"""
        p = PlayTaskExecuteParams(task_id=1)
        assert p.retry == 0
        assert p.retry_interval == 0
        assert p.notify_id is None
        assert p.variables is None
        assert p.error_continue is False

    def test_task_id_accepts_int_or_str(self):
        """task_id 应支持 int 和 str (按 uid 查)。"""
        p_int = PlayTaskExecuteParams(task_id=42)
        p_str = PlayTaskExecuteParams(task_id="abc123")
        assert p_int.task_id == 42
        assert p_str.task_id == "abc123"

    def test_error_continue_can_be_set(self):
        """error_continue 应可设 True (P-R4 修复, 之前写死 False)。"""
        p = PlayTaskExecuteParams(task_id=1, error_continue=True)
        assert p.error_continue is True

# --------------------------------------------------------------------------- #
# PlayTaskRunner.execute_task
# --------------------------------------------------------------------------- #

class TestExecuteTask:
    """execute_task 任务级执行测试。"""

    @pytest.mark.asyncio
    async def test_int_task_id_uses_get_by_id(self):
        """task_id 是 int 时应调 get_by_id。"""
        starter = MagicMock()
        starter.send = AsyncMock()
        runner = PlayTaskRunner(starter=starter)
        mock_task = MagicMock(id=1, title="T1", desc="d1")
        with patch.object(PlayTaskRunner, "_PlayTaskRunner__execute_case", new=AsyncMock()) as mock_exec, \
             patch("croe.play.task_runner.PlayTaskMapper") as mock_mapper, \
             patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
            mock_mapper.get_by_id = AsyncMock(return_value=mock_task)
            mock_mapper.query_case = AsyncMock(return_value=[MagicMock()])  # 1 case
            mock_writer = MagicMock()
            mock_writer.init_result = AsyncMock(return_value=MagicMock(id=10))
            mock_writer.write_final_result = AsyncMock()
            mock_writer_cls.return_value = mock_writer
            await runner.execute_task(PlayTaskExecuteParams(task_id=1))
            mock_mapper.get_by_id.assert_called_once_with(ident=1)
            mock_mapper.query_case.assert_called_once_with(taskId=1)

    @pytest.mark.asyncio
    async def test_str_task_id_uses_get_by_uid(self):
        """task_id 是 str 时应调 get_by_uid。"""
        starter = MagicMock()
        starter.send = AsyncMock()
        runner = PlayTaskRunner(starter=starter)
        mock_task = MagicMock(id=1, title="T1", desc="d1")
        with patch.object(PlayTaskRunner, "_PlayTaskRunner__execute_case", new=AsyncMock()), \
             patch("croe.play.task_runner.PlayTaskMapper") as mock_mapper, \
             patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
            mock_mapper.get_by_uid = AsyncMock(return_value=mock_task)
            mock_mapper.query_case = AsyncMock(return_value=[])
            mock_writer = MagicMock()
            mock_writer.init_result = AsyncMock(return_value=MagicMock(id=10))
            mock_writer.write_final_result = AsyncMock()
            mock_writer_cls.return_value = mock_writer
            await runner.execute_task(PlayTaskExecuteParams(task_id="abc"))
            mock_mapper.get_by_uid.assert_called_once_with(uid="abc")
            mock_mapper.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_cases_returns_early_with_warning(self, caplog=None):
        """query_case 返空时 execute_task 应 return, 不 init_result。"""
        starter = MagicMock()
        starter.send = AsyncMock()
        runner = PlayTaskRunner(starter=starter)
        mock_task = MagicMock(id=1, title="空任务", desc="d1")
        with patch("croe.play.task_runner.PlayTaskMapper") as mock_mapper, \
             patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
            mock_mapper.get_by_id = AsyncMock(return_value=mock_task)
            mock_mapper.query_case = AsyncMock(return_value=[])
            mock_writer = MagicMock()
            mock_writer.init_result = AsyncMock()
            mock_writer.write_final_result = AsyncMock()
            mock_writer_cls.return_value = mock_writer
            await runner.execute_task(PlayTaskExecuteParams(task_id=1))
            # init_result 不应被调
            mock_writer.init_result.assert_not_called()
            mock_writer.write_final_result.assert_not_called()

    @pytest.mark.asyncio
    async def test_init_result_failure_does_not_crash(self):
        """init_result 抛异常时 execute_task 应 log + return, 不挂。"""
        starter = MagicMock()
        starter.send = AsyncMock()
        runner = PlayTaskRunner(starter=starter)
        mock_task = MagicMock(id=1, title="T", desc="d")
        with patch("croe.play.task_runner.PlayTaskMapper") as mock_mapper, \
             patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
            mock_mapper.get_by_id = AsyncMock(return_value=mock_task)
            mock_mapper.query_case = AsyncMock(return_value=[MagicMock()])
            mock_writer = MagicMock()
            mock_writer.init_result = AsyncMock(side_effect=RuntimeError("DB 挂了"))
            mock_writer.write_final_result = AsyncMock()
            mock_writer_cls.return_value = mock_writer
            # 不应抛
            await runner.execute_task(PlayTaskExecuteParams(task_id=1))
            # send 应被调告知用户失败
            assert any("初始化失败" in str(call) for call in starter.send.call_args_list)

    @pytest.mark.asyncio
    async def test_execute_case_exception_still_writes_final(self):
        """__execute_case 抛异常时 (不管什么原因), 仍应调 write_final_result。"""
        starter = MagicMock()
        starter.send = AsyncMock()
        runner = PlayTaskRunner(starter=starter)
        mock_task = MagicMock(id=1, title="T", desc="d")
        with patch.object(PlayTaskRunner, "_PlayTaskRunner__execute_case",
                          new=AsyncMock(side_effect=RuntimeError("case 跑炸"))), \
             patch("croe.play.task_runner.PlayTaskMapper") as mock_mapper, \
             patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
            mock_mapper.get_by_id = AsyncMock(return_value=mock_task)
            mock_mapper.query_case = AsyncMock(return_value=[MagicMock()])
            mock_writer = MagicMock()
            mock_writer.init_result = AsyncMock(return_value=MagicMock(id=10))
            mock_writer.write_final_result = AsyncMock()
            mock_writer_cls.return_value = mock_writer
            await runner.execute_task(PlayTaskExecuteParams(task_id=1))
            # write_final_result 仍应被调 (finally 块)
            mock_writer.write_final_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_id_calls_notify(self):
        """params.notify_id 有值时应调 __notify_report。"""
        starter = MagicMock()
        starter.send = AsyncMock()
        runner = PlayTaskRunner(starter=starter)
        mock_task = MagicMock(id=1, title="T", desc="d")
        with patch.object(PlayTaskRunner, "_PlayTaskRunner__execute_case", new=AsyncMock()), \
             patch.object(PlayTaskRunner, "_PlayTaskRunner__notify_report", new=AsyncMock()) as mock_notify, \
             patch("croe.play.task_runner.PlayTaskMapper") as mock_mapper, \
             patch("croe.play.task_runner.PlayTaskResultWriter") as mock_writer_cls:
            mock_mapper.get_by_id = AsyncMock(return_value=mock_task)
            mock_mapper.query_case = AsyncMock(return_value=[MagicMock()])
            mock_writer = MagicMock()
            mock_writer.init_result = AsyncMock(return_value=MagicMock(id=10))
            mock_writer.write_final_result = AsyncMock()
            mock_writer_cls.return_value = mock_writer
            await runner.execute_task(PlayTaskExecuteParams(task_id=1, notify_id=99))
            mock_notify.assert_called_once()
            args = mock_notify.call_args.args
            assert args[0] == 99

# --------------------------------------------------------------------------- #
# PlayTaskRunner.__notify_report
# --------------------------------------------------------------------------- #

class TestNotifyReport:
    """__notify_report 静态方法测试。"""

    @pytest.mark.asyncio
    async def test_creates_notify_manager_and_push(self):
        """应创建 NotifyManager(notify_id) 并 push。"""
        from croe.play.task_runner import PlayTaskRunner
        task_result = MagicMock()
        with patch("croe.play.task_runner.NotifyManager") as mock_nm_cls:
            mock_nm = MagicMock()
            mock_nm.push = AsyncMock()
            mock_nm_cls.return_value = mock_nm
            await PlayTaskRunner._PlayTaskRunner__notify_report(42, task_result)
            mock_nm_cls.assert_called_once_with(42)
            mock_nm.push.assert_called_once()
            # push 应有 flag="UI" + task_result
            kwargs = mock_nm.push.call_args.kwargs
            assert kwargs.get("flag") == "UI"
            assert kwargs.get("task_result") is task_result
