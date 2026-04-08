#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Request Builder

HTTP 请求构建器
负责根据 Interface 对象构建完整的 HTTP 请求信息
支持各种认证方式、请求体类型和参数处理
"""
import asyncio
import json
import os
from typing import Dict, Any, Tuple, Optional

import aiofiles
import mimetypes
from base64 import b64encode
from httpx._utils import to_bytes

from app.mapper.interface import InterfaceGlobalHeaderMapper
from app.model.interfaceAPIModel.interfaceModel import Interface
from croe.a_manager.variable_manager import VariableManager
from enums import InterfaceAuthType, InterfaceRequestMethodEnum, InterfaceRequestTBodyTypeEnum
from utils import GenerateTools, log


class RequestBuilder:
    """
    HTTP 请求构建器

    根据 Interface 对象构建完整的 HTTP 请求信息，
    支持 GET/POST 等各种请求方法和认证方式
    """

    def __init__(self, variables: VariableManager):
        """
        初始化请求构建器

        Args:
            variables: 变量管理器，用于变量替换
        """
        self.variables = variables

    async def set_req_info(self, interface: Interface) -> Dict[str, Any]:
        """
        处理并构建 HTTP 请求信息

        Args:
            interface: 接口对象，包含请求方法、头信息、参数等

        Returns:
            包含完整请求信息的字典，可用于 httpx 等 HTTP 客户端
        """
        _request_data = {
            'read': interface.interface_response_timeout,
            'connect': interface.interface_connect_timeout,
            'follow_redirects': bool(interface.interface_follow_redirects),
            InterfaceRequestTBodyTypeEnum.HEADERS: await self._prepare_headers(interface)
        }

        if interface.interface_method == InterfaceRequestMethodEnum.GET:
            await self._process_get_params(_request_data, interface)
        else:
            await self._process_request_body(_request_data, interface)

        log.debug(f"_request_data = {_request_data}")
        await self._prepare_auth(request_data=_request_data, interface=interface)
        # 并行转换请求数据中的变量
        await self._transform_request_data(_request_data)

        return _request_data

    @staticmethod
    async def _prepare_auth(request_data: Dict[str, Any], interface: Interface) -> None:
        """
        处理认证信息

        支持三种认证方式：
        - KV Auth: 将认证信息添加到 query 或 header
        - Basic Auth: 生成 Basic 认证头
        - Bearer Auth: 生成 Bearer 认证头

        Args:
            request_data: 请求数据字典
            interface: 接口对象
        """
        match interface.interface_auth_type:
            case InterfaceAuthType.KV_Auth:
                _auth = interface.interface_auth
                target = _auth.pop("target")
                if target == "query":
                    request_data[InterfaceRequestTBodyTypeEnum.PARAMS].update(
                        GenerateTools.list2dict(_auth)
                    )
                elif target == "header":
                    request_data[InterfaceRequestTBodyTypeEnum.HEADERS].update(
                        GenerateTools.list2dict(_auth)
                    )

            case InterfaceAuthType.BASIC_Auth:
                userpass = b":".join((
                    to_bytes(interface.interface_auth.get("username")),
                    to_bytes(interface.interface_auth.get("password"))
                ))
                token = b64encode(userpass).decode()
                request_data[InterfaceRequestTBodyTypeEnum.HEADERS].update(
                    {"Authorization": f"Basic {token}"}
                )

            case InterfaceAuthType.BEARER_Auth:
                request_data[InterfaceRequestTBodyTypeEnum.HEADERS].update(
                    {"Authorization": f"Bearer {interface.interface_auth.get('token')}"}
                )

    @staticmethod
    async def _prepare_headers(interface: Interface) -> Dict[str, str]:
        """
        准备请求头

        合并全局请求头和接口特定的请求头

        Args:
            interface: 接口对象

        Returns:
            合并后的请求头字典
        """
        headers = {}

        global_headers = await InterfaceGlobalHeaderMapper.query_all()
        for header in global_headers:
            headers.update(header.map)

        if interface.interface_headers:
            headers.update(GenerateTools.list2dict(interface.interface_headers))

        return headers

    @staticmethod
    async def _process_get_params(request_data: Dict[str, Any], interface: Interface) -> None:
        """
        处理 GET 请求参数

        Args:
            request_data: 请求数据字典
            interface: 接口对象
        """
        if interface.interface_params:
            request_data[InterfaceRequestTBodyTypeEnum.PARAMS] = GenerateTools.list2dict(
                interface.interface_params
            )

    async def _process_request_body(self, request_data: Dict[str, Any], interface: Interface) -> None:
        """
        处理非 GET 请求的请求体

        Args:
            request_data: 请求数据字典
            interface: 接口对象
        """
        if not interface.interface_body_type or interface.interface_body_type == InterfaceRequestTBodyTypeEnum.Null:
            return

        body_data, content_type = await self._filter_request_body(interface)

        if content_type:
            request_data[InterfaceRequestTBodyTypeEnum.HEADERS]["Content-Type"] = content_type

        if body_data:
            request_data.update(**body_data)

    async def _filter_request_body(self, interface: Interface) -> Tuple[Dict[str, Any] | None, str | None]:
        """
        根据接口请求体类型处理请求体数据

        Args:
            interface: 接口对象

        Returns:
            Tuple[处理后的请求体字典, Content-Type 字符串]
            如果不需要请求体则返回 (None, None)
        """
        log.info(f"request body = {interface.interface_body}")
        log.info(f"request body_type = {interface.interface_body_type}")

        match interface.interface_body_type:
            case InterfaceRequestTBodyTypeEnum.Raw:
                return await self._prepare_raw_body(interface)
            case InterfaceRequestTBodyTypeEnum.UrlEncoded:
                return await self._prepare_form_urlencoded(interface)
            case InterfaceRequestTBodyTypeEnum.Data:
                return await self._prepare_form_data(interface)
            case _:
                log.warning(f"Unsupported body type: {interface.interface_body_type}")
                return None, None

    async def _transform_request_data(self, request_data: Dict[str, Any]) -> None:
        """
        并行转换请求数据中的变量

        Args:
            request_data: 请求数据字典
        """
        items_to_transform = {
            key: value
            for key, value in request_data.items()
            if value is not None
        }

        if not items_to_transform:
            return

        async with asyncio.TaskGroup() as tg:
            tasks = {
                tg.create_task(self.variables.trans(value)): key
                for key, value in items_to_transform.items()
            }

        for task, key in tasks.items():
            transformed_value = task.result()
            if transformed_value is not None:
                request_data[key] = transformed_value

    @staticmethod
    async def _prepare_raw_body(interface: Interface) -> Tuple[Dict[str, Any], str]:
        """
        准备原始请求体（JSON/Text）

        Args:
            interface: 接口对象

        Returns:
            Tuple[请求体字典, Content-Type]
        """
        if interface.interface_raw_type == "json":
            return (
                {InterfaceRequestTBodyTypeEnum.JSON: interface.interface_body},
                "application/json"
            )
        else:
            return (
                {InterfaceRequestTBodyTypeEnum.Content: json.dumps(interface.interface_body)},
                "text/plain"
            )

    @staticmethod
    async def _prepare_form_urlencoded(interface: Interface) -> Tuple[Dict[str, Any], str]:
        """
        准备 URL 编码表单数据

        Args:
            interface: 接口对象

        Returns:
            Tuple[表单数据字典, Content-Type]
        """
        form_data = GenerateTools.list2dict(interface.interface_data)
        return (
            {InterfaceRequestTBodyTypeEnum.FORM_DATA: form_data},
            "application/x-www-form-urlencoded"
        )

    async def _prepare_form_data(self, interface: Interface) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        准备多部分表单数据（支持文件上传）

        Args:
            interface: 接口对象

        Returns:
            Tuple[表单数据和文件字典, Content-Type]
        """
        files = {}
        data = {}

        form_data = GenerateTools.list2dict(interface.interface_data)

        for key, value in form_data.items():
            if str(value).startswith(str(interface.uid)):
                file_info = await self._prepare_file_upload(key, value)
                if file_info:
                    files[key] = file_info
            else:
                data[key] = value

        return (
            {
                InterfaceRequestTBodyTypeEnum.FORM_FILES: files,
                InterfaceRequestTBodyTypeEnum.FORM_DATA: data
            },
            None
        )

    @staticmethod
    async def _prepare_file_upload(key: str, value: Any) -> Optional[Tuple]:
        """
        准备文件上传数据

        Args:
            key: 文件字段名
            value: 文件值

        Returns:
            文件上传元组 (filename, content, mime_type)
        """
        from utils.fileManager import API_DATA

        files = {}
        filepath = os.path.join(API_DATA, value)
        log.debug(f"filepath = {filepath}")

        try:
            if not os.path.exists(filepath):
                log.error(f"文件不存在: {filepath}")
                return None

            if not os.access(filepath, os.R_OK):
                log.error(f"文件不可读: {filepath}")
                return None

            mime_type, _ = mimetypes.guess_type(str(filepath))
            mime_type = mime_type or 'application/octet-stream'

            file_name = os.path.basename(filepath).split("_")[-1]

            async with aiofiles.open(filepath, 'rb') as f:
                file_content = await f.read()

            if file_content:
                files[key] = (file_name, file_content, mime_type)
                log.debug(f"文件 {file_name} 已添加到上传列表，MIME 类型 = {mime_type}")
                return file_name, file_content, mime_type
            else:
                log.error(f"无法读取文件 {filepath}")
                return None

        except Exception as e:
            log.exception(f"处理文件 {filepath} 时出错: {str(e)}")
            return None
