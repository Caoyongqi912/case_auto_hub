#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : assert_methods
# @Software: PyCharm
# @Desc:

import re
from typing import  Optional

from playwright.async_api import Locator, expect

from utils import GenerateTools, log
from ._base_method import BaseMethods
from croe.play.context import StepContext
from .result_types import  create_assert_info, StepExecutionResult


class AssertIsCheckedMethod(BaseMethods):
    """
    Assert that the element is checked.
    """
    method_name = "expect.to_be_checked"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        assert_info = create_assert_info(
            assert_name=context.step.name,
            assert_opt="=",
            assert_expect=True,
            assert_actual=None,
            assert_result=False,
            id=GenerateTools.getTime(3),
            desc=context.step.description,
            type="UI",
            assert_script=context.step.method,
        )
        try:
            expect(locator).to_be_checked()
            assert_info["assert_actual"] = True
            assert_info["assert_result"] = True
            return True, assert_info
        except Exception as e:
            log.error(f"[AssertIsCheckedMethod] execute error: {e}")
            assert_info["assert_actual"] = False
            return False, assert_info


class AssertIsDisabledMethod(BaseMethods):
    """
    Assert that the element is disabled.
    """
    method_name = "expect.to_be_disabled"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        assert_info = create_assert_info(
            assert_name=context.step.name,
            assert_opt="=",
            assert_expect=True,
            assert_actual=None,
            assert_result=False,
            id=GenerateTools.getTime(3),
            desc=context.step.description,
            type="UI",
            assert_script=context.step.method,
        )
        try:
            expect(locator).to_be_disabled()
            assert_info["assert_actual"] = True
            assert_info["assert_result"] = True
            return True, assert_info
        except Exception as e:
            log.error(f"[AssertIsDisabledMethod] execute error: {e}")
            assert_info["assert_actual"] = await get_error_value(e)
            return False, assert_info


class AssertIsEditableMethod(BaseMethods):
    """
    Assert that the element is editable.
    """
    method_name = "expect.to_be_editable"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        assert_info = create_assert_info(
            assert_name=context.step.name,
            assert_opt="=",
            assert_expect=True,
            assert_actual=None,
            assert_result=False,
            id=GenerateTools.getTime(3),
            desc=context.step.description,
            type="UI",
            assert_script=context.step.method,
        )
        try:
            expect(locator).to_be_editable()
            assert_info["assert_actual"] = True
            assert_info["assert_result"] = True
            return True, assert_info
        except Exception as e:
            log.error(f"[AssertIsEditableMethod] execute error: {e}")
            assert_info["assert_actual"] = await get_error_value(e)
            return False, assert_info


class AssertIsEmptyMethod(BaseMethods):
    """
    Assert that the element is empty.
    """
    method_name = "expect.to_be_empty"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        assert_info = create_assert_info(
            assert_name=context.step.name,
            assert_opt="=",
            assert_expect=True,
            assert_actual=None,
            assert_result=False,
            id=GenerateTools.getTime(3),
            desc=context.step.description,
            type="UI",
            assert_script=context.step.method,
        )
        try:
            expect(locator).to_be_empty()
            assert_info["assert_actual"] = True
            assert_info["assert_result"] = True
            return True, assert_info
        except Exception as e:
            log.error(f"[AssertIsEmptyMethod] execute error: {e}")
            assert_info["assert_actual"] = await get_error_value(e)
            return False, assert_info


class AssertIsEnabledMethod(BaseMethods):
    """
    Assert that the element is enabled.
    """
    method_name = "expect.to_be_enabled"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        assert_info = create_assert_info(
            assert_name=context.step.name,
            assert_opt="=",
            assert_expect=True,
            assert_actual=None,
            assert_result=False,
            id=GenerateTools.getTime(3),
            desc=context.step.description,
            type="UI",
            assert_script=context.step.method,
        )
        try:
            expect(locator).to_be_enabled()
            assert_info["assert_actual"] = True
            assert_info["assert_result"] = True
            return True, assert_info
        except Exception as e:
            log.error(f"[AssertIsEnabledMethod] execute error: {e}")
            assert_info["assert_actual"] = await get_error_value(e)
            return False, assert_info


class AssertIsFocusedMethod(BaseMethods):
    """
    Assert that the element is focused.
    """
    method_name = "expect.to_be_focused"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        assert_info = create_assert_info(
            assert_name=context.step.name,
            assert_opt="=",
            assert_expect=True,
            assert_actual=None,
            assert_result=False,
            id=GenerateTools.getTime(3),
            desc=context.step.description,
            type="UI",
            assert_script=context.step.method,
        )
        try:
            expect(locator).to_be_focused()
            assert_info["assert_actual"] = True
            assert_info["assert_result"] = True
            return True, assert_info
        except Exception as e:
            log.error(f"[AssertIsFocusedMethod] execute error: {e}")
            assert_info["assert_actual"] = await get_error_value(e)
            return False, assert_info


class AssertIsHiddenMethod(BaseMethods):
    """
    Assert that the element is hidden.
    """
    method_name = "expect.to_be_hidden"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        assert_info = create_assert_info(
            assert_name=context.step.name,
            assert_opt="=",
            assert_expect=True,
            assert_actual=None,
            assert_result=False,
            id=GenerateTools.getTime(3),
            desc=context.step.description,
            type="UI",
            assert_script=context.step.method,
        )
        try:
            expect(locator).to_be_hidden()
            assert_info["assert_actual"] = True
            assert_info["assert_result"] = True
            return True, assert_info
        except Exception as e:
            log.error(f"[AssertIsHiddenMethod] execute error: {e}")
            assert_info["assert_actual"] = await get_error_value(e)
            return False, assert_info


class AssertUrlTitle(BaseMethods):
    """
    Assert url title
    """
    method_name = "expect.url_title"

    async def execute(self, context: StepContext, locator: Optional[Locator] = None) -> StepExecutionResult:
        expect_value = context.step.value.strip()
        assert_info = create_assert_info(
            assert_name=context.step.name,
            assert_opt="=",
            assert_expect=expect_value,
            assert_actual=None,
            assert_result=False,
            id=GenerateTools.getTime(3),
            desc=context.step.description,
            type="UI",
            assert_script=context.step.method,
        )
        url_title = None
        try:
            url_title = await context.page.title()
            actual_value = url_title.strip()
            assert actual_value == expect_value
            assert_info["assert_actual"] = actual_value
            assert_info["assert_result"] = True
            return True, assert_info
        except Exception as e:
            log.error(f"[AssertUrlTitle] execute error: {e}")
            assert_info["assert_actual"] = url_title.strip() if url_title else None
            return False, assert_info


async def get_error_value(e: Exception):
    """
    Extract actual value from assertion error message
    """
    err = str(e)

    # 尝试提取 Playwright 断言错误中的实际值
    if "Actual value:" in err:
        pattern = r"Actual value:\s*(.*?)\s*(?:Call log:|$)"
        match = re.search(pattern, err, re.DOTALL)
        if match:
            return match.group(1).strip()

    # 尝试提取其他格式的错误信息
    if "Expected:" in err and "Received:" in err:
        pattern = r"Received:\s*(.*?)(?:\n|$)"
        match = re.search(pattern, err)
        if match:
            return match.group(1).strip()

    # 返回完整错误信息而不是空字符串
    return str(e)[:200]  # 限制长度避免过长


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
