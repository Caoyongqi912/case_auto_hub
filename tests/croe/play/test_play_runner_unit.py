"""play_runner.py 单元测试覆盖"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.play.play_runner import PlayRunner

# --------------------------------------------------------------------------- #
# PlayRunner 基础
# --------------------------------------------------------------------------- #

class TestPlayRunnerInit:
    """PlayRunner __init__ 测试。"""

    def test_init_creates_variable_manager_and_browser_none(self):
        """init 应创建 VariableManager, browser 初始 None。"""
        starter = MagicMock()
        r = PlayRunner(starter=starter)
        assert r.starter is starter
        assert r.variable_manager is not None
        assert r.browser is None

# --------------------------------------------------------------------------- #
# PlayRunner._init_page
# --------------------------------------------------------------------------- #

class TestInitPage:
    """_init_page 测试。"""

    @pytest.mark.asyncio
    async def test_init_page_sets_browser(self):
        """_init_page 应通过 BrowserManagerFactory 拿 browser, set self.browser。"""
        starter = MagicMock()
        r = PlayRunner(starter=starter)
        mock_browser = MagicMock()
        mock_browser.get_browser = AsyncMock(return_value=MagicMock())
        mock_page = MagicMock()
        with patch("croe.play.play_runner.BrowserManagerFactory") as mock_factory, \
             patch("croe.play.play_runner.PageManager") as mock_pm_cls:
            mock_factory.get_instance = AsyncMock(return_value=mock_browser)
            mock_ctx = MagicMock()
            mock_ctx.new_page = AsyncMock(return_value=mock_page)
            mock_browser.get_browser = AsyncMock(return_value=mock_ctx)
            mock_pm = MagicMock()
            mock_pm_cls.return_value = mock_pm
            result = await r._init_page()
            # self.browser 应被设
            assert r.browser is mock_browser
            # PageManager.set_page 应被调
            mock_pm.set_page.assert_called_once()
            # result 是 PageManager 实例
            assert result is mock_pm

# --------------------------------------------------------------------------- #
# PlayRunner._clean
# --------------------------------------------------------------------------- #

class TestClean:
    """_clean 资源清理测试。"""

    @pytest.mark.asyncio
    async def test_clean_closes_page_manager(self):
        """_clean 在 page_manager 存在时应调 page_manager.close。"""
        starter = MagicMock()
        starter.clear_logs = AsyncMock()
        r = PlayRunner(starter=starter)
        r.variable_manager = MagicMock()
        r.variable_manager.clear = AsyncMock()
        r.browser = None
        pm = MagicMock()
        pm.close = AsyncMock()
        await r._clean(page_manager=pm)
        pm.close.assert_called_once()
        r.variable_manager.clear.assert_called_once()
        starter.clear_logs.assert_called_once()

    @pytest.mark.asyncio
    async def test_clean_closes_browser_when_set(self):
        """_clean 在 self.browser 存在时应调 browser.close_all。"""
        starter = MagicMock()
        starter.clear_logs = AsyncMock()
        r = PlayRunner(starter=starter)
        r.variable_manager = MagicMock()
        r.variable_manager.clear = AsyncMock()
        mock_browser = MagicMock()
        mock_browser.close_all = AsyncMock()
        r.browser = mock_browser
        await r._clean(page_manager=None)
        mock_browser.close_all.assert_called_once()

# --------------------------------------------------------------------------- #
# PlayRunner.init_case_variables
# --------------------------------------------------------------------------- #

class TestInitCaseVariables:
    """init_case_variables 加载 case 关联的变量测试。"""

    @pytest.mark.asyncio
    async def test_no_variables_does_not_crash(self):
        """没变量时 init_case_variables 应跳过, 不报错。"""
        starter = MagicMock()
        starter.send = AsyncMock()
        r = PlayRunner(starter=starter)
        r.variable_manager = MagicMock()
        r.variable_manager.variables = {}
        play_case = MagicMock(id=1)
        with patch("croe.play.play_runner.PlayCaseVariablesMapper") as mock_vm_mapper:
            mock_vm_mapper.query_by = AsyncMock(return_value=[])
            await r.init_case_variables(play_case=play_case)
            mock_vm_mapper.query_by.assert_called_once_with(play_case_id=1)

    @pytest.mark.asyncio
    async def test_variables_added_to_variable_manager(self):
        """变量应被 add 到 variable_manager (用 case_var.key / value, value 经 trans)。"""
        starter = MagicMock()
        starter.send = AsyncMock()
        r = PlayRunner(starter=starter)
        r.variable_manager = MagicMock()
        r.variable_manager.variables = {}
        r.variable_manager.trans = AsyncMock(side_effect=lambda x: f"trans({x})")
        r.variable_manager.add_vars = AsyncMock()
        # mock 2 个 case var
        v1 = MagicMock(key="token", value="abc123")
        v2 = MagicMock(key="host", value="http://api.example.com")
        play_case = MagicMock(id=1)
        with patch("croe.play.play_runner.PlayCaseVariablesMapper") as mock_vm_mapper:
            mock_vm_mapper.query_by = AsyncMock(return_value=[v1, v2])
            await r.init_case_variables(play_case=play_case)
            # add_vars 应被调 2 次 (每变量 1 次)
            assert r.variable_manager.add_vars.call_count == 2
            # 第一次 add_vars 收到 {"token": "trans(abc123)"}
            first_call_args = r.variable_manager.add_vars.call_args_list[0].args[0]
            assert first_call_args == {"token": "trans(abc123)"}

    @pytest.mark.asyncio
    async def test_mapper_exception_does_not_raise_p1_8(self):
        """[BUG-P-1-8] mapper 抛异常时 init_case_variables 不应 raise (让 case 继续跑)。"""
        starter = MagicMock()
        starter.send = AsyncMock()
        r = PlayRunner(starter=starter)
        r.variable_manager = MagicMock()
        r.variable_manager.variables = {}
        play_case = MagicMock(id=1)
        with patch("croe.play.play_runner.PlayCaseVariablesMapper") as mock_vm_mapper:
            mock_vm_mapper.query_by = AsyncMock(side_effect=RuntimeError("DB 挂了"))
            # 不应抛
            await r.init_case_variables(play_case=play_case)
            # starter.send 应被调告知 WARNING
            assert any("⚠️" in str(call) for call in starter.send.call_args_list)

# --------------------------------------------------------------------------- #
# PlayRunner.run_case
# --------------------------------------------------------------------------- #

class TestRunCase:
    """run_case 端到端入口测试 (mock execute_case)。"""

    @pytest.mark.asyncio
    async def test_run_case_exception_propagates_after_log(self):
        """run_case 在 execute_case 抛异常时应 log 后 re-raise (让 controller 拿结果)。

        Notes: 这里测的是"log 异常 + raise" 的行为, 跟 run_case 自身 try/except/raise 的设计。
        """
        starter = MagicMock()
        starter.send = AsyncMock()
        r = PlayRunner(starter=starter)
        mock_case = MagicMock(id=1, title="C1")
        with patch("croe.play.play_runner.PlayCaseMapper") as mock_mapper, \
             patch.object(r, "init_case_variables", new=AsyncMock()), \
             patch("croe.play.play_runner.PlayCaseResultWriter") as mock_writer_cls, \
             patch.object(r, "execute_case", new=AsyncMock(side_effect=RuntimeError("case 跑炸"))):
            mock_mapper.get_by_id = AsyncMock(return_value=mock_case)
            mock_writer = MagicMock()
            mock_writer.init_result = AsyncMock(return_value=MagicMock(id=10))
            mock_writer_cls.return_value = mock_writer
            # 应抛 RuntimeError
            with pytest.raises(RuntimeError, match="case 跑炸"):
                await r.run_case(case_id=1)

    @pytest.mark.asyncio
    async def test_run_case_calls_init_then_execute(self):
        """run_case 应: get case → init vars → init result → execute。"""
        starter = MagicMock()
        starter.send = AsyncMock()
        r = PlayRunner(starter=starter)
        mock_case = MagicMock(id=1, title="C1")
        with patch("croe.play.play_runner.PlayCaseMapper") as mock_mapper, \
             patch.object(r, "init_case_variables", new=AsyncMock()) as mock_init_vars, \
             patch("croe.play.play_runner.PlayCaseResultWriter") as mock_writer_cls, \
             patch.object(r, "execute_case", new=AsyncMock(return_value=True)) as mock_exec:
            mock_mapper.get_by_id = AsyncMock(return_value=mock_case)
            mock_writer = MagicMock()
            mock_writer.init_result = AsyncMock(return_value=MagicMock(id=10))
            mock_writer_cls.return_value = mock_writer
            await r.run_case(case_id=1, error_continue=True)
            mock_init_vars.assert_called_once()
            mock_writer.init_result.assert_called_once()
            mock_exec.assert_called_once()
            # error_continue 应透传
            assert mock_exec.call_args.kwargs.get("error_continue") is True
