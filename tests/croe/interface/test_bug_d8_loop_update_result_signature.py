"""
[BUG-D8] APILoopContentStrategy._update_loop_result 漏收 step_context 参数

根因: 函数体里直接 `await step_context.result_writer.update_step_result(...)`,
但函数签名只有 (content_result, all_success, loop_count, success_count,
fail_count, case_result, loop_items) — 没有 step_context。

后果: 4 个调用点 (_execute_loop_times / _execute_loop_items /
_execute_loop_items-empty / _execute_loop_condition) 全部传了
content_result=content_result 但漏传 step_context,
循环跑完一进入 _update_loop_result 就 NameError, 整 case 跑挂。

生产 traceback:
  File "step_content_loop.py", line 405, in _update_loop_result
    await step_context.result_writer.update_step_result(...)
NameError: name 'step_context' is not defined

修复:
  1. 函数签名加 step_context: CaseStepContext 作为第一个参数
  2. 4 个调用点都加 step_context=step_context

本测试 (3 个, 不接 DB):
  1. AST 检查 _update_loop_result 签名包含 step_context
  2. AST 检查 4 个调用点都传 step_context=step_context
  3. 端到端 mock: 直接调 _update_loop_result 验证不再 NameError
"""
import ast
import inspect
import textwrap
from unittest.mock import AsyncMock, MagicMock
import pytest


def _parse_strategy_class():
    """从 source 解析 APILoopContentStrategy 类, 拿到方法定义列表"""
    from croe.interface.executor.step_content.step_content_loop import APILoopContentStrategy
    return APILoopContentStrategy


def test_bug_d8_update_loop_result_signature_has_step_context():
    """核心回归: _update_loop_result 必须收 step_context 参数"""
    cls = _parse_strategy_class()
    sig = inspect.signature(cls._update_loop_result)
    params = list(sig.parameters.keys())
    assert "step_context" in params, (
        f"[BUG-D8] _update_loop_result 漏收 step_context, 当前参数: {params}。"
        f"\n函数体内直接 await step_context.result_writer.update_step_result(...),"
        f"\n但调用方不传就 NameError 整 case 跑挂。"
    )


def test_bug_d8_all_four_call_sites_pass_step_context():
    """
    防御: 4 个 _update_loop_result 调用点必须都传 step_context=step_context

    锁定 4 个调用点: _execute_loop_times, _execute_loop_items (空 items 短路),
    _execute_loop_items (正常结束), _execute_loop_condition
    """
    from croe.interface.executor.step_content import step_content_loop
    src = inspect.getsource(step_content_loop)

    # 找出所有 self._update_loop_result( 调用
    import re
    calls = re.findall(
        r'await self\._update_loop_result\(\s*\n(.*?)\n\s*\)',
        src, re.DOTALL,
    )
    # 4 个调用点 (3 个外层 + 1 个空 items 短路)
    assert len(calls) == 4, f"期望 4 个 _update_loop_result 调用, 实际 {len(calls)}"

    for i, body in enumerate(calls, 1):
        assert "step_context=step_context" in body, (
            f"[BUG-D8] 第 {i} 个 _update_loop_result 调用漏传 step_context=step_context\n"
            f"调用体:\n{textwrap.indent(body, '    ')}"
        )


@pytest.mark.asyncio
async def test_bug_d8_update_loop_result_actually_runs_without_nameerror():
    """
    端到端: 直接调 _update_loop_result 验证不 NameError

    用 mock 模拟 step_context.result_writer.update_step_result + case_result
    """
    from croe.interface.executor.step_content.step_content_loop import APILoopContentStrategy

    strategy = APILoopContentStrategy.__new__(APILoopContentStrategy)

    # mock step_context — _update_loop_result 内部调两次 result_writer
    # (update_step_result + update_case_progress), 两个都要 mock
    mock_update_step = AsyncMock()
    mock_update_progress = AsyncMock()
    mock_result_writer = MagicMock()
    mock_result_writer.update_step_result = mock_update_step
    mock_result_writer.update_case_progress = mock_update_progress
    mock_step_context = MagicMock()
    mock_step_context.result_writer = mock_result_writer

    # mock content_result (loop result row)
    mock_content_result = MagicMock()
    mock_content_result.id = 123

    # mock case_result
    mock_case_result = MagicMock()
    mock_case_result.success_num = 0
    mock_case_result.fail_num = 0
    mock_case_result.result = None

    # 这条原本会 NameError, 现在应该正常走完
    await strategy._update_loop_result(
        step_context=mock_step_context,
        content_result=mock_content_result,
        all_success=False,
        loop_count=2,
        success_count=0,
        fail_count=2,
        case_result=mock_case_result,
        loop_items=None,
    )

    # 验证 update_step_result 被调过 (不再 NameError)
    mock_update_step.assert_awaited_once()
    call_kwargs = mock_update_step.await_args.kwargs
    assert call_kwargs["result_id"] == 123
    assert call_kwargs["loop_count"] == 2
    assert call_kwargs["success_count"] == 0
    assert call_kwargs["fail_count"] == 2
    assert call_kwargs["result"] is False
    # case_result 内存修改也对
    assert mock_case_result.fail_num == 1
    # update_case_progress 也会被调 (BUG-D8 实际有两处 step_context 引用)
    mock_update_progress.assert_awaited_once_with(mock_case_result)
