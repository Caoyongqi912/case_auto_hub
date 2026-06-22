"""
2026-06-22 Round 2 P1 收尾批 - 6 个 P1 一锅端
回归测试: tests/croe/interface/test_bug_p1_5_to_p1_10_batch.py

涵盖 BUG_ID:
- BUG_P1_5: kwargs["id"] code smell (2 处 mapper)
- BUG_P1_6: try_interface/try_group 缺清理 (clear_trace_id + vm.clear + rw.clear_cache)
- BUG_P1_7: run_interface_case try/except 范围太大
- BUG_P1_8: interface_result.content_result_id NULL 回填
- BUG_P1_9: _flush_cache 失败 cache 丢 retry queue
- BUG_P1_10: starter.over 返回 None
"""
import inspect
import re
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from tests.croe.interface._bug_ids import (
    BUG_P1_5,
    BUG_P1_6,
    BUG_P1_7,
    BUG_P1_8,
    BUG_P1_9,
    BUG_P1_10,
)


# ============================================================
# kwargs["id"] code smell
# ============================================================
class TestBugP15KwargsId:
    """kwargs["id"] = xxx 模式应在 2 个 mapper 中消除"""

    def test_interface_case_mapper_no_kwargs_id_mutation(self):
        """interfaceCaseMapper.update_interface_case 不能再有 kwargs["id"] = case_id"""
        import ast
        from app.mapper.interfaceApi import interfaceCaseMapper
        src = inspect.getsource(interfaceCaseMapper)
        tree = ast.parse(src)
        target = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "update_interface_case":
                target = node
                break
        assert target, "update_interface_case not found"
        body_lines = [l for l in ast.unparse(target).splitlines() if not l.strip().startswith("#")]
        body_code = "\n".join(body_lines)
        assert "kwargs[\"id\"]" not in body_code, (
            f"[{BUG_P1_5}] update_interface_case 实际代码仍含 kwargs[\"id\"] mutation"
        )

    def test_interface_mapper_no_kwargs_id_mutation(self):
        """interfaceMapper.update_interface 不能再有 kwargs["id"] = interface_id"""
        import ast
        from app.mapper.interfaceApi import interfaceMapper
        src = inspect.getsource(interfaceMapper)
        tree = ast.parse(src)
        target = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "update_interface":
                target = node
                break
        assert target, "update_interface not found"
        body_lines = [l for l in ast.unparse(target).splitlines() if not l.strip().startswith("#")]
        body_code = "\n".join(body_lines)
        assert "kwargs[\"id\"]" not in body_code, (
            f"[{BUG_P1_5}] update_interface 实际代码仍含 kwargs[\"id\"] mutation"
        )

    def test_case_mapper_passes_id_to_update_by_id(self):
        """update_by_id 调用必须显式传 id=case_id"""
        from app.mapper.interfaceApi import interfaceCaseMapper
        src = inspect.getsource(interfaceCaseMapper)
        match = re.search(
            r"async def update_interface_case\(cls.*?(?=\n    @|\nclass )",
            src, re.DOTALL,
        )
        body = match.group(0)
        assert "id=case_id" in body, (
            f"[{BUG_P1_5}] update_by_id 调用应显式 id=case_id"
        )

    def test_interface_mapper_passes_id_to_update_by_id(self):
        """interfaceMapper.update_by_id 应显式 id=interface_id"""
        from app.mapper.interfaceApi import interfaceMapper
        src = inspect.getsource(interfaceMapper)
        match = re.search(
            r"async def update_interface\(cls.*?(?=\n    @|\nclass )",
            src, re.DOTALL,
        )
        body = match.group(0)
        assert "id=interface_id" in body, (
            f"[{BUG_P1_5}] update_by_id 调用应显式 id=interface_id"
        )


