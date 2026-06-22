"""`SCRIPT_TIMEOUT` 必须真生效,死循环脚本不能阻塞 worker。"""

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
    """while True: pass 应当在 ~SCRIPT_TIMEOUT 秒内抛错或终止。"""
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
    """SCRIPT_TIMEOUT 应当作为类/实例属性可读。"""
    sm = ScriptManager()
    assert hasattr(sm, "SCRIPT_TIMEOUT"), (
        f"[{BUG_S3}] ScriptManager 应当有 SCRIPT_TIMEOUT 属性"
    )
    assert sm.SCRIPT_TIMEOUT > 0, "SCRIPT_TIMEOUT 必须为正数"
