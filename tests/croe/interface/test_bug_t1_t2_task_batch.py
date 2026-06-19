"""
[BUG-T1 + T2] 任务级 execution 2 个 P0 一锅端, 来自 EXECUTION_LAYERS_REVIEW_2026_06_20。

BUG-T1: task.py:_init_task_variables 之前只 log.info 一行, 函数名说
       "init task variables" 但实际 params.variables 永远不注入
       VariableManager, 用户传的任务级变量静默丢失。
       修: TaskRunner 自管 self._shared_vm, params.variables 走 trans 后
       add_vars 进去, 后续每个 InterfaceRunner 共享这个 vm, 任务级
       variables 跨 API/CASE step 全局可见。

BUG-T2: runner.py:run_interface_by_task 之前整个函数没 try/finally,
       跑完一个 task (N 个 interface) 后 httpx 连接池不释放 (E1 漏修到
       这条路径), variable / result_writer 缓存跨 case 残留 (D1 / OBS-2
       漏修到这条路径), 跨 task 累积泄漏 / 串号。
       修: 加 try/finally 跟 run_interface_case 清理顺序对齐:
       aclose → rw.clear_cache → vm.clear。
"""
import inspect
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.croe.interface._bug_ids import BUG_T1, BUG_T2


# --------------------------------------------------------------------------- #
# BUG-T1: _init_task_variables 真的注入变量
# --------------------------------------------------------------------------- #

def test_bug_t1_init_task_variables_actually_adds_to_vm():
    """[BUG-T1] _init_task_variables 必须真的调 self._shared_vm.add_vars(...)。

    修前: 函数体只 await self.starter.send(...), log.info 一行,
    params.variables 静默丢失。
    """
    from croe.interface.task import TaskRunner

    src = inspect.getsource(TaskRunner._init_task_variables)

    # 1. 必须有 add_vars 调用
    assert "add_vars" in src, (
        f"[{BUG_T1}] _init_task_variables 必须调 add_vars, "
        f"否则 params.variables 静默丢失"
    )

    # 2. 必须引用 _shared_vm (自管 vm)
    assert "_shared_vm" in src, (
        f"[{BUG_T1}] _init_task_variables 应走 self._shared_vm, "
        f"不是 InterfaceRunner 的 vm"
    )

    # 3. 不应再只 log.info 一行 (修前的"假函数"模式)
    #    简化判断: 调 starter.send 之前/之后必须 add_vars
    add_vars_pos = src.find("add_vars")
    send_pos = src.find("starter.send")
    assert add_vars_pos > 0 and send_pos > 0, (
        f"[{BUG_T1}] _init_task_variables 应同时有 add_vars 和 starter.send"
    )
    # add_vars 必须在 send 之前 (init 完再 log)
    assert add_vars_pos < send_pos, (
        f"[{BUG_T1}] add_vars 必须在 starter.send 之前, "
        f"先 init 再 log, 不能 log 了再 init"
    )


@pytest.mark.asyncio
async def test_bug_t1_init_task_variables_end_to_end():
    """[BUG-T1] 端到端: 传 dict 进去, _shared_vm 应该有这个 key=value。"""
    from croe.interface.task import TaskRunner
    from croe.interface.starter import APIStarter

    # 构造一个最小 starter (只 mock, 不接 socket)
    starter = MagicMock(spec=APIStarter)
    starter.send = AsyncMock()
    starter.username = "test"
    starter.startBy = 1
    starter.userId = 1
    starter.uid = "test-uid"

    # TaskRunner 只 init 内部 vm + mock starter, 不跑 task
    runner = TaskRunner(starter=starter)

    # 传一个 dict 进去
    await runner._init_task_variables({"base_url": "https://staging.api.com"})

    # 验 _shared_vm 有 base_url=staging
    assert "base_url" in runner._shared_vm.variables, (
        f"[{BUG_T1}] _shared_vm 缺 base_url, 实际 vars: {runner._shared_vm.variables}"
    )
    assert runner._shared_vm.variables["base_url"] == "https://staging.api.com", (
        f"[{BUG_T1}] _shared_vm.base_url 值不对, 实际: "
        f"{runner._shared_vm.variables.get('base_url')}"
    )


@pytest.mark.asyncio
async def test_bug_t1_init_task_variables_none_noop():
    """[BUG-T1] 传 None 不应崩, 也不应误注入。"""
    from croe.interface.task import TaskRunner
    from croe.interface.starter import APIStarter

    starter = MagicMock(spec=APIStarter)
    starter.send = AsyncMock()
    starter.username = "test"
    starter.startBy = 1
    starter.userId = 1
    starter.uid = "test-uid"

    runner = TaskRunner(starter=starter)
    await runner._init_task_variables(None)

    # 静默 noop, vm 仍空
    assert runner._shared_vm.variables == {}, (
        f"[{BUG_T1}] None 输入时 vm 应仍空, 实际: {runner._shared_vm.variables}"
    )


def test_bug_t1_interface_runner_accepts_optional_variable_manager():
    """[BUG-T1] InterfaceRunner.__init__ 应接受 optional variable_manager 参数,
    TaskRunner 注入 _shared_vm 时不报错。
    """
    from croe.interface.runner import InterfaceRunner
    from croe.a_manager import VariableManager

    sig = inspect.signature(InterfaceRunner.__init__)
    params = sig.parameters

    assert "variable_manager" in params, (
        f"[{BUG_T1}] InterfaceRunner.__init__ 应有 variable_manager 参数, "
        f"实际参数: {list(params.keys())}"
    )

    # 验证 default 是 None (不传时回退到新建, 不破坏现有调用方)
    vm_param = params["variable_manager"]
    assert vm_param.default is None, (
        f"[{BUG_T1}] variable_manager 应该有 default=None, 实际: {vm_param.default!r}"
    )


