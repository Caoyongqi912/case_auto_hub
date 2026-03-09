#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : assert_methods
# @Software: PyCharm
# @Desc:

from typing import Optional
from playwright.async_api import Locator, expect

from croe.a_manager.assert_manager import AssertResult
from utils import log
from ._base_method import BaseMethods
from croe.play.context import StepContext
from .result_types import StepExecutionResult, create_success_result, create_error_result


class AssertIsCheckedMethod(BaseMethods):
    """
    Assert that the element is checked.
    """
    method_name = "expect.to_be_checked"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:

        assert_result = AssertResult(
            assert_type=0,
            assert_key="-",
            assert_result=False,
            assert_actual=None,
            assert_expect=True,
        )
        try:
            expect(locator).to_be_checked()
            assert_result.assert_actual = True
            assert_result.assert_result = True
            return create_success_result(
                assert_data=assert_result,
            )
        except Exception as e:
            log.error(f"[AssertIsCheckedMethod] 断言失败: {e}")
            assert_result.assert_actual = False
            assert_result.assert_result = False
            return create_error_result(
                error_type="assertion_failed",
                message=f"[AssertIsCheckedMethod] 断言失败: 期望元素被选中, 实际未被选中",
                selector=context.method,
                assert_data=assert_result,
            )


class AssertIsDisabledMethod(BaseMethods):
    """
    Assert that the element is disabled.
    """
    method_name = "expect.to_be_disabled"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:

        assert_result = AssertResult(
            assert_type=0,
            assert_key="-",
            assert_result=False,
            assert_actual=None,
            assert_expect=True,
        )
        try:
            expect(locator).to_be_disabled()
            assert_result.assert_actual = True
            assert_result.assert_result = True
            return create_success_result(
                assert_data=assert_result,
            )
        except Exception as e:
            log.error(f"[AssertIsDisabledMethod] 断言失败: {e}")
            assert_result.assert_actual = False
            assert_result.assert_result = False
            return create_error_result(
                error_type="assertion_failed",
                message=f"[AssertIsDisabledMethod] 断言失败: 期望元素被禁用, 实际未被禁用",
                selector=context.method,
                assert_data=assert_result,
            )


class AssertIsEditableMethod(BaseMethods):
    """
    Assert that the element is editable.
    """
    method_name = "expect.to_be_editable"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:

        assert_result = AssertResult(
            assert_type=0,
            assert_key="-",
            assert_result=False,
            assert_actual=None,
            assert_expect=True,
        )
        try:
            expect(locator).to_be_editable()
            assert_result.assert_actual = True
            assert_result.assert_result = True
            return create_success_result(
                assert_data=assert_result,
            )
        except Exception as e:
            log.error(f"[AssertIsEditableMethod] 断言失败: {e}")
            assert_result.assert_actual = False
            assert_result.assert_result = False
            return create_error_result(
                error_type="assertion_failed",
                message=f"[AssertIsEditableMethod] 断言失败: 期望元素可编辑, 实际不可编辑",
                selector=context.method,
                assert_data=assert_result,
            )


class AssertIsEmptyMethod(BaseMethods):
    """
    Assert that the element is empty.
    """
    method_name = "expect.to_be_empty"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:

        assert_result = AssertResult(
            assert_type=0,
            assert_key="-",
            assert_result=False,
            assert_actual=None,
            assert_expect=True,
        )
        try:
            expect(locator).to_be_empty()
            assert_result.assert_actual = True
            assert_result.assert_result = True
            return create_success_result(
                assert_data=assert_result,
            )
        except Exception as e:
            log.error(f"[AssertIsEmptyMethod] 断言失败: {e}")
            assert_result.assert_actual = False
            assert_result.assert_result = False
            return create_error_result(
                error_type="assertion_failed",
                message=f"[AssertIsEmptyMethod] 断言失败: 期望元素为空, 实际不为空",
                selector=context.method,
                assert_data=assert_result,
            )


