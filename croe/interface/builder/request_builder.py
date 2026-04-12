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

from app.mapper.interfaceApi.interfaceGlobalMapper import InterfaceGlobalHeaderMapper
from app.model.interfaceAPIModel.interfaceModel import Interface
from croe.a_manager.variable_manager import VariableManager
from enums import InterfaceAuthType, InterfaceRequestMethodEnum, InterfaceRequestTBodyTypeEnum
from utils import GenerateTools, log



KEY_HEADERS = "headers"
KEY_PARAMS = "params"
KEY_JSON = "json"
KEY_FORM_DATA = "data"
KEY_FORM_FILES = "files"
KEY_CONTENT = "content"


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

    # ==================== 公共接口 ====================

    async def set_req_info(self, interface: Interface) -> Dict[str, Any]:
        """
        构建完整的 HTTP 请求信息（主入口）

        执行流程：
        1. 初始化基础请求信息（超时、重定向等）
        2. 准备请求头
        3. 处理请求参数或请求体
        4. 处理认证信息
        5. 变量替换

        Args:
            interface: 接口对象，包含请求方法、头信息、参数等

        Returns:
            包含完整请求信息的字典，可用于 httpx 等 HTTP 客户端
        """
        # 初始化基础请求信息
        request_data = {
            'read': interface.interface_response_timeout,
            'connect': interface.interface_connect_timeout,
            'follow_redirects': bool(interface.interface_follow_redirects),
            KEY_HEADERS: await self._prepare_headers(interface)
        }

        # 根据请求方法处理参数或请求体
        if interface.interface_method == InterfaceRequestMethodEnum.GET:
            await self._process_get_params(request_data, interface)
        else:
            await self._process_request_body(request_data, interface)

        log.debug(f"构建的请求信息: {request_data}")

        # 处理认证信息
        await self._prepare_auth(request_data, interface)

        # 变量替换
        await self._transform_request_data(request_data)

        return request_data

    # ==================== 私有方法 - 请求头处理 ====================

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

        # 添加全局请求头
        global_headers = await InterfaceGlobalHeaderMapper.query_all()
        for header in global_headers:
            headers.update(header.map)

        # 添加接口特定请求头
        if interface.interface_headers:
            headers.update(GenerateTools.list2dict(interface.interface_headers))

        return headers

    # ==================== 私有方法 - 认证处理 ====================

    @staticmethod
    async def _prepare_auth(request_data: Dict[str, Any], interface: Interface) -> None:
        """
        处理认证信息

        支持三种认证方式：
        - KV Auth: 将认证信息添加到 query 或 header
        - Basic Auth: 生成 Basic 认证头
        - Bearer Auth: 生成 Bearer 认证头

        Args:
            request_data: 请求数据字典（会被修改）
            interface: 接口对象
        """
        auth_type = interface.interface_auth_type

        # KV 认证：添加到 query 或 header
        if auth_type == InterfaceAuthType.KV_Auth:
            auth_data = interface.interface_auth.copy()
            target = auth_data.pop("target")

            if target == "query":
                # 添加到查询参数
                request_data[KEY_PARAMS].update(
                    GenerateTools.list2dict(auth_data)
                )
            elif target == "header":
                # 添加到请求头
                request_data[KEY_HEADERS].update(
                    GenerateTools.list2dict(auth_data)
                )

        # Basic 认证：生成 Basic 认证头
        elif auth_type == InterfaceAuthType.BASIC_Auth:
            userpass = b":".join((
                to_bytes(interface.interface_auth.get("username")),
                to_bytes(interface.interface_auth.get("password"))
            ))
            token = b64encode(userpass).decode()
            request_data[KEY_HEADERS].update(
                {"Authorization": f"Basic {token}"}
            )

        # Bearer 认证：生成 Bearer 认证头
        elif auth_type == InterfaceAuthType.BEARER_Auth:
            request_data[KEY_HEADERS].update(
                {"Authorization": f"Bearer {interface.interface_auth.get('token')}"}
            )

    # ==================== 私有方法 - 参数处理 ====================

    @staticmethod
    async def _process_get_params(request_data: Dict[str, Any], interface: Interface) -> None:
        """
        处理 GET 请求参数

        Args:
            request_data: 请求数据字典（会被修改）
            interface: 接口对象
        """
        if interface.interface_params:
            request_data[KEY_PARAMS] = GenerateTools.list2dict(
                interface.interface_params
            )

    # ==================== 私有方法 - 请求体处理 ====================

    async def _process_request_body(self, request_data: Dict[str, Any], interface: Interface) -> None:
        """
        处理非 GET 请求的请求体

        Args:
            request_data: 请求数据字典（会被修改）
            interface: 接口对象
        """
        # 检查是否有请求体
        if not interface.interface_body_type or interface.interface_body_type == InterfaceRequestTBodyTypeEnum.Null:
            return

        # 根据请求体类型处理
        body_data, content_type = await self._filter_request_body(interface)

        # 设置 Content-Type
        if content_type:
            request_data[KEY_HEADERS]["Content-Type"] = content_type

        # 添加请求体数据
        if body_data:
            request_data.update(**body_data)

    async def _filter_request_body(self, interface: Interface) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        根据接口请求体类型处理请求体数据

        Args:
            interface: 接口对象

        Returns:
            Tuple[处理后的请求体字典, Content-Type 字符串]
            如果不需要请求体则返回 (None, None)
        """
        log.info(f"请求体类型: {interface.interface_body_type}")
        log.info(f"请求体内容: {interface.interface_body}")

        body_type = interface.interface_body_type

        # Raw 类型：JSON 或 Text
        if body_type == InterfaceRequestTBodyTypeEnum.Raw:
            return await self._prepare_raw_body(interface)

        # URL 编码表单
        elif body_type == InterfaceRequestTBodyTypeEnum.UrlEncoded:
            return await self._prepare_form_urlencoded(interface)

        # 多部分表单（支持文件上传）
        elif body_type == InterfaceRequestTBodyTypeEnum.Data:
            return await self._prepare_form_data(interface)

        # 不支持的类型
        else:
            log.warning(f"不支持的请求体类型: {body_type}")
            return None, None

    @staticmethod
    async def _prepare_raw_body(interface: Interface) -> Tuple[Dict[str, Any], str]:
        """
        准备原始请求体（JSON/Text）

        Args:
            interface: 接口对象

        Returns:
            Tuple[请求体字典, Content-Type]
        """
        # JSON 类型
        if interface.interface_raw_type == "json":
            return (
                {KEY_JSON: interface.interface_body},
                "application/json"
            )
        # Text 类型
        else:
            return (
                {KEY_CONTENT: json.dumps(interface.interface_body)},
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
            {KEY_FORM_DATA: form_data},
            "application/x-www-form-urlencoded"
        )

    async def _prepare_form_data(self, interface: Interface) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        准备多部分表单数据（支持文件上传）

        Args:
            interface: 接口对象

        Returns:
            Tuple[表单数据和文件字典, Content-Type]
            注意：多部分表单的 Content-Type 由 httpx 自动设置，因此返回 None
        """
        files = {}
        data = {}

        form_data = GenerateTools.list2dict(interface.interface_data)

        # 遍历表单数据，区分文件字段和普通字段
        for key, value in form_data.items():
            # 文件字段：值以接口 UID 开头
            if str(value).startswith(str(interface.uid)):
                file_info = await self._prepare_file_upload(key, value)
                if file_info:
                    files[key] = file_info
            # 普通字段
            else:
                data[key] = value

        return (
            {
                KEY_FORM_FILES: files,
                KEY_FORM_DATA: data
            },
            None  # Content-Type 由 httpx 自动设置
        )

    @staticmethod
    async def _prepare_file_upload(key: str, value: Any) -> Optional[Tuple[str, bytes, str]]:
        """
        准备文件上传数据

        Args:
            key: 文件字段名
            value: 文件值（文件路径标识）

        Returns:
            文件上传元组 (filename, content, mime_type)
            如果文件处理失败则返回 None
        """
        from utils.fileManager import API_DATA

        # 构建文件路径
        filepath = os.path.join(API_DATA, value)
        log.debug(f"准备上传文件: {filepath}")

        try:
            # 检查文件是否存在
            if not os.path.exists(filepath):
                log.error(f"文件不存在: {filepath}")
                return None

            # 检查文件是否可读
            if not os.access(filepath, os.R_OK):
                log.error(f"文件不可读: {filepath}")
                return None

            # 获取 MIME 类型
            mime_type, _ = mimetypes.guess_type(str(filepath))
            mime_type = mime_type or 'application/octet-stream'

            # 获取文件名（去除 UID 前缀）
            file_name = os.path.basename(filepath).split("_")[-1]

            # 读取文件内容
            async with aiofiles.open(filepath, 'rb') as f:
                file_content = await f.read()

            # 检查文件内容
            if not file_content:
                log.error(f"无法读取文件内容: {filepath}")
                return None

            log.debug(f"文件 {file_name} 已准备上传，MIME 类型: {mime_type}")
            return file_name, file_content, mime_type

        except Exception as e:
            log.exception(f"处理文件 {filepath} 时出错: {str(e)}")
            return None

    # ==================== 私有方法 - 变量转换 ====================

    async def _transform_request_data(self, request_data: Dict[str, Any]) -> None:
        """
        并行转换请求数据中的变量

        使用 asyncio.TaskGroup 并行处理所有需要变量替换的字段

        Args:
            request_data: 请求数据字典（会被修改）
        """
        # 过滤出需要转换的字段
        items_to_transform = {
            key: value
            for key, value in request_data.items()
            if value is not None
        }

        if not items_to_transform:
            return

        # 并行执行变量替换
        async with asyncio.TaskGroup() as tg:
            tasks = {
                tg.create_task(self.variables.trans(value)): key
                for key, value in items_to_transform.items()
            }

        # 更新转换后的值
        for task, key in tasks.items():
            transformed_value = task.result()
            if transformed_value is not None:
                request_data[key] = transformed_value
