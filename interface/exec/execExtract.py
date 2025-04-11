from typing import List, Mapping, Any, Dict, Callable
import re
from enums import InterfaceExtractTargetVariablesEnum
from httpx import Response

from utils import MyJsonPath, log


class ExecResponseExtract:
    """
    接口 响应提取
    """

    def __init__(self, response: Response = None):
        self.response = response
        self.variables = {}

    async def __call__(self, extracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        :param extracts:
        :return:
        """

        log.debug(f"extracts:{extracts}")
        handlers = {
            InterfaceExtractTargetVariablesEnum.ResponseJsonExtract: self._handle_response_json_extract,
            InterfaceExtractTargetVariablesEnum.ResponseHeaderExtract: self._handle_response_header_extract,
            InterfaceExtractTargetVariablesEnum.RequestCookieExtract: self._handle_request_cookie_extract,
            InterfaceExtractTargetVariablesEnum.ResponseTextExtract: self._handle_response_text_extract,
        }
        for extract in extracts:
            try:
                target = int(extract.get("target", 0))
                handler:Callable = handlers.get(target)
                if handler:
                    extract['value'] = await handler(extract)
                else:
                    log.warning(f"Unsupported Target: {target}")
            except KeyError as e:
                log.error(f"Missing key in extract: {e}")
            except Exception as e:
                log.error(f"Error processing extract: {e}")

        return extracts

    async def _handle_response_json_extract(self, extract: Dict[str, Any]) -> Any:
        """处理 ResponseJsonExtract 类型"""
        try:
            jp = MyJsonPath(jsonBody=self.response, expr=extract['value'])
            return await jp.value()
        except Exception as e:
            log.error(f"Failed to extract JSON value: {e}")
            return None

    async def _handle_response_header_extract(self, extract: Dict[str, Any]) -> Any:
        """处理 ResponseHeaderExtract 类型"""
        try:
            jp = MyJsonPath(jsonBody=dict(self.response.headers), expr=extract['value'])
            return await jp.value()
        except Exception as e:
            log.error(f"Failed to extract header value: {e}")
            return None

    async def _handle_request_cookie_extract(self, extract: Dict[str, Any]) -> Any:
        """处理 RequestCookieExtract 类型"""
        return self.response.request.headers.get("cookie", None)

    async def _handle_response_text_extract(self, extract: Dict[str, Any]) -> Any:
        """处理 ResponseTextExtract 类型"""
        try:
            match = re.search(extract['value'], self.response.text)
            return match.group(1) if match else None
        except Exception as e:
            log.error(f"Failed to extract text value: {e}")
            return None