# --------------------------------------------------------------------------- #
# BUG-T2: run_interface_by_task finally 清理
# --------------------------------------------------------------------------- #

def test_bug_t2_run_interface_by_task_has_try_finally():
    """[BUG-T2] run_interface_by_task 函数体必须有 try/finally 包裹 retry 循环。"""
    from croe.interface.runner import InterfaceRunner

    src = inspect.getsource(InterfaceRunner.run_interface_by_task)

    # 1. 必须有 try 和 finally
    assert "try:" in src, (
        f"[{BUG_T2}] run_interface_by_task 必须有 try 块, "
        f"清理 httpx/vm/rw 缓存"
    )
    assert "finally:" in src, (
        f"[{BUG_T2}] run_interface_by_task 必须有 finally 块, "
        f"跟 run_interface_case 风格对齐"
    )

    # 2. try 必须在 for attempt 之前 (包住整个重试循环)
    try_pos = src.find("try:")
    for_pos = src.find("for attempt in range")
    assert try_pos > 0 and try_pos < for_pos, (
        f"[{BUG_T2}] try 必须在 for attempt 之前, "
        f"实际 try_pos={try_pos}, for_pos={for_pos}"
    )

    # 3. finally 必须在 for 之后
    finally_pos = src.find("finally:")
    assert finally_pos > for_pos, (
        f"[{BUG_T2}] finally 必须在 for 之后, "
        f"实际 finally_pos={finally_pos}, for_pos={for_pos}"
    )


def test_bug_t2_finally_cleans_three_things():
    """[BUG-T2] finally 块必须调 aclose + rw.clear_cache + vm.clear, 跟
    run_interface_case 清理风格对齐。
    """
    from croe.interface.runner import InterfaceRunner

    src = inspect.getsource(InterfaceRunner.run_interface_by_task)

    # 提取 finally 块
    finally_m = re.search(r"finally:\s*\n(.*?)(?=\n    (?:async )?def |\Z)", src, re.DOTALL)
    assert finally_m, f"[{BUG_T2}] 找不到 finally 块"
    finally_block_raw = finally_m.group(1)

    # 去掉注释行, 避免误命中修复注释里描述"不调什么"的引用
    finally_block = "\n".join(
        ln for ln in finally_block_raw.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )

    # 必须有 3 个清理调用
    assert "interface_executor.aclose" in finally_block, (
        f"[{BUG_T2}] finally 必须调 interface_executor.aclose() (E1 风格)"
    )
    assert "result_writer.clear_cache" in finally_block, (
        f"[{BUG_T2}] finally 必须调 result_writer.clear_cache() (D1 风格)"
    )
    assert "variable_manager.clear" in finally_block, (
        f"[{BUG_T2}] finally 必须调 variable_manager.clear() (防跨 case 残留)"
    )

    # 不应调 starter.over (外层 _execute_api_steps 统一调, 重复调让前端收 N+1 次)
    assert "starter.over" not in finally_block, (
        f"[{BUG_T2}] finally 不应调 starter.over(), 跟外层 _execute_api_steps "
        f"finally 重复, 会让前端收到 N+1 个 over 事件"
    )

    # 不应调 clear_trace_id (本函数自己不设 trace_id, 清会误伤外层)
    assert "clear_trace_id" not in finally_block, (
        f"[{BUG_T2}] finally 不应调 clear_trace_id(), 那是 run_interface_case "
        f"设的, 本函数不设, 清会误伤"
    )


@pytest.mark.asyncio
async def test_bug_t2_finally_runs_even_on_exception():
    """[BUG-T2] 端到端: 接口执行抛异常时, finally 清理仍要跑。"""
    from croe.interface.runner import InterfaceRunner
    from croe.interface.starter import APIStarter
    from croe.interface.executor.interface_executor import InterfaceExecutor
    from croe.interface.writer.result_writer import ResultWriter
    from croe.a_manager import VariableManager

    # 构造一个 runner, mock 各依赖
    starter = MagicMock(spec=APIStarter)
    starter.send = AsyncMock()
    starter.username = "test"
    starter.startBy = 1
    starter.userId = 1
    starter.uid = "test-uid"

    runner = InterfaceRunner(starter=starter)
    # mock executor 让它抛异常
    runner.interface_executor.execute = AsyncMock(
        side_effect=RuntimeError("boom")
    )
    runner.interface_executor.aclose = AsyncMock()
    runner.interface_executor.g_headers = []

    # mock clear_cache / clear
    runner.result_writer.clear_cache = MagicMock()
    runner.variable_manager.clear = AsyncMock()

    # mock InterfaceGlobalHeaderMapper 避免真查 DB
    with patch(
        "app.mapper.interfaceApi.interfaceGlobalMapper"
        ".InterfaceGlobalHeaderMapper.query_all",
        new=AsyncMock(return_value=[]),
    ):
        # execute 抛异常, finally 仍要跑清理
        with pytest.raises(RuntimeError, match="boom"):
            await runner.run_interface_by_task(
                interface=MagicMock(),
                task_result_id=42,
            )

    # finally 三个清理都跑了
    runner.interface_executor.aclose.assert_awaited()
    runner.result_writer.clear_cache.assert_called_once()
    runner.variable_manager.clear.assert_awaited_once()
