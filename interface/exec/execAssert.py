#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/22# @Author : cyq# @File : execAssert# @Software: PyCharm# @Desc:from enums.CaseEnum import ExtraEnumfrom utils import MyLoguru, JsonExtractfrom utils.assertsUtil import MyAssertsfrom httpx import Responsefrom typing import List, Mapping, Anyimport refrom json import JSONDecodeErrorlog = MyLoguru().get_logger()class ExecAsserts:    """    执行断言    """    def __init__(self, response: Response = None):        self.response = response    async def __call__(self, assertsInfo: List[Mapping[str, Any]]):        """        [{'id': 1744352052647, 'desc': '测试', 'expect': 'text/html; charset=UTF-8', 'extraOpt': 're',         'assertOpt': '==', 'extraValue': 'content="(.*?)"', 'extraValueType': 'string'}]        """        log.debug(f"断言 {assertsInfo}")        order = ["string", "integer", "float", "bool", "object"]        asserts_info = sorted(assertsInfo, key=lambda x: order.index(x["extraValueType"]))        asserts_result = []        for ass in asserts_info:            _assert_result = await self.invoke(**ass)            asserts_result.append({**ass, **_assert_result})        return asserts_result    async def invoke(self, extraOpt: str, assertOpt: str, extraValue: str, extraValueType: str, expect: Any, **kwargs):        """        :param extraValue 提取语法        :param extraOpt   提取方式        :param assertOpt   断言方法        :param extraValueType 预期值类型        :param expect     预期值        """        _ = {}        actual = None        match extraOpt:            case ExtraEnum.JSONPATH:                try:                    _response = self.response.json()                    jp = JsonExtract(_response, extraValue)                    actual = await jp.value()                except JSONDecodeError:                    log.warning(f"响应 {self.response.text} 非JSON 、无法使用JSONPATH 提取")                    actual = None            case ExtraEnum.JMESPATH:                try:                    actual = self.response.json()                    jp = JsonExtract(actual, extraValue)                    actual = await jp.search()                except JSONDecodeError:                    log.warning(f"响应 {self.response.text} 非JSON 、无法使用JMESPATH 提取")                    actual = None            case ExtraEnum.RE:                match = re.search(extraValue, self.response.text)                actual = match.group(1) if match else None            case _:                pass        _['actual'] = actual        try:            MyAsserts.option(assertOpt, expect, actual, extraValueType)            _['result'] = True            return _        except AssertionError as e:            log.error(e)            _['result'] = False            return _