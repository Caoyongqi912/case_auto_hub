#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : assert_manager
# @Software: PyCharm
# @Desc:
from dataclasses import dataclass, asdict
import re
from enum import Enum

import httpx

from typing import List, Mapping, Any, Tuple, Dict, Optional
from json import JSONDecodeError
from app.schema.api.interfaceSchema import IAssert
from pydantic import BaseModel
from enums.CaseEnum import ExtraEnum, AssertTargetEnum
from utils import log, JsonExtract
from utils.assertsUtil import MyAsserts
from utils.transform import Transform


class ContentAssert(BaseModel):
    assert_key: str
    assert_value: str
    assert_type: int


class ExtractError(Enum):
    JSONPath_ERROR = "JSONPath extraction failed"
    JMESPATH_ERROR = "JMESPath extraction failed or invalid syntax"
    JSON_DECODE_ERROR = "Response is not valid JSON"


@dataclass
class AssertResult:
    assert_expect: Any  # 预期结果
    assert_result: bool  # 断言结果
    assert_type: int  # 断言类型
    assert_key: str  # 变量名
    assert_actual: Any = None  # 实际值


@dataclass
class AssertResponse:
    actual: Any
    result: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actual": self.actual,
            "result": self.result,
            "error": self.error
        }


class AssertManager:

    def __init__(self, response: Optional['httpx.Response'] = None, variables: Optional["Dict"] = None):
        self.variables = variables
        self.response = response

    @staticmethod
    def _error_result(actual: Any = None, error: str = None) -> AssertResponse:
        return AssertResponse(actual=actual, result=False, error=error)

    async def __call__(self, asserts_info: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量执行断言

        Args:
            asserts_info: 断言配置列表

        Returns:
            断言结果列表
        """
        if not asserts_info:
            return []

        asserts_result = []
        for assertion in asserts_info:
            _assert = IAssert(**assertion)
            log.info(_assert.model_dump())
            if not _assert.assert_switch:
                continue
            _assert_result = await self.invoke(_assert)
            asserts_result.append({**_assert.model_dump(), **_assert_result})
        return asserts_result

    async def assert_content_list(self, assert_list: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
        """
        批量断言

        Args:
            assert_list: 断言列表

        Returns:
            (断言结果列表, 是否全部成功)
        """
        assert_success = True
        assert_result_list = []
        for item in assert_list:
            assert_content = ContentAssert(**item)
            assert_result = await self.assert_content(assert_content)
            if not assert_result.assert_result:
                assert_success = False
            assert_result_list.append(asdict(assert_result))

        return assert_result_list, assert_success

    async def assert_content(self, content: ContentAssert) -> AssertResult:
        """
        步骤断言

        Args:
            content: 断言内容

        Returns:
            断言结果
        """
        assert_result = AssertResult(
            assert_expect=content.assert_value,
            assert_type=content.assert_type,
            assert_key=content.assert_key,
            assert_result=False
        )
        actual = self.variables.get(content.assert_key) if content.assert_key in self.variables else None
        assert_result.assert_actual = actual
        try:
            log.info(f"actual {type(actual)} {actual}")
            log.info(f"expect {type(content.assert_value)} {content.assert_value}")
            MyAsserts.option(
                assertOpt=content.assert_type,
                expect=content.assert_value,
                actual=actual
            )
            assert_result.assert_result = True
            return assert_result
        except AssertionError as e:
            log.error(e)
            assert_result.assert_result = False
            return assert_result

    async def invoke(self, assertInfo: IAssert) -> Dict[str, Any]:
        """
        断言执行

        Args:
            assertInfo: 断言目标

        Returns:
            断言结果字典
        """
        expect_value = await self.set_expect_value(assertInfo.assert_value)
        assertInfo.assert_value = expect_value
        match assertInfo.assert_target:
            case AssertTargetEnum.StatusCode:  # 状态码断言
                return await self.assert_status_code(assertInfo)
            case AssertTargetEnum.ResponseText:  # 文本断言
                return await self.assert_response_text(assertInfo)
            case AssertTargetEnum.ResponseBody:  # body断言
                return await self.assert_response_json(assertInfo)
            case AssertTargetEnum.ResponseHeader:  # header断言
                return await self.assert_response_header(assertInfo)
            case _:
                return self._error_result(error=f"Unknown assert target: {assertInfo.assert_target}").to_dict()

    async def assert_status_code(self, assertInfo: IAssert) -> Dict[str, Any]:
        """
        响应状态码断言

        Args:
            assertInfo: 断言信息

        Returns:
            断言结果
        """
        return await self.__assert(
            assertInfo.assert_opt,
            assertInfo.assert_value,
            self.response.status_code
        )

    async def assert_response_text(self, assertInfo: IAssert) -> Dict[str, Any]:
        """
        响应文本断言
        只支持正则提取
        Args:
            assertInfo: 断言信息
        Returns:
            断言结果
        """
        if assertInfo.assert_extract != ExtraEnum.RE or not assertInfo.assert_text:
            log.error(f"断言方法 {assertInfo.assert_extract} 不能对响应文本进行断言 或 断言语法为空！")
            return self._error_result(error="Text assertion requires RE extract type").to_dict()

        target = self.response.text
        match = re.search(assertInfo.assert_text, target)
        actual = match.group(1) if match else None
        return await self.__assert(assertInfo.assert_opt, assertInfo.assert_value, actual)

    async def assert_response_json(self, assertInfo: IAssert) -> Dict[str, Any]:
        """
        响应 JSON 断言

        Args:
            assertInfo: 断言信息
            支持 JSONPath 和 JMESPath 提取

        Returns:
            断言结果
        """
        if assertInfo.assert_extract not in [ExtraEnum.JMESPATH, ExtraEnum.JSONPATH] or not assertInfo.assert_text:
            log.error(f"assert_response_json {assertInfo.assert_extract} 不能对响应Json进行断言 或 断言语法为空！")
            return self._error_result(error="JSON assertion requires JSONPath or JMESPath extract type").to_dict()

        try:
            target = self.response.json()
            actual = await self.__json_extract(target, assertInfo.assert_text, assertInfo.assert_extract)
            if actual is None and assertInfo.assert_extract == ExtraEnum.JSONPATH:
                return self._error_result(error=ExtractError.JSONPath_ERROR.value).to_dict()
            return await self.__assert(assertInfo.assert_opt, assertInfo.assert_value, actual)
        except JSONDecodeError as e:
            log.warning(f"响应 JSON 解析失败: {e}")
            return self._error_result(error=ExtractError.JSON_DECODE_ERROR.value).to_dict()
        except ValueError as e:
            log.warning(f"响应格式错误: {e}")
            return self._error_result(error=str(e)).to_dict()

    async def assert_response_header(self, assertInfo: IAssert) -> Dict[str, Any]:
        """
        响应 Header 断言

        Args:
            assertInfo: 断言信息
            只支持 JSONPath 和 JMESPath 提取

        Returns:
            断言结果
        """
        if assertInfo.assert_extract not in [ExtraEnum.JMESPATH, ExtraEnum.JSONPATH] or not assertInfo.assert_text:
            log.error(f"assert_response_header {assertInfo.assert_extract} 不能对响应Header进行断言 或 断言语法为空！")
            return self._error_result(error="Header assertion requires JSONPath or JMESPath extract type").to_dict()

        try:
            target = dict(self.response.headers)
            log.info(f"assert_response_header= {target}")
            actual = await self.__json_extract(target, assertInfo.assert_text, assertInfo.assert_extract)
            if actual is None and assertInfo.assert_extract == ExtraEnum.JSONPATH:
                return self._error_result(error=ExtractError.JSONPath_ERROR.value).to_dict()
            return await self.__assert(assertInfo.assert_opt, assertInfo.assert_value, actual)
        except JSONDecodeError:
            log.warning(f"响应 {self.response.text} 非JSON、无法提取")
            return self._error_result(error=ExtractError.JSON_DECODE_ERROR.value).to_dict()

    @staticmethod
    async def __assert(assert_opt: int, expect: Any, actual: Any) -> Dict[str, Any]:
        """
        底层断言执行

        Args:
            assert_opt: 断言类型
            expect: 预期值
            actual: 实际值

        Returns:
            断言结果字典
        """
        try:
            MyAsserts.option(assert_opt, expect, actual)
            return AssertResponse(actual=actual, result=True).to_dict()
        except AssertionError as e:
            log.error(e)
            return AssertResponse(actual=actual, result=False, error=str(e)).to_dict()

    @staticmethod
    async def __json_extract(target: Any, assert_text: str, assert_extract: str) -> Any:
        """
        JSON 提取

        Args:
            target: 目标对象
            assert_text: 提取表达式
            assert_extract: 提取类型 (JSONPath/JMESPath)

        Returns:
            提取结果，失败时返回 None
        """
        jp = JsonExtract(target, assert_text)
        match assert_extract:
            case ExtraEnum.JSONPATH:
                return await jp.value()
            case ExtraEnum.JMESPATH:
                return jp.search()
            case _:
                return None

    async def set_expect_value(self, assert_value: str) -> Any:
        """
        变量替换

        Args:
            assert_value: 包含变量的断言值

        Returns:
            替换后的值
        """
        t = Transform(self.variables)
        return await t.transform_target(assert_value)
