import asyncio
import json
from json import JSONDecodeError
from typing import List, Dict, Any

from fastapi import UploadFile
from enums import InterfaceUploadEnum
from utils import MyLoguru

log = MyLoguru().get_logger()


class FileReader:


    @staticmethod
    async def readUploadFile(v: str, file: UploadFile):

        match v:
            case InterfaceUploadEnum.YApi:
                return await FileReader._yapi(file)
            case InterfaceUploadEnum.PostMan:
                pass
            case InterfaceUploadEnum.Swagger:
                pass
            case InterfaceUploadEnum.ApiPost:
                return await FileReader._apipost(file)

    @staticmethod
    async def _apipost(file: UploadFile):
        data = json.loads(await file.read())
        post_data = {
            "module": data.get("name"),
            "data": []
        }
        apis = data.get("apis")
        if apis:
            for api in apis:
                if api.get("target_type") != "api":
                    continue
                else:
                    post_data['data'].append(await FileReader._get_apipost_data(api))
        return [post_data]
    @staticmethod
    async def _get_apipost_data(data: Dict[str, Any]):
        request_info = {
            'name': data.get("name"),
            'method': data.get("method"),
            'url': data.get("url"),
            'description': data.get("description", ""),
        }
        request = data.get("request")
        if request:
            headers: List[Dict[str, Any]] = request.get("header").get("parameter")
            if headers:
                request_info['headers'] = [
                    {
                        'id': header.get('param_id'),
                        'key': header.get('key'),
                        'value': header.get('value'),
                        'desc': header.get('description'),
                    }
                    for header in headers
                ]
            query: List[Dict[str, Any]] = request.get("query").get("parameter")
            if query:
                request_info['params'] = [
                    {
                        'id': q.get('param_id'),
                        'key': q.get('key'),
                        'value': q.get('value'),
                        'desc': q.get('description'),
                    }
                    for q in query
                ]

            mode = request.get("body").get("mode")
            if mode == "json":
                request_info['body_type'] = 1
                try:
                    request_info['body'] = json.loads(request.get("body").get("raw"))
                except JSONDecodeError:
                    request_info['body'] = None
            elif mode == "form-data":
                request_info['body_type'] = 1
            else:
                request_info['body_type'] = 0

        return request_info
    @staticmethod
    async def _yapi(file: UploadFile) -> List[Dict[str, Any]]:
        """
        解析 YAPI 导出的文件数据，并转换为结构化数据。

        :param file: 上传的文件对象
        :return: 解析后的 YAPI 数据列表
        """
        data = json.loads(await file.read())
        yapi_data = []

        for item in data:
            module_data = {
                'module': item.get("name"),
                'data': []
            }

            item_list = item.get('list', [])
            if item_list:
                # 并发处理每个接口的数据
                module_data['data'] = await asyncio.gather(
                    *(FileReader._get_yapi_data(api_data) for api_data in item_list)
                )

            yapi_data.append(module_data)

        return yapi_data

    @staticmethod
    async def _get_yapi_data(api_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析单个 API 数据，提取请求信息。

        :param api_data: 单个 API 的原始数据
        :return: 解析后的请求信息
        """
        request_info = {
            'name': api_data.get("title"),
            'method': api_data.get("method"),
            'url': api_data.get("path"),
            'params': api_data.get("req_params", []),
            'headers': api_data.get("req_headers", []),
            'description': api_data.get("desc", ""),
        }

        # 处理请求头
        if api_data.get('req_headers'):
            request_info['headers'] = [
                {
                    'id': header.get('_id'),
                    'key': header.get('name'),
                    'value': header.get('value'),
                    'desc': header.get('desc'),
                }
                for header in api_data.get("req_headers")
            ]

        # 处理查询参数
        if api_data.get('req_query'):
            request_info['params'] = [
                {
                    'id': query.get('_id'),
                    'key': query.get('name'),
                    'value': query.get('value'),
                    'desc': query.get('desc'),
                }
                for query in api_data.get("req_query")
            ]

        # 处理请求体
        req_body_type = api_data.get('req_body_type')
        if req_body_type == "json":
            request_info['body_type'] = 1
            try:
                request_info['body'] = json.loads(api_data.get('res_body', '{}'))
            except JSONDecodeError:
                request_info['body'] = api_data.get('res_body')
        elif req_body_type == "form":
            request_info['body_type'] = 2
            request_info['data'] = api_data.get('req_body_form')
        else:
            request_info['body_type'] = 0

        return request_info
