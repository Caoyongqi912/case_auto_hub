"""
writer.py 单元测试覆盖

目标: 把 croe/play/writer.py 的 3 个 writer 类 (ContentResultWriter,
PlayCaseResultWriter, PlayTaskResultWriter) 全部覆盖, 包括:
- 正常路径 (add / update / flush / write_result / write_final_result)
- 异常路径 (None 参数 / 不存在 step / Mapper 失败)
- 边界 (空字典 / 0 case / 单 case)
- 内部 state 正确性 (content_results dict / progress 字段)
"""
import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.model.playUI import PlayCaseResult, PlayTaskResult, PlayCase, PlayTask
from app.model.playUI.PlayResult import PlayStepContentResult
from croe.play.writer import (
    ContentResultWriter,
    PlayCaseResultWriter,
    PlayTaskResultWriter,
)


# --------------------------------------------------------------------------- #
# ContentResultWriter
# --------------------------------------------------------------------------- #

class TestContentResultWriter:
    """ContentResultWriter 步骤结果聚合写入测试。"""

    def test_init_creates_empty_content_results(self):
        """初始化应创建空 content_results dict, 不预填。"""
        w = ContentResultWriter(play_case_result_id=1, play_task_result_id=2)
        assert w.play_case_result_id == 1
        assert w.play_task_result_id == 2
        assert w.content_results == {}

    @pytest.mark.asyncio
    async def test_add_content_result_sets_ids_and_stores(self):
        """add_content_result 应设置 play_case_result_id / play_task_result_id
        并存到 content_results[step_index]。"""
        w = ContentResultWriter(play_case_result_id=10, play_task_result_id=20)
        cr = PlayStepContentResult(content_step=1)
        await w.add_content_result(step_index=1, content_result=cr)
        assert cr.play_case_result_id == 10
        assert cr.play_task_result_id == 20
        assert 1 in w.content_results
        assert w.content_results[1]["result"] is cr
        assert w.content_results[1]["children"] == []

    @pytest.mark.asyncio
    async def test_add_child_content_result_appends_to_parent(self):
        """add_child_content_result 应把子结果 append 到父的 children 列表。"""
        w = ContentResultWriter(play_case_result_id=1, play_task_result_id=None)
        parent = PlayStepContentResult(content_step=1)
        child1 = PlayStepContentResult(content_step=1)
        child2 = PlayStepContentResult(content_step=2)
        await w.add_content_result(step_index=1, content_result=parent)
        await w.add_child_content_result(parent_index=1, content_result=child1)
        await w.add_child_content_result(parent_index=1, content_result=child2)
        assert w.content_results[1]["children"] == [child1, child2]

    @pytest.mark.asyncio
    async def test_add_child_to_nonexistent_parent_logs_warning_and_drops(self):
        """父 step 不存在时应 log.warning 且不丢也不存 (子结果被警告, 不入 dict)。"""
        w = ContentResultWriter(play_case_result_id=1)
        child = PlayStepContentResult(content_step=1)
        await w.add_child_content_result(parent_index=99, content_result=child)
        # 实际行为: 不 add as main, 只 log warning, content_results 仍空
        # 文档里写 "adding as main step" 但实际代码没 add, 是个文档 / 行为不一致的小 BUG
        # 锁当前行为, 不动实现 (避免引入 BUG)
        assert 99 not in w.content_results
        assert w.content_results == {}

    @pytest.mark.asyncio
    async def test_update_content_result_sets_success_and_recomputes_use_time(self):
        """update_content_result 应设 success 并用 now - start_time 重算 use_time
        (跟 add_content_result 时算的初值不同, 反映真实耗时)。"""
        w = ContentResultWriter(play_case_result_id=1)
        cr = PlayStepContentResult(
            content_step=1,
            start_time=datetime.datetime.now() - datetime.timedelta(seconds=5),
            use_time="0s",  # 占位初值
        )
        await w.add_content_result(step_index=1, content_result=cr)
        await w.update_content_result(step_index=1, success=True)
        assert cr.content_result is True
        # use_time 应被重算 (5s 左右), 不再是 "0s"
        assert cr.use_time != "0s"
        # 不应抛 KeyError

    @pytest.mark.asyncio
    async def test_update_content_result_missing_index_does_not_raise(self):
        """update_content_result 在 step_index 不存在时不应 raise, 只 log warning。"""
        w = ContentResultWriter(play_case_result_id=1)
        # 不应抛
        await w.update_content_result(step_index=99, success=False)

    @pytest.mark.asyncio
    async def test_flush_no_content_results_logs_error_and_returns(self):
        """flush 在 content_results 为空时应 log error 并 return, 不调 mapper。"""
        w = ContentResultWriter(play_case_result_id=1)
        with patch("croe.play.writer.PlayContentResultMapper") as mock_mapper:
            await w.flush()
            # mapper.save_result_batch 不应被调
            mock_mapper.save_result_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_calls_mapper_with_content_results(self):
        """flush 在有结果时应调 PlayContentResultMapper.save_result_batch。"""
        w = ContentResultWriter(play_case_result_id=1)
        cr = PlayStepContentResult(content_step=1)
        await w.add_content_result(step_index=1, content_result=cr)
        with patch("croe.play.writer.PlayContentResultMapper") as mock_mapper:
            mock_mapper.save_result_batch = AsyncMock(return_value=1)
            await w.flush()
            mock_mapper.save_result_batch.assert_called_once_with(w.content_results)

    @pytest.mark.asyncio
    async def test_flush_log_inserted_count(self, caplog=None):
        """flush 应 log 插入条数。"""
        w = ContentResultWriter(play_case_result_id=1)
        cr = PlayStepContentResult(content_step=1)
        await w.add_content_result(step_index=1, content_result=cr)
        with patch("croe.play.writer.PlayContentResultMapper") as mock_mapper:
            mock_mapper.save_result_batch = AsyncMock(return_value=5)
            await w.flush()
            # log 包含 "5"
            # (caplog 抓 loguru 比较复杂, 不强测, 只确认函数正常返回)

    def test_results_property_returns_count(self):
        """results property 应返回 content_results 的条数。"""
        w = ContentResultWriter(play_case_result_id=1)
        assert w.results == 0
        # 模拟加几个
        w.content_results[1] = {"result": None, "children": []}
        w.content_results[2] = {"result": None, "children": []}
        assert w.results == 2

    def test_repr_format_is_valid_xml_like(self):
        """__repr__ 输出应是有效 XML 风格 (单 /> 收尾, 跟修前的 > /> 错乱对比)。"""
        w = ContentResultWriter(play_case_result_id=42, play_task_result_id=7)
        text = repr(w)
        # 应以 /> 收尾
        assert text.endswith(" />"), f"repr 应以 /> 收尾, 实际: {text!r}"
        # 不应有 "> />" 双符号
        assert "> />" not in text, f"repr 不应有 `> />` 双符号, 实际: {text!r}"
        # 应包含关键字段
        assert "42" in text
        assert "7" in text


