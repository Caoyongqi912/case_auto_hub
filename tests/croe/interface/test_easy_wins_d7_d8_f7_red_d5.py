"""
Easy wins 回归测试:D7 / D8 / F7 / RED-D5

详见 docs/review/run_interface_case_deep_review.md。
"""
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.interface.writer.result_writer import ResultWriter
from tests.croe.interface._bug_ids import BUG_D1  # 借用 marker, 避免 _bug_ids 散乱

# ===========================================================
# D7: InterfaceGroupMapper.copy_interface 不再有死代码 if not group
# ===========================================================

@pytest.mark.unit
def test_bug_d7_copy_interface_no_dead_group_check():
    """copy_interface 不应再有 `if not group: raise` 死代码。"""
    from app.mapper.interfaceApi.interfaceGroupMapper import InterfaceGroupMapper
    src = inspect.getsource(InterfaceGroupMapper.copy_interface)
    assert "if not group:" not in src, (
        f"copy_interface 还有 if not group 死代码, get_by_id 已经会抛 NotFind"
    )
    assert "if not interface:" not in src, (
        f"copy_interface 还有 if not interface 死代码, 同上"
    )

# ===========================================================
# D8 (已废) + BUG-COPY-CONTENT: copy_content 必须用 creatorName=, 不能再 username=
# ===========================================================
#
# 历史: 旧版 D8 修时把 `username=user.username` 当 "对" 的写进 copy_content.
#       但 BaseModel 列定义是 creatorName, 不是 username, 实际是对所有类型
#       都会 TypeError. Round 4 BUG-COPY-CONTENT 顺带修这个字段名错.
# 锁住: 改完后的正确行为 (creatorName=user.username, 不再 username=).

@pytest.mark.unit
def test_bug_d8_copy_content_uses_creator_name_kwarg():
    """[BUG-COPY-CONTENT] copy_content 必须 creatorName=user.username, 不再 username=."""
    from app.mapper.interfaceApi.interfaceCaseContentMapper import (
        InterfaceCaseContentMapper,
    )
    src = inspect.getsource(InterfaceCaseContentMapper.copy_content)
    # 排除注释行后再检查
    code_lines = [
        line for line in src.splitlines()
        if not line.strip().startswith("#")
    ]
    code_text = "\n".join(code_lines)
    assert "creatorName=user.username" in code_text, (
        f"[BUG-COPY-CONTENT] copy_content 应 creatorName=user.username, 实际没找到"
    )
    assert "username=user.username" not in code_text, (
        f"[BUG-COPY-CONTENT] copy_content 不能 username=user.username (字段名错)"
    )

# ===========================================================
# F7: init_case_result 不再有误导性 log.info
# ===========================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f7_init_case_result_does_not_log_obj_directly():
    """init_case_result 在 if task_result: 分支里不应再有 'task_result {}'.format(...) 这种 log。"""

    # 模拟一个最小化的 case_result / task_result, 走完 init_case_result 看 log 行为
    with patch("croe.interface.writer.result_writer.InterfaceCaseResultMapper") as mock_mapper, \
         patch("croe.interface.writer.result_writer.log.info") as mock_log_info:
        # 让 insert 直接返回传入的对象
        mock_mapper.insert = AsyncMock(side_effect=lambda x: x)

        rw = ResultWriter()
        fake_case = MagicMock()
        fake_case.id = 1
        fake_case.case_title = "t"
        fake_case.uid = "u-1"
        fake_case.case_desc = "d"
        fake_case.project_id = 1
        fake_case.module_id = 1
        fake_case.case_api_num = 5

        fake_starter = MagicMock()
        fake_starter.userId = 1
        fake_starter.username = "u"

        fake_env = MagicMock()
        fake_env.id = 1
        fake_env.name = "env"

        fake_task = MagicMock()
        fake_task.id = 99

        await rw.init_case_result(
            interface_case=fake_case,
            starter=fake_starter,
            env=fake_env,
            task_result=fake_task,
        )

        # 检查所有 log.info 调用: 不应再有 "task_result {}" 形式的 str.format 调用
        for call in mock_log_info.call_args_list:
            msg = str(call.args[0]) if call.args else ""
            assert not (
                "task_result {" in msg or "task_result{}" in msg
            ), f"仍然有误导性 log.info: {msg!r}"

# ===========================================================
# RED-D5: ResultWriter 不再有 _progress_update_cache 死字段
# ===========================================================

@pytest.mark.unit
def test_bug_red_d5_no_progress_update_cache():
    """[RED-D5] ResultWriter 不应再定义 _progress_update_cache (死字段)。"""
    rw = ResultWriter()
    assert not hasattr(rw, "_progress_update_cache"), (
        f"[RED-D5] _progress_update_cache 仍是死字段, 应删除"
    )

@pytest.mark.unit
def test_bug_red_d5_clear_cache_does_not_touch_dead_field():
    """[RED-D5] clear_cache 不应再 touch _progress_update_cache。"""
    src = inspect.getsource(ResultWriter.clear_cache)
    assert "_progress_update_cache" not in src, (
        f"[RED-D5] clear_cache 还在清死字段, 应删除"
    )
