#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/7/23
# @Author : cyq
# @File : JsonExtract
# @Software: PyCharm
# @Desc:

import jmespath
from typing import Any
from jsonpath import search as JsonPathSearch
from httpx import Response
from json import JSONDecodeError
from ._myLoguru import MyLoguru

log = MyLoguru().get_logger()


class JsonExtract:
    """
    json 提取

    jsonpath
    jmespath
    """

    def __init__(self, jsonBody: Response | dict | list[dict[str, Any]], expr: str):
        """
        :param jsonBody Response.json
        :param expr
        """
        if isinstance(jsonBody, Response):
            try:
                self.jsonBody = jsonBody.json()
            except JSONDecodeError as e:
                log.error(f" JsonExtract jsonpath解析失败:{e}")
                self.jsonBody = {}
        else:
            self.jsonBody = jsonBody
        self.endStr = None
        self.expr = self.handel_expr(expr)

    def search(self):
        """
        jmespath 解析
        :return:
        """
        return jmespath.search(self.expr, self.jsonBody)

    async def value(self) -> Any:
        """
        jsonpath 解析

        Returns:
            提取的值，未匹配到返回 None
        """
        try:
            log.debug(f"expr {self.expr}")
            log.debug(f"jsonBody {self.jsonBody}")
            result = JsonPathSearch(self.expr, self.jsonBody)
            if result is None:
                return None

            if isinstance(result, list):
                if not result:
                    return None
                value = result[0]
            else:
                value = result

            if self.endStr:
                return self.funcMap(value)
            return value
        except JSONDecodeError as e:
            raise e

    def regex(self) -> Any:
        """
        正则表达式提取

        使用正则从文本中提取值

        Returns:
            匹配的值，未匹配到返回 None
        """
        import re

        if not self.expr or not self.jsonBody:
            return None

        pattern = re.compile(self.expr)
        match = pattern.search(str(self.jsonBody))

        if match:
            if match.groups():
                return match.group(1)
            return match.group(0)
        return None

    def handel_expr(self, expr: str) -> str:
        """

        """
        expr = expr.strip()
        if expr.endswith("()"):
            self.endStr = expr.split(".")[-1]
            new = expr.replace("." + self.endStr, "")
            return new
        return expr

    def funcMap(self, data: Any) -> Any:
        """
        jsonpath 提取后的后处理函数

        支持：length() 返回长度

        Args:
            data: 提取的原始值

        Returns:
            处理后的值
        """
        func_map = {
            "length()": len
        }
        func = func_map.get(self.endStr)
        if func is not None:
            if data is not None:
                return func(data)
        return data
