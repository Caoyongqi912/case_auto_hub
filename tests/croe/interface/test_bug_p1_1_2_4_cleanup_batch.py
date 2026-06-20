"""[BUG-P1-1 + P1-2 + P1-4] 3 个 P1 一锅端, 来自 EXECUTION_LAYERS_REVIEW_2026_06_20。"""

import inspect
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.croe.interface._bug_ids import BUG_P1_1, BUG_P1_2, BUG_P1_4

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def test_bug_p1_1_no_magic_200_in_build_result():
    """[
    修前: `is_success = ctx.response.status_code == 200`
    修后: `is_success = ctx.response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS`
    """
    from croe.interface.executor.interface_executor import InterfaceExecutor

    src = inspect.getsource(InterfaceExecutor._build_result)

    # 1. 不应有 == 200 硬编码
    # 找 code_lines (剥注释), 避免误命中注释
    code_lines = [
        ln for ln in src.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    code_only = "\n".join(code_lines)
    assert " == 200" not in code_only, (
        f"[{BUG_P1_1}] _build_result 不应硬编码 ' == 200', "
        f"改用 InterfaceResponseStatusCodeEnum.SUCCESS"
    )
    # 2. 应该有 enum
    assert "InterfaceResponseStatusCodeEnum.SUCCESS" in code_only, (
        f"[{BUG_P1_1}] _build_result 应使用 "
        f"InterfaceResponseStatusCodeEnum.SUCCESS"
    )

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def test_bug_p1_2_slots_no_global_headers():
    """[
    修前: __slots__ = ("starter", "variable_manager", "interface_executor",
                       "global_headers", "result_writer")
    修后: __slots__ = ("starter", "variable_manager", "interface_executor",
                       "result_writer")
    """
    from croe.interface.runner import InterfaceRunner

    src = inspect.getsource(InterfaceRunner)

    # 1. __slots__ 块不应含 global_headers
    slots_m = re.search(r"__slots__\s*=\s*\(([^)]+)\)", src)
    assert slots_m, f"[{BUG_P1_2}] 找不到 __slots__ 块"
    slots_str = slots_m.group(1)
    assert "global_headers" not in slots_str, (
        f"[{BUG_P1_2}] __slots__ 不应含 'global_headers', "
        f"self.global_headers 永为 stale 空 list, 实际: {slots_str}"
    )

    # 2. __init__ 不应设 self.global_headers = ...
    init_m = re.search(r"def __init__\(.*?\n(.*?)(?=\n    (?:async )?def |\Z)", src, re.DOTALL)
    assert init_m
    init_body = init_m.group(1)
    # 剥注释
    init_body_code = "\n".join(
        ln for ln in init_body.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )
    assert "self.global_headers" not in init_body_code, (
        f"[{BUG_P1_2}] __init__ 不应设 self.global_headers, "
        f"字段已删, 单一来源 executor.g_headers"
    )

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def test_bug_p1_4_try_interface_has_try_finally():
    """[BUG-P1-4] try_interface 函数体必须有 try/finally, finally 调 aclose。"""
    from croe.interface.runner import InterfaceRunner

    src = inspect.getsource(InterfaceRunner.try_interface)

    assert "try:" in src and "finally:" in src, (
        f"[{BUG_P1_4}] try_interface 必须有 try/finally 调 aclose, "
        )

    # finally 必须调 aclose
    finally_m = re.search(r"finally:\s*\n(.*?)(?=\n    (?:async )?def |\Z)", src, re.DOTALL)
    assert finally_m
    finally_block = "\n".join(
        ln for ln in finally_m.group(1).splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )
    assert "interface_executor.aclose" in finally_block, (
        f"[{BUG_P1_4}] try_interface finally 必须调 interface_executor.aclose()"
    )

def test_bug_p1_4_try_group_has_try_finally():
    """[BUG-P1-4] try_group 函数体必须有 try/finally, finally 调 aclose。"""
    from croe.interface.runner import InterfaceRunner

    src = inspect.getsource(InterfaceRunner.try_group)

    assert "try:" in src and "finally:" in src, (
        f"[{BUG_P1_4}] try_group 必须有 try/finally 调 aclose, "
        )

    # finally 必须调 aclose
    finally_m = re.search(r"finally:\s*\n(.*?)(?=\n    (?:async )?def |\Z)", src, re.DOTALL)
    assert finally_m
    finally_block = "\n".join(
        ln for ln in finally_m.group(1).splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )
    assert "interface_executor.aclose" in finally_block, (
        f"[{BUG_P1_4}] try_group finally 必须调 interface_executor.aclose()"
    )

@pytest.mark.asyncio
async def test_bug_p1_4_try_interface_finally_runs_on_exception():
    """[BUG-P1-4] 端到端: try_interface 抛异常时 finally 仍调 aclose。"""
    from croe.interface.runner import InterfaceRunner
    from croe.interface.starter import APIStarter

    starter = MagicMock(spec=APIStarter)
    starter.send = AsyncMock()
    starter.username = "test"
    starter.startBy = 1
    starter.userId = 1
    starter.uid = "test-uid"

    runner = InterfaceRunner(starter=starter)
    runner.interface_executor.aclose = AsyncMock()
    runner.interface_executor.g_headers = []

    # mock InterfaceMapper.get_by_id 返 mock interface
    fake_interface = MagicMock()
    fake_env = MagicMock()
    fake_env.id = 1
    fake_env.name = "test"

    with patch(
        "app.mapper.interfaceApi.interfaceMapper.InterfaceMapper.get_by_id",
        new=AsyncMock(return_value=fake_interface),
    ), patch(
        "app.mapper.project.env.EnvMapper.get_by_id",
        new=AsyncMock(return_value=fake_env),
    ), patch(
        "app.mapper.interfaceApi.interfaceGlobalMapper"
        ".InterfaceGlobalHeaderMapper.query_all",
        new=AsyncMock(return_value=[]),
    ):
        # executor.execute 抛异常
        runner.interface_executor.execute = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        with pytest.raises(RuntimeError, match="boom"):
            await runner.try_interface(interface_id=1, env_id=1)

    # finally 跑了 aclose
    runner.interface_executor.aclose.assert_awaited()

@pytest.mark.asyncio
async def test_bug_p1_4_try_group_finally_runs_on_exception():
    """[BUG-P1-4] 端到端: try_group 抛异常时 finally 仍调 aclose。"""
    from croe.interface.runner import InterfaceRunner
    from croe.interface.starter import APIStarter

    starter = MagicMock(spec=APIStarter)
    starter.send = AsyncMock()
    starter.username = "test"
    starter.startBy = 1
    starter.userId = 1
    starter.uid = "test-uid"

    runner = InterfaceRunner(starter=starter)
    runner.interface_executor.aclose = AsyncMock()
    runner.interface_executor.g_headers = []

    fake_env = MagicMock()
    fake_env.id = 1
    fake_env.name = "test"

    with patch(
        "app.mapper.interfaceApi.interfaceGroupMapper"
        ".InterfaceGroupMapper.query_association_interfaces",
        new=AsyncMock(return_value=[MagicMock(), MagicMock()]),
    ), patch(
        "app.mapper.project.env.EnvMapper.get_by_id",
        new=AsyncMock(return_value=fake_env),
    ), patch(
        "app.mapper.interfaceApi.interfaceGlobalMapper"
        ".InterfaceGlobalHeaderMapper.query_all",
        new=AsyncMock(return_value=[]),
    ):
        # execute 第一次抛异常
        runner.interface_executor.execute = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        with pytest.raises(RuntimeError, match="boom"):
            await runner.try_group(group_id=1, env_id=1)

    # finally 跑了 aclose
    runner.interface_executor.aclose.assert_awaited()
