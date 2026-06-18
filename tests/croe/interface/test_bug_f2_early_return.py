"""
BUG-F2 回归测试:runner 在用例不存在或步骤为空时,应返回 (False, None) 二元组,
而不是直接 await starter.over() 的返回值(目前是 None,task 模式调用方
`success, _ = await ...` 会 TypeError)。

详见 docs/review/run_interface_case_deep_review.md。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from croe.interface.runner import InterfaceRunner
from tests.croe.interface._bug_ids import BUG_F2


@pytest.fixture
def bug_f2_marker():
    return BUG_F2


def _make_starter():
    starter = MagicMock()
    starter.send = AsyncMock()
    # 关键: 模拟现有 starter.over() 实际返回 None 的行为(BUG 源)
    starter.over = AsyncMock(return_value=None)
    starter.username = "u"
    starter.userId = 1
    starter.uid = "u-1"
    starter.logs = []
    return starter


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f2_early_return_when_case_not_found(bug_f2_marker):
    """[BUG-F2] case 不存在时,run_interface_case 应返回 (False, None) 二元组。"""
    runner = InterfaceRunner(starter=_make_starter())

    with patch(
        "app.mapper.interfaceApi.interfaceCaseMapper.InterfaceCaseMapper.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        result = await runner.run_interface_case(
            interface_case_id=999,
            env=1,
            error_stop=False,
        )

    assert result is not None, f"[{BUG_F2}] 早返路径不能返回 None"
    assert isinstance(result, tuple) and len(result) == 2, (
        f"[{BUG_F2}] 早返应是 (bool, Optional[Any]) 二元组,实际 {type(result)!r}"
    )
    assert result[0] is False, f"[{BUG_F2}] 早返 success 应为 False,实际 {result[0]!r}"
    assert result[1] is None, f"[{BUG_F2}] 早返 case_result 应为 None,实际 {result[1]!r}"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f2_early_return_when_no_steps(bug_f2_marker):
    """[BUG-F2] 用例存在但无步骤时,也应返回 (False, None)。"""
    runner = InterfaceRunner(starter=_make_starter())
    case = InterfaceCase(
        id=1, case_title="x", uid="u-1", project_id=1, module_id=1,
    )

    async def fake_get_by_id(ident, **_):
        return case if ident == 1 else None

    with patch(
        "app.mapper.interfaceApi.interfaceCaseMapper.InterfaceCaseMapper.get_by_id",
        new=AsyncMock(side_effect=fake_get_by_id),
    ), patch(
        "app.mapper.interfaceApi.interfaceCaseMapper.InterfaceCaseMapper.query_steps",
        new=AsyncMock(return_value=[]),
    ):
        result = await runner.run_interface_case(
            interface_case_id=1,
            env=1,
            error_stop=False,
        )

    assert result is not None
    assert isinstance(result, tuple) and len(result) == 2
    assert result[0] is False
    assert result[1] is None
