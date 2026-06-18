"""
BUG-S3 回归测试:`SCRIPT_TIMEOUT` 必须真生效,死循环脚本不能阻塞 worker。

详见 docs/review/run_interface_case_deep_review.md。

实现要点:在子进程跑脚本,主进程用 proc.join(timeout) 等待,超时就
proc.terminate() -> proc.kill(),然后抛 ScriptSecurityError。

测试用 pytest 自身 + 外层 `timeout 30` 命令保护,避免子进程清理失败时
把整个 session 挂死。
"""
import time
import pytest

from croe.a_manager.script_manager import ScriptManager, ScriptSecurityError
from tests.croe.interface._bug_ids import BUG_S3


@pytest.fixture
def bug_s3_marker():
    return BUG_S3


@pytest.mark.security
@pytest.mark.unit
def test_bug_s3_infinite_loop_terminates_within_timeout(bug_s3_marker):
    """[BUG-S3] while True: pass 应当在 ~SCRIPT_TIMEOUT 秒内抛错或终止。"""
    sm = ScriptManager()
    start = time.time()
    with pytest.raises(Exception):
        sm.execute("while True: pass")
    elapsed = time.time() - start
    # 给 2 秒 buffer,因为是子进程 / signal 终止会有延迟
    assert elapsed < (sm.SCRIPT_TIMEOUT + 2), (
        f"[{BUG_S3}] 死循环应在 SCRIPT_TIMEOUT ({sm.SCRIPT_TIMEOUT}s) 内终止,"
        f"实际 {elapsed:.2f}s"
    )


@pytest.mark.unit
def test_bug_s3_script_timeout_constant_defined(bug_s3_marker):
    """[BUG-S3] SCRIPT_TIMEOUT 应当作为类/实例属性可读。"""
    sm = ScriptManager()
    assert hasattr(sm, "SCRIPT_TIMEOUT"), (
        f"[{BUG_S3}] ScriptManager 应当有 SCRIPT_TIMEOUT 属性"
    )
    assert sm.SCRIPT_TIMEOUT > 0, "SCRIPT_TIMEOUT 必须为正数"