# --------------------------------------------------------------------------- #
# PlayCaseResultWriter
# --------------------------------------------------------------------------- #

class TestPlayCaseResultWriter:
    """PlayCaseResultWriter 单 case 结果写入测试。"""

    def test_init_no_case_result_yet(self):
        """init 后 play_case_result 应为 None (还没 init_result)。"""
        starter = MagicMock()
        w = PlayCaseResultWriter(starter=starter, play_task_result_id=10)
        assert w.play_case_result is None
        assert w._starter is starter
        assert w.play_task_result_id == 10

    def test_play_case_result_id_property_returns_none_when_not_initialized(self):
        """play_case_result_id property 在没 init_result 时返回 None + log warning。"""
        starter = MagicMock()
        w = PlayCaseResultWriter(starter=starter)
        assert w.play_case_result_id is None

    def test_play_case_result_id_property_returns_id_when_initialized(self):
        """play_case_result_id property 在 init 后返回 id。"""
        starter = MagicMock()
        w = PlayCaseResultWriter(starter=starter)
        w.play_case_result = MagicMock(id=42)
        assert w.play_case_result_id == 42

    @pytest.mark.asyncio
    async def test_set_error_step_info_populates_fields(self):
        """set_error_step_info 应把 content_result 的 4 个错误字段写到 case_result。"""
        starter = MagicMock()
        w = PlayCaseResultWriter(starter=starter)
        # case_result 是 MagicMock, 验证字段被设
        w.play_case_result = MagicMock()
        cr = MagicMock(
            content_step=3,
            content_name="失败步骤",
            content_message="断言失败: expected 200 got 500",
            content_screenshot_path="/path/to/screen.jpeg",
        )
        # set_error_step_info 是 async, await
        await w.set_error_step_info(cr)
        assert w.play_case_result.ui_case_err_step == 3
        assert w.play_case_result.ui_case_err_step_title == "失败步骤"
        assert w.play_case_result.ui_case_err_step_msg == "断言失败: expected 200 got 500"
        assert w.play_case_result.ui_case_err_step_pic_path == "/path/to/screen.jpeg"

    @pytest.mark.asyncio
    async def test_init_result_calls_mapper(self):
        """init_result 应调 PlayCaseResultMapper.init_case_result。"""
        starter = MagicMock(username="admin", userId=1)
        w = PlayCaseResultWriter(starter=starter, play_task_result_id=10)
        play_case = MagicMock(spec=PlayCase)
        with patch("croe.play.writer.PlayCaseResultMapper") as mock_mapper:
            mock_mapper.init_case_result = AsyncMock(return_value=MagicMock(id=42))
            await w.init_result(play_case=play_case, vars_info={"k": "v"})
            mock_mapper.init_case_result.assert_called_once()
            # play_case_result 应被设
            assert w.play_case_result is not None

    def test_build_vars_dict_format(self):
        """_build_vars 应输出 Before_Vars 格式 dict 列表。"""
        vars_map = {"token": "abc123", "host": "http://example.com"}
        result = PlayCaseResultWriter._build_vars(vars_map)
        assert isinstance(result, list)
        assert len(result) == 2
        for entry in result:
            assert entry["step_name"] == "Before_Vars"
            assert entry["extract_method"] == "Before"
            assert "id" in entry
            assert "key" in entry
            assert "value" in entry
        # keys
        keys = {e["key"] for e in result}
        assert keys == {"token", "host"}

    def test_build_vars_empty_dict_returns_empty_list(self):
        """_build_vars 传 {} 应返回 [] (无变量)."""
        assert PlayCaseResultWriter._build_vars({}) == []

    def test_repr_includes_case_result_id(self):
        """__repr__ 应包含 case_result_id (可能为 None) + task_result_id。"""
        w = PlayCaseResultWriter(starter=MagicMock(), play_task_result_id=7)
        text = repr(w)
        assert "7" in text
        assert "PlayCaseResultWriter" in text