# ============================================================
# try_interface/try_group 缺清理
# ============================================================
class TestBugP16TryInterfaceCleanup:
    """try_interface / try_group 的 finally 缺 trace_id / vm.clear / rw.clear_cache"""

    def _runner_src(self):
        from croe.interface import runner
        return inspect.getsource(runner)

    def test_try_interface_finally_clears_vm_and_rw(self):
        """try_interface finally 必须有 variable_manager.clear + result_writer.clear_cache"""
        src = self._runner_src()
 # 找 try_interface 函数体
        m = re.search(
            r"async def try_interface\(.*?(?=\n    async def)",
            src, re.DOTALL,
        )
        assert m, "try_interface not found"
        body = m.group(0)
        assert "self.variable_manager.clear" in body, (
            f"[{BUG_P1_6}] try_interface 缺 variable_manager.clear"
        )
        assert "self.result_writer.clear_cache" in body, (
            f"[{BUG_P1_6}] try_interface 缺 result_writer.clear_cache"
        )

    def test_try_group_finally_clears_vm_and_rw(self):
        """try_group finally 必须有 variable_manager.clear + result_writer.clear_cache"""
        src = self._runner_src()
        m = re.search(
            r"async def try_group\(.*?(?=\n    async def)",
            src, re.DOTALL,
        )
        assert m, "try_group not found"
        body = m.group(0)
        assert "self.variable_manager.clear" in body, (
            f"[{BUG_P1_6}] try_group 缺 variable_manager.clear"
        )
        assert "self.result_writer.clear_cache" in body, (
            f"[{BUG_P1_6}] try_group 缺 result_writer.clear_cache"
        )

    def test_try_interface_no_clear_trace_id(self):
        """try_interface 不应 clear_trace_id (自己不设, 会误伤外层)"""
        import ast
        src = self._runner_src()
        tree = ast.parse(src)
        target = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "try_interface":
                target = node
                break
        assert target, "try_interface not found"
        body_lines = [l for l in ast.unparse(target).splitlines() if not l.strip().startswith("#")]
        body_code = "\n".join(body_lines)
        assert "clear_trace_id" not in body_code, (
            f"[{BUG_P1_6}] try_interface 实际代码仍调 clear_trace_id"
        )


# ============================================================
# run_interface_case try/except 范围太大
# ============================================================
class TestBugP17TryExceptScope:
    """run_interface_case 主 try/except 不应捕获 step 级异常 (单步应自处理)"""

    def test_step_loop_extracted_to_method(self):
        """step loop 应被抽到 _execute_steps 独立方法"""
        from croe.interface import runner
        src = inspect.getsource(runner)
        assert "async def _execute_steps" in src, (
            f"[{BUG_P1_7}] 应有 _execute_steps 独立方法"
        )

    def test_step_loop_inner_try_except(self):
        """_execute_steps 内部每步应有独立 try/except"""
        from croe.interface import runner
        src = inspect.getsource(runner)
        m = re.search(
            r"async def _execute_steps\(.*?(?=\n    async def)",
            src, re.DOTALL,
        )
        assert m, "_execute_steps not found"
        body = m.group(0)
 # 内部 strategy.execute 应该被 try 包
        assert re.search(
            r"try:\s*\n\s*strategy\s*=\s*get_step_strategy",
            body,
        ), f"[{BUG_P1_7}] _execute_steps 内部 strategy.execute 缺独立 try/except"
        assert "step_success = False" in body, (
            f"[{BUG_P1_7}] 失败路径应设 step_success=False 而非 raise"
        )

    def test_run_interface_case_calls_execute_steps(self):
        """run_interface_case 应调 self._execute_steps 而不是内联 step loop"""
        from croe.interface import runner
        src = inspect.getsource(runner)
        m = re.search(
            r"async def run_interface_case\(.*?(?=\n    async def)",
            src, re.DOTALL,
        )
        body = m.group(0)
        assert "await self._execute_steps" in body, (
            f"[{BUG_P1_7}] run_interface_case 应调 self._execute_steps"
        )
 # 主 try 不应再包 strategy.execute
        main_try_match = re.search(
            r"try:\s*\n.*?await self\._execute_steps",
            body, re.DOTALL,
        )
        assert main_try_match, "main try not found"
        main_try_block = main_try_match.group(0)
        assert "strategy = get_step_strategy" not in main_try_block, (
            f"[{BUG_P1_7}] 主 try 块不应包含 strategy 调用 (已拆到 _execute_steps)"
        )


