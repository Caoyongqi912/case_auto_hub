import json
from typing import List, Mapping, Any, Dict
from enums import InterfaceExtractTargetVariablesEnum
from httpx import Response

from utils import MyJsonPath, log


class ExecResponseExtract:

    def __init__(self, response: Response = None):
        self.response = response
        self.variables = {}

    async def __call__(self, extracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        :param extracts:
        :return:
        """
        for extract in extracts:
            match int(extract[InterfaceExtractTargetVariablesEnum.Target]):
                case InterfaceExtractTargetVariablesEnum.ResponseJsonExtract:
                    jp = MyJsonPath(jsonBody=self.response.json(),
                                    expr=extract['value'])
                    value = await jp.value()
                    extract['value'] = value
                case int(InterfaceExtractTargetVariablesEnum.ResponseHeaderExtract):
                    jp = MyJsonPath(jsonBody=dict(self.response.headers),
                                    expr=extract['value'])
                    value = await jp.value()
                    extract['value'] = value
                case int(InterfaceExtractTargetVariablesEnum.RequestCookieExtract):
                    #
                    log.error(f'暂不支持 ={self.response.request.headers}')
                    log.error(f'暂不支持 ={self.response.cookies}')
                    # jp = MyJsonPath(jsonBody=json.load(self.response.cookies),
                    #                 expr=extract['value'])
                    # value = await jp.value()
                    extract['value'] = self.response.request.headers.get("cookie", None)
                case int(InterfaceExtractTargetVariablesEnum.ResponseTextExtract):
                    """正则"""
                    import re
                    text = self.response.text
                    match = re.search(extract['value'], text)
                    if match:
                        extract['value'] = match.group(1)
                    else:
                        extract['value'] = None
                case _:
                    continue
        return extracts