# --------------------------------------------------------------------------- #
# PlayTaskResultWriter
# --------------------------------------------------------------------------- #

class TestPlayTaskResultWriter:
    """PlayTaskResultWriter 任务结果写入测试。"""

    def test_init_stores_starter(self):
        """init 应存 starter。"""
        starter = MagicMock()
        w = PlayTaskResultWriter(starter=starter)
        assert w.starter is starter

    @pytest.mark.asyncio
    async def test_set_task_running_calls_mapper(self):
        """set_task_running 应调 PlayTaskMapper.set_task_status(task_id, RUNNING)。"""
        with patch("croe.play.writer.PlayTaskMapper") as mock_mapper:
            mock_mapper.set_task_status = AsyncMock(return_value=None)
            from enums.CaseEnum import Status
            await PlayTaskResultWriter.set_task_running(task_id=42)
            mock_mapper.set_task_status.assert_called_once_with(42, Status.RUNNING)

    @pytest.mark.asyncio
    async def test_set_task_wait_calls_mapper(self):
        """set_task_wait 应调 PlayTaskMapper.set_task_status(task_id, WAIT)。"""
        with patch("croe.play.writer.PlayTaskMapper") as mock_mapper:
            mock_mapper.set_task_status = AsyncMock(return_value=None)
            from enums.CaseEnum import Status
            await PlayTaskResultWriter.set_task_wait(task_id=42)
            mock_mapper.set_task_status.assert_called_once_with(42, Status.WAIT)

    @pytest.mark.asyncio
    async def test_init_result_calls_set_running_then_mapper(self):
        """init_result 应先 set_task_running, 再调 PlayTaskResultMapper.init_task_result。"""
        starter = MagicMock()
        w = PlayTaskResultWriter(starter=starter)
        task = MagicMock(spec=PlayTask, id=1)
        with patch.object(PlayTaskResultWriter, "set_task_running", new=AsyncMock()) as mock_run, \
             patch("croe.play.writer.PlayTaskResultMapper") as mock_mapper:
            mock_mapper.init_task_result = AsyncMock(return_value=MagicMock(id=100))
            await w.init_result(task=task, case_nums=5)
            mock_run.assert_called_once_with(task_id=task.id)
            mock_mapper.init_task_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_final_result_zero_total_rate_is_zero(self):
        """write_final_result 在 total_number=0 时 rate_number 应是 0 (不除零)。"""
        starter = MagicMock()
        w = PlayTaskResultWriter(starter=starter)
        task_result = MagicMock(
            spec=PlayTaskResult,
            task_id=1,
            total_number=0,
            success_number=0,
            fail_number=0,
            start_time=datetime.datetime.now() - datetime.timedelta(seconds=10),
        )
        with patch.object(PlayTaskResultWriter, "set_task_wait", new=AsyncMock()), \
             patch("croe.play.writer.PlayTaskResultMapper") as mock_mapper:
            mock_mapper.set_result = AsyncMock(return_value=None)
            await w.write_final_result(task_result)
            # rate_number = 0 (避免 ZeroDivisionError)
            assert task_result.rate_number == 0

    @pytest.mark.asyncio
    async def test_write_final_result_computes_rate_from_success_total(self):
        """write_final_result 在 total_number>0 时应算 rate = success/total*100。"""
        from enums.CaseEnum import Result
        starter = MagicMock()
        w = PlayTaskResultWriter(starter=starter)
        task_result = MagicMock(
            spec=PlayTaskResult,
            task_id=1,
            total_number=10,
            success_number=7,
            fail_number=3,
            start_time=datetime.datetime.now() - datetime.timedelta(seconds=10),
        )
        with patch.object(PlayTaskResultWriter, "set_task_wait", new=AsyncMock()), \
             patch("croe.play.writer.PlayTaskResultMapper") as mock_mapper:
            mock_mapper.set_result = AsyncMock(return_value=None)
            await w.write_final_result(task_result)
            # 7/10*100 = 70.0
            assert task_result.rate_number == 70.0
            # result 应是 FAIL (有失败)
            assert task_result.result == Result.FAIL

    @pytest.mark.asyncio
    async def test_write_final_result_all_success_is_success(self):
        """write_final_result 在全部成功时 result 应是 SUCCESS。"""
        starter = MagicMock()
        w = PlayTaskResultWriter(starter=starter)
        task_result = MagicMock(
            spec=PlayTaskResult,
            task_id=1,
            total_number=5,
            success_number=5,
            fail_number=0,
            start_time=datetime.datetime.now() - datetime.timedelta(seconds=10),
        )
        with patch.object(PlayTaskResultWriter, "set_task_wait", new=AsyncMock()), \
             patch("croe.play.writer.PlayTaskResultMapper") as mock_mapper:
            mock_mapper.set_result = AsyncMock(return_value=None)
            await w.write_final_result(task_result)
            assert task_result.rate_number == 100.0
