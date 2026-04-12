#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : extract_manager
# @Software: PyCharm
# @Desc: 变量提取管理器模块

import re
from typing import List, Dict, Any, Callable, Optional, TYPE_CHECKING

from httpx import Response

from enums import ExtractTargetVariablesEnum
from enums.CaseEnum import ExtraEnum
from utils import JsonExtract, log

if TYPE_CHECKING:
    pass


class ExtractManager:
    """接口响应变量提取管理器"""

    def __init__(self, response: Optional[Response] = None) -> None:
        """
        初始化提取管理器

        Args:
            response: HTTP响应对象
        """
        self.response = response
        self.variables = {}

    async def __call__(
        self,
        extracts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        执行变量提取

        Args:
            extracts: 提取配置列表

        Returns:
            提取结果列表
        """
        handlers: Dict[int, Callable] = {
            ExtractTargetVariablesEnum.ResponseJsonExtract:
                self._handle_response_json_extract,
            ExtractTargetVariablesEnum.ResponseHeaderExtract:
                self._handle_response_header_extract,
            ExtractTargetVariablesEnum.RequestCookieExtract:
                self._handle_request_cookie_extract,
            ExtractTargetVariablesEnum.ResponseTextExtract:
                self._handle_response_text_extract,
        }

        for extract in extracts:
            try:
                target = int(extract.get("target", 0))
                handler: Optional[Callable] = handlers.get(target)

                if handler:
                    extract['value'] = await handler(extract)
                else:
                    log.warning(f"Unsupported Target: {target}")

            except KeyError as e:
                log.error(f"Missing key in extract: {e}")
            except Exception as e:
                log.error(f"Error processing extract: {e}")

        return extracts

    async def _handle_response_json_extract(
        self,
        extract: Dict[str, Any]
    ) -> Any:
        """
        处理响应JSON提取

        Args:
            extract: 提取配置

        Returns:
            提取的值
        """
        opt = extract.get("extraOpt", ExtraEnum.JSONPATH)

        try:
            jp = JsonExtract(
                jsonBody=self.response,
                expr=extract['value']
            )

            match opt:
                case ExtraEnum.JMESPATH:
                    return jp.jmespath()
                case ExtraEnum.JSONPATH:
                    return jp.jsonpath()
                case ExtraEnum.REGEX:
                    return jp.regex()
                case _:
                    log.warning(f"Unsupported extract option: {opt}")
                    return None

        except Exception as e:
            log.error(f"JSON提取失败: {e}")
            return None

    async def _handle_response_header_extract(
        self,
        extract: Dict[str, Any]
    ) -> Optional[str]:
        """
        处理响应头提取

        Args:
            extract: 提取配置

        Returns:
            提取的响应头值
        """
        header_name = extract.get('value')

        if not header_name:
            log.error("Missing header name in extract config")
            return None

        try:
            return self.response.headers.get(header_name)
        except Exception as e:
            log.error(f"响应头提取失败: {e}")
            return None

    async def _handle_request_cookie_extract(
        self,
        extract: Dict[str, Any]
    ) -> Optional[str]:
        """
        处理请求Cookie提取

        Args:
            extract: 提取配置

        Returns:
            提取的Cookie值
        """
        cookie_name = extract.get('value')

        if not cookie_name:
            log.error("Missing cookie name in extract config")
            return None

        try:
            cookies = self.response.request.cookies
            return cookies.get(cookie_name)
        except Exception as e:
            log.error(f"Cookie提取失败: {e}")
            return None

    async def _handle_response_text_extract(
        self,
        extract: Dict[str, Any]
    ) -> Optional[str]:
        """
        处理响应文本提取（正则表达式）

        Args:
            extract: 提取配置

        Returns:
            提取的文本
        """
        pattern = extract.get('value')

        if not pattern:
            log.error("Missing pattern in extract config")
            return None

        try:
            text = self.response.text
            match = re.search(pattern, text)

            if match:
                return match.group(1) if match.groups() else match.group(0)

            return None
        except Exception as e:
            log.error(f"文本提取失败: {e}")
            return None
