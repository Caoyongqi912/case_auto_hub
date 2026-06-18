"""
烟雾测试:跑通 run_interface_case 主流程骨架,不接真实业务,只验证接口形状。

所有 mock 在各 BUG 测试里已覆盖;这里只做端到端形状检查。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.integration
@pytest.mark.asyncio
async def test_smoke_run_interface_case_returns_tuple_when_case_missing():
    """用例不存在时,返回 (False, None) 二元组(BUG-F2 修复 + 接口形状)。"""
    from croe.interface.runner import InterfaceRunner
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.over = AsyncMock()
    starter.username = "u"
    starter.userId = 1
    starter.uid = "u-1"
    starter.logs = []

    runner = InterfaceRunner(starter=starter)

    with patch(
        "app.mapper.interfaceApi.interfaceCaseMapper.InterfaceCaseMapper.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        result = await runner.run_interface_case(
            interface_case_id=999,
            env=1,
            error_stop=False,
        )

    assert result is not None
    assert isinstance(result, tuple) and len(result) == 2
    assert result[0] is False
    assert result[1] is None


@pytest.mark.integration
def test_smoke_runner_holds_independent_result_writer():
    """每个 InterfaceRunner 持有独立 ResultWriter (BUG-D1 修复)。"""
    from croe.interface.runner import InterfaceRunner
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.username = "u"
    starter.userId = 1

    r1 = InterfaceRunner(starter=starter)
    r2 = InterfaceRunner(starter=starter)

    assert r1.result_writer is not r2.result_writer
    # 缓存列表也独立
    assert r1.result_writer.api_result_cache is not r2.result_writer.api_result_cache
