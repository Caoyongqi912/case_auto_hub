"""BUG-F5 回归测试: error_stop 触发时, case_result.progress 不应被强制 100,"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from tests.croe.interface._bug_ids import BUG_F5

REPO = Path(__file__).resolve().parents[3]

@pytest.fixture
def bug_f5_marker():
    return BUG_F5

def _make_starter():
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.username = "u"
    starter.userId = 1
    starter.uid = "u-1"
    starter.logs = []
    starter.over = AsyncMock()
    return starter

# ---------- 1. runner 源码不再 force 100 ----------

def test_bug_f5_runner_does_not_force_progress_100(bug_f5_marker):
    """[BUG-F5] runner 的 error_stop break 路径不能 `case_result.progress = 100`"""
    src = (REPO / "croe/interface/runner.py").read_text(encoding="utf-8")
    # 找 error_stop 块
    block_start = src.find("if not case_success and error_stop:")
    assert block_start > 0, f"[{BUG_F5}] runner.py 找不到 error_stop 分支"
    # 取这一段到下一个 break (大约 200 字符内)
    snippet = src[block_start: block_start + 500]
    assert "case_result.progress = 100" not in snippet, (
        f"[{BUG_F5}] runner.py 在 error_stop 分支里又把 progress 强制 100, "
        f"前端会误以为跑完了"
    )

# ---------- 2. finalize 写库用 case_result.progress ----------

def test_bug_f5_finalize_uses_case_result_progress(bug_f5_marker):
    """[BUG-F5] finalize_case_result 末尾 progress 写库不能硬编码 100.0"""
    src = (REPO / "croe/interface/writer/result_writer.py").read_text(encoding="utf-8")
    # 在 finalize_case_result 函数体里找 update_by_id
    finalize_idx = src.find("async def finalize_case_result")
    body = src[finalize_idx: finalize_idx + 6000]
    assert "progress=100.0" not in body, (
        f"[{BUG_F5}] finalize 还在写 progress=100.0, 应改用 case_result.progress"
    )
    assert "progress=case_result.progress" in body, (
        f"[{BUG_F5}] finalize 没传 case_result.progress, error_stop 进度会丢"
    )

# ---------- 3. 端到端: error_stop 触发时 progress 应是中间值 ----------

@pytest.mark.asyncio
async def test_bug_f5_error_stop_progress_is_intermediate(bug_f5_marker):
    """
    [    """
    from croe.interface.runner import InterfaceRunner
    from croe.interface.executor.context import ExecutionContext

    starter = _make_starter()
    runner = InterfaceRunner(starter=starter)

    # 模拟 4 个 step content, 第 2 个会失败
    class FakeContent:
        def __init__(self, idx, content_type="STEP_API", enable=1):
            self.id = idx
            self.uid = f"u-{idx}"
            self.content_type = content_type
            self.target_id = 1
            self.content_desc = f"step{idx}"
            self.content_name = f"step{idx}"
            self.enable = enable
            self.resolved_content_name = f"step{idx}"
        def __repr__(self):
            return f"<FakeContent id={self.id}>"

    step_contents = [FakeContent(i) for i in range(1, 5)]

    # mock case_result
    case_result = MagicMock()
    case_result.id = 1
    case_result.success_num = 0
    case_result.fail_num = 0
    case_result.progress = 0
    case_result.start_time = "2026-06-19 00:00:00"
    case_result.interface_case_id = 3
    case_result.interface_case_uid = "fake"
    case_result.interface_case_name = "fake"
    case_result.interface_case_desc = "fake"
    case_result.project_id = 1
    case_result.module_id = 1
    case_result.starter_id = 1
    case_result.starter_name = "u"
    case_result.running_env_id = 1
    case_result.running_env_name = "Mini"
    case_result.status = "RUNNING"
    case_result.map = {"start_time": "2026-06-19 00:00:00"}
    case_result.interface_log = None

    # mock strategy: 第 1 步成功, 第 2 步失败, 后面的不会跑 (error_stop)
    call_count = {"n": 0}
    async def fake_execute(step_context):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return True
        if call_count["n"] == 2:
            step_context.execution_context.case_result.result = "ERROR"
            return False
        raise AssertionError("error_stop 后续 step 不应被调用")

    # patch init_case_result 让它返回我们准备好的 case_result MagicMock
    # insert(model) 签名, 我们忽略 model 直接返回 case_result
    async def fake_init_case_result(model):
        return case_result

    with patch(
        "app.mapper.interfaceApi.interfaceCaseMapper.InterfaceCaseMapper.get_by_id",
        new=AsyncMock(return_value=MagicMock(
            id=3, case_title="fake", case_desc="", case_api_num=4,
            project_id=1, module_id=1, uid="fake"
        )),
    ), patch(
        "app.mapper.interfaceApi.interfaceCaseMapper.InterfaceCaseMapper.query_steps",
        new=AsyncMock(return_value=step_contents),
    ), patch(
        "croe.interface.runner.get_step_strategy",
        return_value=MagicMock(execute=fake_execute),
    ), patch(
        "app.mapper.project.env.EnvMapper.get_by_id",
        new=AsyncMock(return_value=MagicMock(id=1, name="Mini", url="http://x", headers={})),
    ), patch(
        "app.mapper.interfaceApi.interfaceResultMapper.InterfaceCaseResultMapper.insert",
        new=AsyncMock(side_effect=fake_init_case_result),
    ), patch(
        "app.mapper.interfaceApi.interfaceVarsMapper.InterfaceVarsMapper.query_by",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.mapper.interfaceApi.interfaceGlobalMapper.InterfaceGlobalHeaderMapper.query_all",
        new=AsyncMock(return_value=[]),
    ):
        success, cr = await runner.run_interface_case(
            interface_case_id=3, env=1, error_stop=True, task_result=None
        )

    # 验证: 跑到第 2 步失败就停了
    assert call_count["n"] == 2, f"[{BUG_F5}] 期望跑 2 步就停, 实际跑了 {call_count['n']}"
    # 关键: progress 应是 50, 不是 100
    # 修复前会是 100, 修复后是 50
    final_progress = case_result.progress
    assert final_progress == 50, (
        f"[{BUG_F5}] error_stop 触发时 progress 应该是 (2*100)//4=50, "
        f"实际是 {final_progress}; 修复前会被强制 100"
    )
    assert success is False, f"[{BUG_F5}] success 应是 False (第 2 步失败)"
