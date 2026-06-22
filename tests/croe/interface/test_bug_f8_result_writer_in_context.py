"""`result_writer` 必须从 ExecutionContext 拿,不能再用模块级单例。"""

import ast
from pathlib import Path
import pytest

from tests.croe.interface._bug_ids import BUG_F8

@pytest.fixture
def bug_f8_marker():
    return BUG_F8

REPO = Path(__file__).resolve().parents[3]

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

# ---------- 1. writer/__init__.py 不再导出 result_writer 单例 ----------

def test_bug_f8_writer_init_does_not_export_singleton(bug_f8_marker):
    """writer/__init__.py 不应再暴露模块级 result_writer 单例"""
    src = _read(REPO / "croe" / "interface" / "writer" / "__init__.py")

    # 禁止出现 `result_writer = ResultWriter()` 这种模块级赋值
    tree = ast.parse(src)
    bad = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "result_writer":
                    bad.append(t.id)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "result_writer":
                bad.append(node.target.id)
    assert not bad, (
        f"[{BUG_F8}] writer/__init__.py 仍有模块级单例 result_writer "
        f"(匹配到 {bad}), 删掉即可"
    )

# ---------- 2. step_content_*.py / task.py / play_interface_strategy.py
#     不能 `from croe.interface.writer import result_writer` ----------

FILES_MUST_NOT_IMPORT_SINGLETON = [
    "croe/interface/executor/step_content/step_content_api.py",
    "croe/interface/executor/step_content/step_content_group.py",
    "croe/interface/executor/step_content/step_content_condition.py",
    "croe/interface/executor/step_content/step_content_loop.py",
    "croe/interface/executor/step_content/step_content_assert.py",
    "croe/interface/executor/step_content/step_content_db.py",
    "croe/interface/executor/step_content/step_content_script.py",
    "croe/interface/executor/step_content/step_content_wait.py",
    "croe/interface/task.py",
    "croe/play/executor/step_content_strategy/play_interface_strategy.py",
]

@pytest.mark.parametrize("rel_path", FILES_MUST_NOT_IMPORT_SINGLETON)
def test_bug_f8_no_module_singleton_import(bug_f8_marker, rel_path):
    """这些文件不能 `import result_writer` 模块单例"""
    src = _read(REPO / rel_path)
    forbidden = [
        "from croe.interface.writer import result_writer",
        "from croe.interface.writer.result_writer import result_writer",
    ]
    for f in forbidden:
        assert f not in src, (
            f"[{BUG_F8}] {rel_path} 仍在 import 模块单例: {f}\n"
            f"应改用 step_context.result_writer 或 self.result_writer"
        )

# ---------- 3. ExecutionContext 包含 result_writer 字段 ----------

def test_bug_f8_execution_context_has_result_writer(bug_f8_marker):
    """ExecutionContext 必须包含 result_writer 字段"""
    from croe.interface.executor.context import ExecutionContext
    from dataclasses import fields
    names = {f.name for f in fields(ExecutionContext)}
    assert "result_writer" in names, (
        f"[{BUG_F8}] ExecutionContext 缺 result_writer 字段, "
        f"实际字段: {names}"
    )

# ---------- 4. CaseStepContext 提供 .result_writer 便捷 property ----------

def test_bug_f8_case_step_context_has_result_writer_property(bug_f8_marker):
    """CaseStepContext 应有 result_writer property 桥接到 ExecutionContext"""
    from croe.interface.executor.context import CaseStepContext
    cls_attr = vars(CaseStepContext)
    assert "result_writer" in cls_attr, (
        f"[{BUG_F8}] CaseStepContext 缺 result_writer property"
    )
    assert isinstance(cls_attr["result_writer"], property), (
        f"[{BUG_F8}] CaseStepContext.result_writer 应是 property"
    )

# ---------- 5. Runner 注入 ExecutionContext 时传 self.result_writer ----------

def test_bug_f8_runner_injects_result_writer_into_context(bug_f8_marker):
    """runner.run_interface_case 创建 ExecutionContext 必须传 self.result_writer"""
    src = _read(REPO / "croe" / "interface" / "runner.py")
    assert "result_writer=self.result_writer" in src, (
        f"[{BUG_F8}] runner.py 未把 self.result_writer 注入 ExecutionContext"
    )

# ---------- 6. TaskRunner 自有 self.result_writer ----------

def test_bug_f8_task_runner_has_own_result_writer(bug_f8_marker):
    """TaskRunner 应在 __init__ 里 self.result_writer = ResultWriter()"""
    src = _read(REPO / "croe" / "interface" / "task.py")
    assert "self.result_writer = ResultWriter()" in src, (
        f"[{BUG_F8}] task.py 未在 TaskRunner.__init__ 创建自有 result_writer"
    )
    # 必须替换 3 个原 result_writer.* 调用
    for call in (
        "self.result_writer.update_task_progress",
        "self.result_writer.init_task_result",
        "self.result_writer.finalize_task_result",
    ):
        assert call in src, f"[{BUG_F8}] task.py 缺 {call}"

# ---------- 7. 端到端: runner 用的 result_writer 跟 context 注入 ----------

def test_bug_f8_runner_result_writer_is_same_as_context(bug_f8_marker):
    """ExecutionContext.result_writer 必须 === runner.result_writer"""
    from unittest.mock import MagicMock, AsyncMock
    from croe.interface.runner import InterfaceRunner
    from croe.interface.executor.context import ExecutionContext

    starter = MagicMock()
    starter.send = AsyncMock()
    starter.username = "u"
    starter.userId = 1
    starter.uid = "u-1"
    starter.logs = []
    starter.over = AsyncMock()

    runner = InterfaceRunner(starter=starter)

    # mock 掉用到的 mapper, 让 run_interface_case 跑到 ExecutionContext 创建即可
    ctx = ExecutionContext(
        interface_case=MagicMock(),
        env=MagicMock(),
        case_result=MagicMock(id=1),
        result_writer=runner.result_writer,
    )
    assert ctx.result_writer is runner.result_writer, (
        f"[{BUG_F8}] 注入的 result_writer 不是 runner 自有实例, 仍会丢 cache"
    )
