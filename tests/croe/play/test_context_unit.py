"""
croe.play.context 三个 dataclass 单测覆盖

目标: 锁定 StepContext / StepContentContext / PlayExecutionContext 的
property 行为 (selector / value / page / targetId 等), 防止字段重命名
或 page_manager 处理改动后无察觉。

约定: 用真实 (未持久化) 的 SQLAlchemy Model 实例 + MagicMock starter/variable/page。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.model.base import User
from app.model.playUI import PlayCaseResult, PlayTaskResult
from app.model.playUI.playCase import PlayCase
from app.model.playUI.playStepContent import PlayStepContent
from app.model.playUI.playStep import PlayStepModel


def _make_user():
    user = User()
    user.id = 1
    user.uid = "u-1"
    user.username = "alice"
    return user


def _make_step(selector="css:#btn", locator="css", method="click", value="  hello  ", key="  k1  "):
    step = PlayStepModel()
    step.selector = selector
    step.locator = locator
    step.method = method
    step.value = value
    step.key = key
    return step


def _make_step_content(content_type=1, target_id=99):
    content = PlayStepContent()
    content.content_type = content_type
    content.target_id = target_id
    content.content_name = "step"
    return content


def _make_play_case(case_id=1):
    case = PlayCase()
    case.id = case_id
    case.title = "test case"
    return case


def _make_page_manager(page=None):
    pm = MagicMock()
    pm.current_page = page if page is not None else MagicMock(name="page")
    return pm


# --------------------------------------------------------------------------- #
# StepContext
# --------------------------------------------------------------------------- #


class TestStepContext:
    """StepContext: 单 step 执行的轻量上下文, 走 starter.send / variable_manager。"""

    def _build(self, **overrides):
        from croe.play.context import StepContext
        defaults = {
            "step": _make_step(),
            "starter": MagicMock(),
            "variable_manager": MagicMock(),
        }
        defaults.update(overrides)
        return StepContext(**defaults)

    def test_inherits_dataclass(self):
        """StepContext 是 dataclass (无 slots 也要支持 kw 构造)。"""
        from croe.play.context import StepContext
        import dataclasses
        assert dataclasses.is_dataclass(StepContext)

    def test_page_returns_page_manager_current_page(self):
        ctx = self._build(page_manager=_make_page_manager())
        assert ctx.page is not None
        assert ctx.page == ctx.page_manager.current_page

    def test_page_raises_when_no_page_manager(self):
        """无 page_manager 时, page 应抛 RuntimeError (业务约定: 必须初始化)。"""
        ctx = self._build(page_manager=None)
        with pytest.raises(RuntimeError, match="PageManager not initialized"):
            _ = ctx.page

    def test_selector_returns_step_selector(self):
        ctx = self._build()
        assert ctx.selector == "css:#btn"

    def test_locator_returns_step_locator(self):
        ctx = self._build()
        assert ctx.locator == "css"

    def test_locator_returns_none_when_step_locator_is_empty(self):
        """step.locator 为空字符串/falsy 时, property 应返回 None (不是空串)。"""
        step = _make_step(locator="")
        ctx = self._build(step=step)
        assert ctx.locator is None

    def test_method_returns_step_method(self):
        ctx = self._build()
        assert ctx.method == "click"

    def test_value_strips_whitespace(self):
        """value 带前后空格应被 strip 掉。"""
        ctx = self._build()
        assert ctx.value == "hello"

    def test_value_returns_none_when_empty(self):
        step = _make_step(value="")
        ctx = self._build(step=step)
        assert ctx.value is None

    def test_value_returns_none_when_none(self):
        step = _make_step(value=None)
        ctx = self._build(step=step)
        assert ctx.value is None

    def test_key_strips_whitespace(self):
        ctx = self._build()
        assert ctx.key == "k1"

    def test_key_returns_None_string_when_empty(self):
        """业务约定: key 为空时, 业务上用字符串 "None" 占位 (不是真 None)。"""
        step = _make_step(key="")
        ctx = self._build(step=step)
        assert ctx.key == "None"

    def test_key_returns_None_string_when_none(self):
        step = _make_step(key=None)
        ctx = self._build(step=step)
        assert ctx.key == "None"

    @pytest.mark.asyncio
    async def test_log_forwards_to_starter_send(self):
        ctx = self._build()
        ctx.starter.send = AsyncMock()
        await ctx.log("hello log")
        ctx.starter.send.assert_awaited_once_with("hello log")


# --------------------------------------------------------------------------- #
# StepContentContext
# --------------------------------------------------------------------------- #


class TestStepContentContext:
    """StepContentContext: 步骤内容执行上下文, 带 writer / case_result_writer。"""

    def _build(self, **overrides):
        from croe.play.context import StepContentContext
        defaults = {
            "index": 1,
            "play_step_content": _make_step_content(content_type=2, target_id=123),
            "play_step_result_writer": MagicMock(),
            "starter": MagicMock(),
            "variable_manager": MagicMock(),
        }
        defaults.update(overrides)
        return StepContentContext(**defaults)

    def test_inherits_dataclass(self):
        from croe.play.context import StepContentContext
        import dataclasses
        assert dataclasses.is_dataclass(StepContentContext)

    def test_index_preserved(self):
        ctx = self._build(index=5)
        assert ctx.index == 5

    def test_page_returns_page_manager_current_page(self):
        ctx = self._build(page_manager=_make_page_manager())
        assert ctx.page == ctx.page_manager.current_page

    def test_page_raises_when_no_page_manager(self):
        ctx = self._build(page_manager=None)
        with pytest.raises(RuntimeError, match="PageManager not initialized"):
            _ = ctx.page

    def test_targetId_returns_play_step_content_target_id(self):
        ctx = self._build()
        assert ctx.targetId == 123

    def test_targetId_none_when_target_id_is_none(self):
        content = _make_step_content(target_id=None)
        ctx = self._build(play_step_content=content)
        assert ctx.targetId is None

    def test_repr_includes_index_and_type(self):
        """__repr__ 格式: <StepContentContext step = {index}  type ={type} />"""
        ctx = self._build(index=7)
        text = repr(ctx)
        assert "7" in text
        assert "StepContentContext" in text

    def test_case_result_writer_optional(self):
        """play_case_result_writer 是 Optional, 允许 None。"""
        ctx = self._build(play_case_result_writer=None)
        assert ctx.play_case_result_writer is None

    def test_writers_attached(self):
        w1 = MagicMock(name="step_writer")
        w2 = MagicMock(name="case_writer")
        ctx = self._build(play_step_result_writer=w1, play_case_result_writer=w2)
        assert ctx.play_step_result_writer is w1
        assert ctx.play_case_result_writer is w2


# --------------------------------------------------------------------------- #
# PlayExecutionContext
# --------------------------------------------------------------------------- #


class TestPlayExecutionContext:
    """PlayExecutionContext: 用例级执行上下文, 串联 case + result + task_result。"""

    def _build(self, **overrides):
        from croe.play.context import PlayExecutionContext
        defaults = {
            "play_case": _make_play_case(case_id=10),
            "starter": MagicMock(),
        }
        defaults.update(overrides)
        return PlayExecutionContext(**defaults)

    def test_inherits_dataclass(self):
        from croe.play.context import PlayExecutionContext
        import dataclasses
        assert dataclasses.is_dataclass(PlayExecutionContext)

    def test_case_result_optional_defaults_none(self):
        """case_result / task_result 默认 None, 初始化后才填。"""
        ctx = self._build()
        assert ctx.case_result is None
        assert ctx.task_result is None

    def test_case_preserved(self):
        case = _make_play_case(case_id=88)
        ctx = self._build(play_case=case)
        assert ctx.play_case is case
        assert ctx.play_case.id == 88

    def test_case_result_can_be_attached(self):
        case_result = PlayCaseResult()
        case_result.id = 1
        ctx = self._build(case_result=case_result)
        assert ctx.case_result is case_result

    def test_task_result_can_be_attached(self):
        task_result = PlayTaskResult()
        task_result.id = 5
        ctx = self._build(task_result=task_result)
        assert ctx.task_result is task_result

    def test_starter_preserved(self):
        starter = MagicMock(name="starter")
        ctx = self._build(starter=starter)
        assert ctx.starter is starter


# --------------------------------------------------------------------------- #
# __all__ 导出
# --------------------------------------------------------------------------- #


class TestContextExports:
    """__all__ 导出契约。"""

    def test_all_contains_three_contexts(self):
        from croe.play import context
        assert "StepContext" in context.__all__
        assert "StepContentContext" in context.__all__
        assert "PlayExecutionContext" in context.__all__

    def test_classes_importable_from_module(self):
        from croe.play.context import StepContext, StepContentContext, PlayExecutionContext
        assert StepContext is not None
        assert StepContentContext is not None
        assert PlayExecutionContext is not None