class AssertIsEnabledMethod(BaseMethods):
    """
    Assert that the element is enabled.
    """
    method_name = "expect.to_be_enabled"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:

        assert_result = AssertResult(
            assert_type=0,
            assert_key="-",
            assert_result=False,
            assert_actual=None,
            assert_expect=True,
        )
        try:
            expect(locator).to_be_enabled()
            assert_result.assert_actual = True
            assert_result.assert_result = True
            return create_success_result(
                assert_data=assert_result,
            )
        except Exception as e:
            log.error(f"[AssertIsEnabledMethod] 断言失败: {e}")
            assert_result.assert_actual = False
            assert_result.assert_result = False
            return create_error_result(
                error_type="assertion_failed",
                message=f"[AssertIsEnabledMethod] 断言失败: 期望元素可用, 实际不可用",
                selector=context.method,
                assert_data=assert_result,
            )


class AssertIsFocusedMethod(BaseMethods):
    """
    Assert that the element is focused.
    """
    method_name = "expect.to_be_focused"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:

        assert_result = AssertResult(
            assert_type=0,
            assert_key="-",
            assert_result=False,
            assert_actual=None,
            assert_expect=True,
        )
        try:
            expect(locator).to_be_focused()
            assert_result.assert_actual = True
            assert_result.assert_result = True
            return create_success_result(
                assert_data=assert_result,
            )
        except Exception as e:
            log.error(f"[AssertIsFocusedMethod] 断言失败: {e}")
            assert_result.assert_actual = False
            assert_result.assert_result = False
            return create_error_result(
                error_type="assertion_failed",
                message=f"[AssertIsFocusedMethod] 断言失败: 期望元素获得焦点, 实际未获得焦点",
                selector=context.method,
                assert_data=assert_result,
            )


class AssertIsHiddenMethod(BaseMethods):
    """
    Assert that the element is hidden.
    """
    method_name = "expect.to_be_hidden"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:

        assert_result = AssertResult(
            assert_type=0,
            assert_key="-",
            assert_result=False,
            assert_actual=None,
            assert_expect=True,
        )
        try:
            expect(locator).to_be_hidden()
            assert_result.assert_actual = True
            assert_result.assert_result = True
            return create_success_result(
                assert_data=assert_result,
            )
        except Exception as e:
            log.error(f"[AssertIsHiddenMethod] 断言失败: {e}")
            assert_result.assert_actual = False
            assert_result.assert_result = False
            return create_error_result(
                error_type="assertion_failed",
                message=f"[AssertIsHiddenMethod] 断言失败: 期望元素隐藏, 实际可见",
                selector=context.method,
                assert_data=assert_result,
            )


class AssertUrlTitle(BaseMethods):
    """
    Assert url title
    """
    method_name = "expect.url_title"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        expect_value = context.step.value.strip()

        assert_result = AssertResult(
            assert_type=0,
            assert_key="-",
            assert_result=False,
            assert_actual=None,
            assert_expect=expect_value,
        )
        url_title = ""
        try:
            url_title = await context.page.title()
            actual_value = url_title.strip()
            if actual_value != expect_value:
                raise AssertionError(f"Expected title '{expect_value}', but got '{actual_value}'")
            assert_result.assert_actual = actual_value
            assert_result.assert_result = True
            return create_success_result(
                assert_data=assert_result,
            )
        except Exception as e:
            log.error(f"[AssertUrlTitle] 断言失败: {e}")
            assert_result.assert_actual = url_title.strip() if url_title else None
            assert_result.assert_result = False
            return create_error_result(
                error_type="assertion_failed",
                message=f"[AssertUrlTitle] 断言失败: 期望 '{expect_value}', 实际 '{url_title.strip() if url_title else None}'",
                selector=context.method,
                assert_data=assert_result,
            )


__all__ = (
    "AssertIsCheckedMethod",
    "AssertIsDisabledMethod",
    "AssertIsEditableMethod",
    "AssertIsEmptyMethod",
    "AssertIsEnabledMethod",
    "AssertIsFocusedMethod",
    "AssertIsHiddenMethod",
    "AssertUrlTitle",
)
