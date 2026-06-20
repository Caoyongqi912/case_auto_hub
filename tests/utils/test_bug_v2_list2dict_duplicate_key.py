"""BUG-V2 回归测试: list2dict 检测重复 key 并 WARNING。"""

import pytest
import logging
from loguru import logger

from utils._generate import GenerateTools
from tests.croe.interface._bug_ids import BUG_V2

@pytest.fixture
def bug_v2_marker():
    return BUG_V2

@pytest.fixture
def capture_loguru():
    """捕获 loguru 的 warning 日志。"""
    captured = []

    def sink(message):
        captured.append(str(message))

    handler_id = logger.add(sink, level="WARNING", format="{message}")
    yield captured
    logger.remove(handler_id)

@pytest.mark.unit
def test_bug_v2_duplicate_key_logs_warning(bug_v2_marker, capture_loguru):
    """[BUG-V2] 重复 key 必须 WARNING, 不能静默覆盖。"""
    result = GenerateTools.list2dict([
        {'key': 'a', 'value': 1},
        {'key': 'a', 'value': 2},
    ])
    # last-wins 语义保持
    assert result == {'a': 2}, (
        f"[{BUG_V2}] 应保持 last-wins 语义, 实际 {result}"
    )
    # 但必须有 warning
    assert any("BUG-V2" in m and "'a'" in m for m in capture_loguru), (
        f"[{BUG_V2}] 必须有 BUG-V2 警告, 实际捕获: {capture_loguru}"
    )

@pytest.mark.unit
def test_bug_v2_no_warning_for_unique_keys(bug_v2_marker, capture_loguru):
    """[BUG-V2] 唯一 key 不应触发警告。"""
    result = GenerateTools.list2dict([
        {'key': 'a', 'value': 1},
        {'key': 'b', 'value': 2},
    ])
    assert result == {'a': 1, 'b': 2}
    assert not any("BUG-V2" in m for m in capture_loguru), (
        f"[{BUG_V2}] 唯一 key 不应触发 BUG-V2 警告, 实际捕获: {capture_loguru}"
    )

@pytest.mark.unit
def test_bug_v2_three_duplicate_keys(bug_v2_marker, capture_loguru):
    """[BUG-V2] 3 个重复 key 应触发 2 次警告 (前 2 次被后覆盖)。"""
    result = GenerateTools.list2dict([
        {'key': 'a', 'value': 1},
        {'key': 'a', 'value': 2},
        {'key': 'a', 'value': 3},
    ])
    assert result == {'a': 3}
    warnings = [m for m in capture_loguru if "BUG-V2" in m and "'a'" in m]
    assert len(warnings) == 2, (
        f"[{BUG_V2}] 3 个重复 key 应有 2 次警告, 实际 {len(warnings)} 次: {warnings}"
    )