# ============================================================
# interface_result.content_result_id NULL 回填
# ============================================================
class TestBugP18ContentResultIdBackfill:
    """step_content_api 应回填 interface_result.content_result_id"""

    def test_write_step_result_has_immediate_param(self):
        """write_step_result 应支持 immediate 参数"""
        from croe.interface.writer import result_writer
        src = inspect.getsource(result_writer.ResultWriter.write_step_result)
        assert "immediate: bool = False" in src, (
            f"[{BUG_P1_8}] write_step_result 缺 immediate 参数"
        )

    def test_write_step_result_immediate_returns_result(self):
        """immediate=True 时 write_step_result 应走 insert_result 路径"""
        from croe.interface.writer import result_writer
        src = inspect.getsource(result_writer.ResultWriter.write_step_result)
        assert "is_parent_step or immediate" in src, (
            f"[{BUG_P1_8}] write_step_result 应在 is_parent_step or immediate 时立即插入"
        )

    def test_step_content_api_uses_immediate_true(self):
        """step_content_api 应传 immediate=True 拿 id 回填"""
        from croe.interface.executor.step_content import step_content_api
        src = inspect.getsource(step_content_api)
 # 找 execute 方法
        m = re.search(
            r"async def execute\(self, step_context.*?(?=\n    async def|class |\Z)",
            src, re.DOTALL,
        )
        assert m, "execute not found"
        body = m.group(0)
        assert "immediate=True" in body, (
            f"[{BUG_P1_8}] step_content_api.execute 缺 immediate=True"
        )

    def test_step_content_api_backfills_content_result_id(self):
        """拿到 content_result 后应 update interface_result.content_result_id"""
        from croe.interface.executor.step_content import step_content_api
        src = inspect.getsource(step_content_api)
        m = re.search(
            r"async def execute\(self, step_context.*?(?=\n    async def|class |\Z)",
            src, re.DOTALL,
        )
        body = m.group(0)
 # 应该有 update_by_id(id=interface_result.id, content_result_id=...)
        assert re.search(
            r"update_by_id\(\s*id\s*=\s*interface_result\.id\s*,\s*content_result_id\s*=\s*content_result\.id",
            body, re.DOTALL,
        ) is not None, (
            f"[{BUG_P1_8}] 缺 update_by_id 回填 interface_result.content_result_id"
        )


# ============================================================
# _flush_cache 失败 cache 丢 retry queue
# ============================================================
class TestBugP19FlushCacheRetry:
    """_flush_cache 失败时把 cache 推到 retry queue 而不是直接清空"""

    def test_result_writer_has_retry_queue(self):
        """ResultWriter 应有 _retry_queue 字段"""
        from croe.interface.writer import result_writer
        src = inspect.getsource(result_writer.ResultWriter)
        assert "_retry_queue" in src, (
            f"[{BUG_P1_9}] ResultWriter 缺 _retry_queue 字段"
        )

    def test_result_writer_has_max_retry_count(self):
        """ResultWriter 应有 MAX_RETRY_COUNT 常量"""
        from croe.interface.writer import result_writer
        src = inspect.getsource(result_writer.ResultWriter)
        assert "MAX_RETRY_COUNT" in src, (
            f"[{BUG_P1_9}] ResultWriter 缺 MAX_RETRY_COUNT 常量"
        )

    def test_flush_cache_consumes_retry_queue(self):
        """_flush_cache 入口应消费 _retry_queue"""
        from croe.interface.writer import result_writer
        src = inspect.getsource(result_writer.ResultWriter._flush_cache)
        assert "_retry_queue" in src, (
            f"[{BUG_P1_9}] _flush_cache 应消费 _retry_queue"
        )

    def test_flush_cache_pushes_to_retry_on_failure(self):
        """降级路径失败时 cache 推到 _retry_queue"""
        from croe.interface.writer import result_writer
        src = inspect.getsource(result_writer.ResultWriter._flush_cache)
 # 应该有一个 except 块 catch 降级失败
        assert "_retry_queue.append" in src, (
            f"降级失败时缺 _retry_queue.append(...)"
        )

    def test_clear_cache_clears_retry_queue(self):
        """clear_cache 应同时清 _retry_queue 防止跨 case 残留"""
        from croe.interface.writer import result_writer
        src = inspect.getsource(result_writer.ResultWriter.clear_cache)
        assert "_retry_queue" in src, (
            f"[{BUG_P1_9}] clear_cache 缺 _retry_queue.clear()"
        )


