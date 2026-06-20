"""BUG-E12 回归测试: ExtractManager 应只返回成功提取 (含 value) 的 extract。"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from croe.interface.manager.extract_manager import ExtractManager
from tests.croe.interface._bug_ids import BUG_E12

@pytest.fixture
def bug_e12_marker():
    return BUG_E12

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_e12_no_handler_extract_dropped(bug_e12_marker):
    """[BUG-E12] 无 handler 的 extract 不应出现在返回 list。"""
    em = ExtractManager(response=MagicMock())
    extracts = [
        {'key': 'k1', 'target': 999},  # 没 handler
        {'key': 'k2', 'target': 998},  # 没 handler
    ]
    result = await em(extracts)
    assert result == [], (
        f"[{BUG_E12}] 无 handler 的 extract 必须被过滤, 实际 {result}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_e12_handler_exception_extract_dropped(bug_e12_marker):
    """[BUG-E12] handler 抛异常的 extract 不应出现在返回 list。"""
    em = ExtractManager(response=MagicMock())

    # mock 一个会抛异常的 handler
    async def boom(extract):
        raise KeyError("oops")

    # 注入到 handlers (用 monkey-patch)
    em._test_handler = boom
    # 直接调内部 handlers 字典
    from enums import ExtractTargetVariablesEnum
    from croe.interface.manager import extract_manager as em_mod
    orig = em_mod.ExtractManager.__call__

    # 用一个 mock dict 替换 handlers
    call_em = ExtractManager(response=MagicMock())

    # 通过 mock _handle_response_json_extract (已存在)
    call_em._handle_response_json_extract = AsyncMock(side_effect=KeyError("test"))

    extracts = [
        {'key': 'k1', 'target': ExtractTargetVariablesEnum.ResponseJsonExtract},
    ]
    result = await call_em(extracts)
    assert result == [], (
        f"[{BUG_E12}] handler 抛异常的 extract 必须被过滤, 实际 {result}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_e12_handler_returns_none_dropped(bug_e12_marker):
    """[BUG-E12] handler 返回 None 的 extract 不应出现在返回 list。"""
    from enums import ExtractTargetVariablesEnum

    em = ExtractManager(response=MagicMock())
    em._handle_response_json_extract = AsyncMock(return_value=None)

    extracts = [
        {'key': 'k1', 'target': ExtractTargetVariablesEnum.ResponseJsonExtract},
    ]
    result = await em(extracts)
    assert result == [], (
        f"[{BUG_E12}] handler 返回 None 的 extract 必须被过滤, 实际 {result}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_e12_successful_extract_kept(bug_e12_marker):
    """[BUG-E12] 成功提取 (handler 返回非 None value) 的 extract 必须保留。"""
    from enums import ExtractTargetVariablesEnum

    em = ExtractManager(response=MagicMock())
    em._handle_response_json_extract = AsyncMock(return_value="hello")

    extracts = [
        {'key': 'k1', 'target': ExtractTargetVariablesEnum.ResponseJsonExtract},
    ]
    result = await em(extracts)
    assert len(result) == 1, f"[{BUG_E12}] 成功提取必须保留, 实际 {result}"
    assert result[0].get('value') == "hello", (
        f"[{BUG_E12}] result[0]['value'] 应为 'hello', 实际 {result[0].get('value')}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_e12_mixed_partial_success(bug_e12_marker):
    """[BUG-E12] 混合场景: 成功的保留, 失败/None 的过滤。"""
    from enums import ExtractTargetVariablesEnum

    em = ExtractManager(response=MagicMock())
    em._handle_response_json_extract = AsyncMock(side_effect=[None, "value2", Exception("boom")])

    extracts = [
        {'key': 'k1', 'target': ExtractTargetVariablesEnum.ResponseJsonExtract},  # None -> drop
        {'key': 'k2', 'target': ExtractTargetVariablesEnum.ResponseJsonExtract},  # "value2" -> keep
        {'key': 'k3', 'target': ExtractTargetVariablesEnum.ResponseJsonExtract},  # Exception -> drop
        {'key': 'k4', 'target': 999},  # no handler -> drop
    ]
    result = await em(extracts)
    assert len(result) == 1, (
        f"[{BUG_E12}] 混合场景应只保留 1 个 (k2), 实际 {len(result)} 个: {result}"
    )
    assert result[0].get('key') == 'k2', (
        f"[{BUG_E12}] 保留的应是 k2, 实际 {result[0].get('key')}"
    )
    assert result[0].get('value') == "value2"
