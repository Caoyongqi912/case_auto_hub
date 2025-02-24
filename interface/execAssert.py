#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/22# @Author : cyq# @File : execAssert# @Software: PyCharm# @Desc:import jsonfrom json import JSONDecodeErrorfrom typing import Any, List, Mappingfrom utils import MyLoguru, MyJsonPathfrom utils.assertsUtil import MyAssertsfrom httpx import Responselog = MyLoguru().get_logger()class ExtraOpt:    JSONPATH = "jsonpath"    RE = "re"class ExecAsserts:    """    执行断言    """    def __init__(self, response: Response = None):        self.response = response    async def __call__(self, assertsInfo: List[Mapping[str, Any]]):        order = ["string", "integer", "float", "bool", "object"]        asserts_info = sorted(assertsInfo, key=lambda x: order.index(x["extraValueType"]))        asserts_result = []        for ass in asserts_info:            _assert_result = await self.invoke(**ass)            asserts_result.append({**ass, **_assert_result})        return asserts_result    async def invoke(self, extraOpt: str, assertOpt: str, extraValue: str, extraValueType: str, expect: Any, **kw):        """        :param extraValue 提取语法        :param extraOpt   提取方式        :param assertOpt   断言方法        :param extraValueType 预期值类型        :param expect     预期值        """        _ = {}        actual = None        match extraOpt:            case ExtraOpt.JSONPATH:                try:                    _response = self.response.json()                    jp = MyJsonPath(_response, extraValue)                    actual = await jp.value()                    log.debug(f"actual ={actual}")                except JSONDecodeError:                    log.warning(f"响应 {self.response.text} 非JSON 、无法使用JSONPATH 提取")                    actual = None            case ExtraOpt.RE:                pass            case _:                pass        _['actual'] = actual        try:            MyAsserts().option(assertOpt, expect, actual, extraValueType)            _['result'] = True            return _        except AssertionError as e:            log.error(e)            _['result'] = False            return _    @staticmethod    def assertEqual(expect: Any, actual: Any):        """        校验相等        :param expect: 预期值        :param actual: 实际值        :assert expect == actual        """        assert expect == actual, f"expect:{expect} != actual:{actual}"    @staticmethod    def assertUnEqual(expect: Any, actual: Any):        """        校验不相等        :param expect:        :param actual:        :return:expect != actual        """        assert expect != actual, f"expect:{expect} == actual:{actual}"    @staticmethod    def assertIn(expect: Any, actual: Any):        """        校验包含        :param expect:        :param actual:        :return:        """        assert expect in actual, f"expect:{expect} not in actual:{actual}"    @staticmethod    def assertNotIn(expect: Any, actual: Any):        """        校验不包含        :param expect:        :param actual:        :return:        """        assert expect not in actual, f"expect:{expect} in actual:{actual}"    @staticmethod    def assertGreater(expect: Any, actual: Any):        """        校验大于        :param expect:        :param actual:        :return:        """        assert int(expect) > int(actual), f"expect:{expect} < actual:{actual}"    @staticmethod    def assertLess(expect: Any, actual: Any):        """        校验大于        :param expect:        :param actual:        :return:        """        assert expect < actual, f"expect:{expect} > actual:{actual}"    @staticmethod    def assertEqualGreater(expect: Any, actual: Any):        """        校验大于等于        :param expect:        :param actual:        :return:        """        assert expect >= actual, f"expect:{expect} <= actual:{actual}"    @staticmethod    def assertEqualLess(expect: Any, actual: Any):        """        校验小于等于        :param expect:        :param actual:        :return:        """        assert expect <= actual, f"expect:{expect} >= actual:{actual}"