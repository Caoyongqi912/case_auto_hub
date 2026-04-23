#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : recoder
# @Software: PyCharm
# @Desc: 接口录制模块

import json
from json import JSONDecodeError
from typing import List, Dict, Any, Optional

from mitmproxy import http
from enums import InterfaceRequestTBodyTypeEnum
from utils import log, GenerateTools
from common import rc

Headers = List[Dict[str, Any]] | None
Params = List[Dict[str, Any]] | None
Data = List[Dict[str, Any]] | None
VALID_EXTENSIONS = ("js", "css", "ttf", "jpg", "svg", "gif", "png", 'ts')


class Record:
    """录制管理类，用于管理接口录制状态"""

    prefix = "record_"

    @classmethod
    async def start_record(
        cls,
        key_name: str,
        record_info: Dict[str, Any]
    ) -> bool:
        """
        开始录制

        Args:
            key_name: 录制键名
            record_info: 录制信息

        Returns:
            是否成功开始录制
        """
        name = Record.prefix + key_name
        key = await rc.check_key_exist(name)
        if key:
            await rc.remove_key(name)

        log.debug(f"start record {name} {record_info}")

        for k, v in record_info.items():
            if isinstance(v, list):
                record_info[k] = json.dumps(v)

        return await rc.h_set(name=name, value=record_info)

    @classmethod
    async def clear_record(
        cls,
        ip: str,
        uid: str
    ) -> None:
        """
        停止录制

        Args:
            ip: IP地址
            uid: 用户ID
        """
        ip_key = cls.prefix + ip
        uid_key = cls.prefix + uid
        await rc.remove_key(ip_key)
        await rc.remove_key(uid_key)

    @classmethod
    async def query_record(
        cls,
        name: str
    ) -> List[Dict[str, Any]]:
        """
        查询录制

        Args:
            name: 录制名称

        Returns:
            录制数据列表
        """
        name = cls.prefix + name
        data = await rc.l_range(name=name)
        datas = [json.loads(i) for i in data]
        return datas

    @classmethod
    async def deduplication(
        cls,
        key_name: str
    ) -> None:
        """
        对URL去重

        Args:
            key_name: 录制键名
        """
        name = cls.prefix + key_name
        data = await rc.l_range(name=name)

        if not data:
            log.info(f"No data found for key: {name}")
            return

        seen_urls = set()
        unique_data = []

        for item_str in data:
            try:
                item = json.loads(item_str)
                url = item.get('url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_data.append(json.dumps(item))
            except json.JSONDecodeError as e:
                log.error(f"Failed to parse JSON: {e}, item: {item_str}")

        log.debug(unique_data)
        await rc.remove_key(name)

        pipeline = rc.r.pipeline()
        for item in unique_data:
            pipeline.rpush(name, item)

        await pipeline.execute()


class InterfaceRecoder:
    """接口录制器，用于捕获HTTP请求"""

    async def response(
        self,
        flow: http.HTTPFlow
    ) -> None:
        """
        响应回调

        Args:
            flow: HTTP流对象
        """
        is_options = flow.request.method.lower() == "options"
        has_static_ext = any(
            ext in flow.request.url for ext in VALID_EXTENSIONS
        )

        if is_options or has_static_ext:
            return

        client_key = "record_" + flow.client_conn.peername[0]
        _client = await rc.h_get_all(client_key)

        if not _client:
            return

        try:
            methods = json.loads(_client['method'])
        except (JSONDecodeError, KeyError) as e:
            log.error(f"解析method失败: {e}")
            return

        url_match = _client["url"] in flow.request.url
        method_match = flow.request.method.upper() in methods

        if _client and url_match and method_match:
            ir = RecordRequest(flow)
            await rc.l_push("record_" + _client['uid'], ir.map)


class RecordRequest:
    """录制请求信息封装"""

    uid: str = None
    url: str | None = None
    method: str | None = None
    headers: Headers = None
    params: Params = None
    body: dict | None = None
    data: Data = None
    body_type: int | None = None
    response: str | None = None

    def __init__(self, flow: http.HTTPFlow) -> None:
        """
        初始化录制请求

        Args:
            flow: HTTP流对象
        """
        self.flow = flow
        self.url = flow.request.url
        self.method = flow.request.method
        self.set_headers()
        self.set_body()
        self.set_response()

    def set_headers(self) -> None:
        """设置请求头"""
        if self.flow.request.headers:
            _headers = dict(self.flow.request.headers)
            self.headers = [
                dict(key=k, value=v, id=GenerateTools.uid())
                for k, v in _headers.items()
                if k not in ["content-length"]
            ]

    def set_body(self) -> None:
        """
        设置请求体

        支持类型：
        - 无body
        - json body
        - data body
        """
        request_type = self.flow.request.headers.get("Content-Type", "")

        if "json" in request_type:
            self._is_json()
        elif "form" in request_type:
            self._is_data()
        else:
            self._is_params()

    def set_response(self) -> None:
        """设置响应内容"""
        content_type = self.flow.response.headers.get("Content-Type", "")
        text = self.flow.response.text if self.flow.response.text else ""

        content_encoding = self.flow.response.headers.get(
            "Content-Encoding", "utf-8"
        )

        try:
            if "json" in content_type.lower():
                self.response = json.dumps(
                    json.loads(text),
                    indent=4,
                    ensure_ascii=False
                )
            elif "text" in content_type.lower() or "xml" in content_type.lower():
                self.response = text
            else:
                self.response = self.flow.response.data.decode(content_encoding)
        except (JSONDecodeError, UnicodeDecodeError) as e:
            log.error(f"Error processing response: {e}")
            self.response = text

    def _is_json(self) -> None:
        """处理JSON请求体"""
        try:
            self.body_type = InterfaceRequestTBodyTypeEnum.Json
            self.body = json.loads(self.flow.request.text)
        except json.decoder.JSONDecodeError as e:
            log.error(f"JSON解析失败: {e}")

    def _is_data(self) -> None:
        """处理表单数据请求体"""
        self.body_type = InterfaceRequestTBodyTypeEnum.Data
        self.data = self._parse_kv_text(self.flow.request.text)

    def _is_params(self) -> None:
        """处理URL参数"""
        self.body_type = InterfaceRequestTBodyTypeEnum.Null
        try:
            query = self.flow.request.query
            self.params = [
                {"key": k, "value": v}
                for k, v in dict(query).items()
            ]
        except Exception as e:
            log.error(f"解析URL参数失败: {e}")

    @staticmethod
    def _parse_kv_text(text: str) -> List[Dict[str, str]]:
        """
        解析键值对文本

        将给定的类似 `key=value` 格式用 `&` 连接的文本解析为字典列表，
        每个字典包含 'key' 和 'value' 表示解析后的键值对，
        并且对键值进行 `unquote` 解引用处理。

        Args:
            text: 待解析的文本，格式如 `key1=value1&key2=value2`

        Returns:
            解析后的字典列表
        """
        from urllib.parse import unquote

        pairs = text.split('&')
        result = []

        for pair in pairs:
            key_value = pair.split('=')
            if len(key_value) == 2:
                key = unquote(key_value[0])
                value = unquote(key_value[1])
                result.append({'key': key, 'value': value})

        return result

    @property
    def map(self) -> str:
        """
        获取请求映射字典的JSON字符串

        Returns:
            JSON格式的请求信息
        """
        m = dict(
            response=self.response,
            create_time=GenerateTools.getTime(1),
            uid=GenerateTools.uid(),
            url=self.url,
            method=self.method,
            headers=self.headers,
            params=self.params,
            data=self.data,
            body=self.body,
            body_type=self.body_type
        )
        return json.dumps(m, ensure_ascii=False)
