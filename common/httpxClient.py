#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/7/3
# @Author : cyq
# @File : httpxClient
# @Software: PyCharm
# @Desc:
from typing import Optional, Callable, Dict, List
from httpx import Response, Timeout, ReadTimeout, ConnectTimeout, ConnectError, AsyncClient, HTTPStatusError, Request, \
    UnsupportedProtocol,RemoteProtocolError

from enums import InterfaceResponseErrorMsgEnum
from utils import MyLoguru, log

LOG = MyLoguru().get_logger()


class HttpxClient:
    # BUG-E2 修复: 写死的 user-agent "case_Hub_http/v0.1" 删了。
    # 旧逻辑下, 调用方无法在 Interface.interface_headers 里覆盖, 因为 client
    # headers 在 client 创建时硬塞 user-agent, 后续 httpx 合并时若 interface_headers
    # 不含 User-Agent 就会用这个 magic string, 且 magic string 没来源说明。
    # 改: 入参 default_user_agent (None = 走 httpx 内置 user-agent);
    # 运行时通过 interface_headers / g_headers 配的 User-Agent 仍会按 httpx 规则
    # 单次 request 覆盖。

    def __init__(
            self,
            logger: Optional[Callable] = None,
            hooks: Optional[Dict[str, List[Callable]]] = None,
            default_timeout: Optional[Timeout] = 10,
            default_user_agent: Optional[str] = None,
            **client_kwargs
    ):
        """
        初始化HTTP客户端

        :param logger: 自定义日志记录器
        :param hooks: 自定义事件钩子
        :param default_timeout: 默认超时设置
        :param client_kwargs: 其他httpx.AsyncClient参数
        """
        self.logger = logger
        self._client = None  # 延迟初始化
        self.default_timeout = default_timeout
        # 合并默认钩子和自定义钩子
        self._hooks = {
            'request': [self.log_request],
            'response': [self.log_response]
        }
        if hooks:
            for event, event_hooks in hooks.items():
                self._hooks.setdefault(event, []).extend(event_hooks)

        # 客户端配置
        # BUG-E2 修复: 仅当调用方显式传 default_user_agent 时才注入 client headers,
        # 不传就走 httpx 内置 user-agent ("python-httpx/x.y.z"), 由 interface_headers
        # 传入的 User-Agent 单次覆盖 (httpx 合并规则: request headers 覆盖 client headers)。
        client_headers: Dict[str, str] = {}
        if default_user_agent:
            client_headers["user-agent"] = default_user_agent
        self._client_config = {
            "headers": client_headers,
            "event_hooks": self._hooks,
            **client_kwargs
        }

    @property
    def client(self) -> AsyncClient:
        """延迟初始化客户端"""
        if self._client is None:
            self._client = AsyncClient(**self._client_config)
        return self._client

    async def __call__(
            self,
            method: str,
            url: str,
            **kwargs
    ) -> Response:
        """
        发起HTTP请求

        :param method: HTTP方法 (GET, POST等)
        :param url: 请求URL
        :param kwargs: 其他httpx请求参数
        :return: 响应对象
        """
        # 把 connect/read 超时从 kwargs 取出,放到本次 request 的 timeout 上,
        # **不**修改 self.client.timeout (BUG-E1) ——
        # 共享 client 状态被并发请求互相覆盖是经典坑。
        connect = kwargs.pop("connect", self.default_timeout)
        read = kwargs.pop("read", self.default_timeout)
        kwargs.setdefault("timeout", Timeout(connect=connect, read=read, write=self.default_timeout, pool=self.default_timeout))
        return await self._request(
            method=method.lower(),
            url=url,
            **kwargs
        )

    async def _request(
            self,
            method: str,
            url: str,
            **kwargs
    ) -> Response:
        """
        执行HTTP请求并处理响应

        :param method: HTTP方法
        :param url: 请求URL
        :param kwargs: 其他httpx请求参数
        :return: 响应对象
        :raises: 各种HTTP请求异常
        """
        try:
            response = await self.client.request(method, url, **kwargs)
            # await self._validate_response(response)
            return response
        except UnsupportedProtocol:
            raise UnsupportedProtocol(InterfaceResponseErrorMsgEnum.UnsupportedProtocol)
        except ReadTimeout:
            raise ReadTimeout(InterfaceResponseErrorMsgEnum.ResponseTimeout)
        except ConnectTimeout:
            raise ConnectTimeout(InterfaceResponseErrorMsgEnum.ConnectTimeout)
        except ConnectError:
            raise ConnectError(InterfaceResponseErrorMsgEnum.ConnectFailed)
        except RemoteProtocolError:
            raise RemoteProtocolError(InterfaceResponseErrorMsgEnum.RemoteProtocolError)
        except Exception as e:
            log.error(e)
            raise

    async def _validate_response(self, response: Response) -> None:
        """
        验证响应状态码

        :param response: 响应对象
        :raises: 如果响应状态码非2xx则抛出异常
        """
        if not 200 <= response.status_code < 300:
            error_msg = (
                f"Request failed with status {response.status_code}. "
                f"Response: {response.text[:500]}..."  # 限制日志长度
            )
            LOG.error(error_msg)
            raise HTTPStatusError(error_msg)

    async def log_request(self, request: Request) -> None:
        """记录请求日志"""
        log_msg = f"🚀🚀  Request {request.method.upper()}: {request.url}"
        if self.logger:
            await self.logger(log_msg)
        LOG.info(log_msg)

    async def log_response(self, response: Response) -> None:
        """记录响应日志"""
        log_msg = f"🚀🚀  Response {response.status_code} for  {response.request.url}"
        if self.logger:
            await self.logger(log_msg)
        LOG.info(log_msg)

    async def close(self) -> None:
        """关闭客户端"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """支持异步上下文管理器"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动关闭"""
        await self.close()
