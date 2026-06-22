"""croe/play/executor/step_content_strategy/_base.py 单元测试覆盖"""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.model.playUI.PlayResult import PlayStepContentResult
from croe.play.context import StepContentContext
from croe.play.executor.play_method.result_types import StepExecutionResult
from croe.play.executor.step_content_strategy._base import StepBaseStrategy

# Helper: instantiate abstract class
class _TestStrategy(StepBaseStrategy):
    """Concrete subclass for testing abstract StepBaseStrategy."""

    async def execute(self, step_context):
        return True

# --------------------------------------------------------------------------- #
# StepBaseStrategy._build_content_result
# --------------------------------------------------------------------------- #

class TestBuildContentResult:
    """_build_content_result 测试。"""

    @pytest.mark.asyncio
    async def test_builds_basic_content_result(self):
        """基本字段应被设置: id / name / type / step / time / use_time。"""
        strategy = _TestStrategy()
        mock_pc = MagicMock(
            id=10,
            content_name="步骤1",
            content_desc="描述1",
            content_type=1,  # STEP_PLAY
        )
        ctx = MagicMock(
            spec=StepContentContext,
            index=1,
            play_step_content=mock_pc,
            starter=MagicMock(userId=1, username="admin"),
            page_manager=MagicMock(),
        )
        result = StepExecutionResult(success=True)
        start_time = datetime.datetime.now()
        cr = await strategy._build_content_result(
            result=result,
            start_time=start_time,
            step_context=ctx,
            ignore=False,
        )
        assert isinstance(cr, PlayStepContentResult)
        assert cr.content_step == 1
        assert cr.content_id == 10
        assert cr.content_name == "步骤1"
        assert cr.content_desc == "描述1"
        assert cr.content_type == 1
        assert cr.starter_id == 1
        assert cr.starter_name == "admin"
        assert cr.content_ignore_error is False
        assert cr.start_time == start_time
        assert cr.use_time  # 应有 use_time 字符串

    @pytest.mark.asyncio
    async def test_result_success_sets_content_result(self):
        """result.success=True 时 cr.content_result 应是 True。"""
        strategy = _TestStrategy()
        ctx = MagicMock(
            spec=StepContentContext,
            index=1,
            play_step_content=MagicMock(id=1, content_type=1),
            starter=MagicMock(userId=1, username="u"),
        )
        result = StepExecutionResult(success=True, message="成功信息")
        cr = await strategy._build_content_result(
            result=result,
            start_time=datetime.datetime.now(),
            step_context=ctx,
            ignore=False,
        )
        assert cr.content_result is True
        assert cr.content_message == "成功信息"

    @pytest.mark.asyncio
    async def test_result_failure_sets_content_result_false(self):
        """result.success=False 时 cr.content_result 应是 False。

        用 error_type='interaction_failed' 跳过截图路径 (避免 mock page.screenshot)。
        """
        strategy = _TestStrategy()
        ctx = MagicMock(
            spec=StepContentContext,
            index=1,
            play_step_content=MagicMock(id=1, content_type=1),
            starter=MagicMock(userId=1, username="u"),
        )
        result = StepExecutionResult(success=False, message="失败信息", error_type="interaction_failed")
        cr = await strategy._build_content_result(
            result=result,
            start_time=datetime.datetime.now(),
            step_context=ctx,
            ignore=False,
        )
        assert cr.content_result is False
        assert cr.content_message == "失败信息"

    @pytest.mark.asyncio
    async def test_assert_data_set_when_present(self):
        """result.assert_data 存在时应写到 cr.content_asserts。

        用 error_type='interaction_failed' 跳过截图路径。
        """
        strategy = _TestStrategy()
        ctx = MagicMock(
            spec=StepContentContext,
            index=1,
            play_step_content=MagicMock(id=1, content_type=1),
            starter=MagicMock(userId=1, username="u"),
        )
        assert_data = [{"key": "status", "expected": 200, "actual": 500}]
        result = StepExecutionResult(success=False, assert_data=assert_data, error_type="interaction_failed")
        cr = await strategy._build_content_result(
            result=result,
            start_time=datetime.datetime.now(),
            step_context=ctx,
        )
        assert cr.content_asserts == assert_data

    @pytest.mark.asyncio
    async def test_extract_data_set_when_present(self):
        """result.extract_data 存在时应写到 cr.extracts。"""
        strategy = _TestStrategy()
        ctx = MagicMock(
            spec=StepContentContext,
            index=1,
            play_step_content=MagicMock(id=1, content_type=1),
            starter=MagicMock(userId=1, username="u"),
        )
        extract_data = [{"key": "user_id", "value": "123"}]
        result = StepExecutionResult(success=True, extract_data=extract_data)
        cr = await strategy._build_content_result(
            result=result,
            start_time=datetime.datetime.now(),
            step_context=ctx,
        )
        assert cr.extracts == extract_data

    @pytest.mark.asyncio
    async def test_ignore_true_sets_content_ignore_error(self):
        """ignore=True 时 cr.content_ignore_error 应是 True。

        用 error_type='interaction_failed' 跳过截图路径。
        """
        strategy = _TestStrategy()
        ctx = MagicMock(
            spec=StepContentContext,
            index=1,
            play_step_content=MagicMock(id=1, content_type=1),
            starter=MagicMock(userId=1, username="u"),
        )
        result = StepExecutionResult(success=False, error_type="interaction_failed")
        cr = await strategy._build_content_result(
            result=result,
            start_time=datetime.datetime.now(),
            step_context=ctx,
            ignore=True,
        )
        assert cr.content_ignore_error is True
        # content_result 应是 False (失败)
        assert cr.content_result is False

    @pytest.mark.asyncio
    async def test_target_id_set_when_present(self):
        """result.content_target_result_id 应被设到 cr.content_target_result_id。"""
        strategy = _TestStrategy()
        ctx = MagicMock(
            spec=StepContentContext,
            index=1,
            play_step_content=MagicMock(id=1, content_type=1),
            starter=MagicMock(userId=1, username="u"),
        )
        result = StepExecutionResult(success=True, content_target_result_id=99)
        cr = await strategy._build_content_result(
            result=result,
            start_time=datetime.datetime.now(),
            step_context=ctx,
        )
        assert cr.content_target_result_id == 99