# ============================================================
# starter.over 返回 None
# ============================================================
class TestBugP110StarterOverReturn:
    """starter.over 应有显式类型注解 + 显式 return"""

    def test_over_has_optional_dict_annotation(self):
        """SocketSender.over 应有 -> Optional[Dict[str, Any]] 注解"""
        from utils.io_sender import SocketSender
        sig = inspect.signature(SocketSender.over)
 # 检查 type annotation
        assert sig.return_annotation is not inspect.Signature.empty, (
            f"[{BUG_P1_10}] over() 缺 return type annotation"
        )
        ann_str = str(sig.return_annotation)
        assert "Optional" in ann_str or "Dict" in ann_str or "None" in ann_str, (
            f"[{BUG_P1_10}] over() return type 应是 Optional[Dict], 实际 {ann_str}"
        )

    def test_over_returns_data_dict(self):
        """over() 应返回 data dict (成功) 或 None (失败)"""
        from utils.io_sender import SocketSender

        class FakeIO:
            async def emit(self, **kwargs):
                return None

        sender = SocketSender.__new__(SocketSender)
        sender._event = "test"
        sender._ns = "/test"
        sender.uid = "u1"
        sender.logs = []
        sender.userId = 0
        sender.startBy = 0

        async def run():
            with patch("utils.io_sender.async_io", FakeIO()):
                return await sender.over(reportId=42)

        result = None
        import asyncio
        result = asyncio.run(run())
 # 成功时返回 data dict
        assert isinstance(result, dict), (
            f"[{BUG_P1_10}] over() 成功时返回 dict, 实际 {type(result)}"
        )
        assert result["code"] == 1
        assert result["data"]["rId"] == 42

    def test_over_returns_none_on_emit_failure(self):
        """emit 抛异常时 over() 应返回 None"""
        from utils.io_sender import SocketSender

        class FakeIOBoom:
            async def emit(self, **kwargs):
                raise RuntimeError("ws down")

        sender = SocketSender.__new__(SocketSender)
        sender._event = "test"
        sender._ns = "/test"
        sender.uid = "u1"
        sender.logs = []
        sender.userId = 0
        sender.startBy = 0

        async def run():
            with patch("utils.io_sender.async_io", FakeIOBoom()):
                return await sender.over(reportId=99)

        import asyncio
        result = asyncio.run(run())
        assert result is None, (
            f"[{BUG_P1_10}] emit 失败时 over() 应返回 None, 实际 {result}"
        )

    def test_task_py_no_return_await_over(self):
        """task.py 不应再用 `return await self.starter.over()`"""
        from croe.interface import task
        src = inspect.getsource(task)
        assert "return await self.starter.over()" not in src, (
            f"[{BUG_P1_10}] task.py 仍用 return await starter.over() "
            f"(over 之前返回 None, 调用方解包会 TypeError)"
        )
