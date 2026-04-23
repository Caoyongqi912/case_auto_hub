#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : upload_file
# @Software: PyCharm
# @Desc: 文件上传解析模块

import asyncio
import json
from json import JSONDecodeError
from typing import List, Dict, Any

from fastapi import UploadFile
from enums import InterfaceUploadEnum
from utils import MyLoguru

log = MyLoguru().get_logger()


class FileReader:
    """文件读取器，用于解析不同格式的接口文档"""

    @staticmethod
    async def read_upload_file(
        file_type: str,
        file: UploadFile
    ) -> List[Dict[str, Any]]:
        """
        读取上传文件

        Args:
            file_type: 文件类型
            file: 上传的文件对象

        Returns:
            解析后的接口数据列表
        """
        match file_type:
            case InterfaceUploadEnum.YApi:
                return await FileReader._yapi(file)
            case InterfaceUploadEnum.PostMan:
                return []
            case InterfaceUploadEnum.Swagger:
                return []
            case InterfaceUploadEnum.ApiPost:
                return await FileReader._apipost(file)
            case _:
                log.warning(f"不支持的文件类型: {file_type}")
                return []

    @staticmethod
    async def _apipost(file: UploadFile) -> List[Dict[str, Any]]:
        """
        解析ApiPost格式文件

        Args:
            file: 上传的文件对象

        Returns:
            解析后的接口数据列表
        """
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
                post_data['data'].append(
                    await FileReader._get_apipost_data(api)
                )

        return [post_data]

    @staticmethod
    async def _get_apipost_data(
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        获取ApiPost单个接口数据

        Args:
            data: 单个接口的原始数据

        Returns:
            解析后的接口信息
        """
        request_info = {
            'name': data.get("name"),
            'method': data.get("method"),
            'url': data.get("url"),
            'description': data.get("description", ""),
        }

        request = data.get("request")
        if not request:
            return request_info

        headers = request.get("header", {}).get("parameter")
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

        query = request.get("query", {}).get("parameter")
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

        body = request.get("body", {})
        mode = body.get("mode")

        if mode == "json":
            request_info['body_type'] = 1
            try:
                request_info['body'] = json.loads(body.get("raw", "{}"))
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
        解析YAPI导出的文件数据

        Args:
            file: 上传的文件对象

        Returns:
            解析后的YAPI数据列表
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
                module_data['data'] = await asyncio.gather(
                    *(
                        FileReader._get_yapi_data(api_data)
                        for api_data in item_list
                    )
                )

            yapi_data.append(module_data)

        return yapi_data

    @staticmethod
    async def _get_yapi_data(
        api_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解析单个YAPI数据

        Args:
            api_data: 单个API的原始数据

        Returns:
            解析后的请求信息
        """
        request_info = {
            'name': api_data.get("title"),
            'method': api_data.get("method"),
            'url': api_data.get("path"),
            'params': api_data.get("req_params", []),
            'headers': api_data.get("req_headers", []),
            'description': api_data.get("desc", ""),
        }

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

        req_body_type = api_data.get('req_body_type')
        if req_body_type == "json":
            request_info['body_type'] = 1
            try:
                request_info['body'] = json.loads(
                    api_data.get('res_body', '{}')
                )
            except JSONDecodeError:
                request_info['body'] = api_data.get('res_body')
        elif req_body_type == "form":
            request_info['body_type'] = 2
            request_info['data'] = api_data.get('req_body_form')
        else:
            request_info['body_type'] = 0

        return request_info