# --------------------------------------------------------------------------- #
# StepBaseStrategy.write_result
# --------------------------------------------------------------------------- #

class TestWriteResult:
    """write_result 测试。"""

    @pytest.mark.asyncio
    async def test_write_result_calls_add_content_result(self):
        """write_result 应 add_content_result 到 step_result_writer。"""
        strategy = _TestStrategy()
        ctx = MagicMock()
        ctx.index = 1
        ctx.play_step_content = MagicMock(id=1, content_type=1)
        ctx.starter = MagicMock(userId=1, username="u")
        ctx.play_step_result_writer = MagicMock()
        ctx.play_step_result_writer.add_content_result = AsyncMock()
        ctx.play_case_result_writer = MagicMock()
        ctx.play_case_result_writer.set_error_step_info = AsyncMock()
        result = StepExecutionResult(success=True)
        await strategy.write_result(
            result=result,
            start_time=datetime.datetime.now(),
            step_context=ctx,
        )
        ctx.play_step_result_writer.add_content_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_result_failure_writes_error_info_p_r5(self):
        """步骤失败时不管 ignore, 都应 set_error_step_info 到 case_result。"""
        strategy = _TestStrategy()
        ctx = MagicMock()
        ctx.index = 1
        ctx.play_step_content = MagicMock(id=1, content_type=1)
        ctx.starter = MagicMock(userId=1, username="u")
        ctx.play_step_result_writer = MagicMock()
        ctx.play_step_result_writer.add_content_result = AsyncMock()
        ctx.play_case_result_writer = MagicMock()
        ctx.play_case_result_writer.set_error_step_info = AsyncMock()
        result = StepExecutionResult(success=False, message="失败", error_type="interaction_failed")
        # ignore=True 也写错误信息
        await strategy.write_result(
            result=result,
            start_time=datetime.datetime.now(),
            step_context=ctx,
            ignore=True,
        )
        # set_error_step_info 应被调
        ctx.play_case_result_writer.set_error_step_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_result_success_does_not_write_error_info(self):
        """步骤成功时不应 set_error_step_info (没错误信息可写)。"""
        strategy = _TestStrategy()
        ctx = MagicMock()
        ctx.index = 1
        ctx.play_step_content = MagicMock(id=1, content_type=1)
        ctx.starter = MagicMock(userId=1, username="u")
        ctx.play_step_result_writer = MagicMock()
        ctx.play_step_result_writer.add_content_result = AsyncMock()
        ctx.play_case_result_writer = MagicMock()
        ctx.play_case_result_writer.set_error_step_info = AsyncMock()
        result = StepExecutionResult(success=True)
        await strategy.write_result(
            result=result,
            start_time=datetime.datetime.now(),
            step_context=ctx,
        )
        ctx.play_case_result_writer.set_error_step_info.assert_not_called()

# --------------------------------------------------------------------------- #
# StepBaseStrategy.write_child_result
# --------------------------------------------------------------------------- #

class TestWriteChildResult:
    """write_child_result 测试。"""

    @pytest.mark.asyncio
    async def test_write_child_calls_add_child_content_result(self):
        """write_child_result 应 add_child_content_result (而不是 add_content_result)。"""
        strategy = _TestStrategy()
        ctx = MagicMock()
        ctx.index = 1
        ctx.play_step_content = MagicMock(id=1, content_type=1)
        ctx.starter = MagicMock(userId=1, username="u")
        ctx.play_step_result_writer = MagicMock()
        ctx.play_step_result_writer.add_child_content_result = AsyncMock()
        ctx.play_step_result_writer.add_content_result = AsyncMock()
        ctx.play_case_result_writer = MagicMock()
        ctx.play_case_result_writer.set_error_step_info = AsyncMock()
        result = StepExecutionResult(success=True)
        await strategy.write_child_result(
            parent_index=1,
            result=result,
            start_time=datetime.datetime.now(),
            step_context=ctx,
        )
        ctx.play_step_result_writer.add_child_content_result.assert_called_once()
        ctx.play_step_result_writer.add_content_result.assert_not_called()
