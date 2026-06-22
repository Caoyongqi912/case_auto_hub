#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : url_builder
# @Software: PyCharm
# @Desc: URL构建器

import ipaddress
import os
import socket
from typing import Optional, TYPE_CHECKING
from urllib.parse import urlparse

from app.model.interfaceAPIModel.interfaceModel import Interface
from app.model.base import EnvModel
from utils import log

if TYPE_CHECKING:
    pass


# SSRF 防护: 默认拒绝解析到内网 / 保留网段的 host。
# 部署方可以通过 env SSRF_ALLOW_PRIVATE_HOSTS=1 显式放开 (用于内网测试环境)。
# 此类风险 (B-SEC-2):
#   1. 已认证用户把 EnvModel.host / interface.interface_url 设为
#      169.254.169.254 (云元数据) / 127.0.0.1 / 10.x.x.x 等内网地址,
#   2. 借本服务的网络出口访问本应隔离的内部资源, 绕过网络分段。
#   3. 严重时可拿到云元数据凭据, 横向移动到内部服务。
def _allow_private() -> bool:
    """是否允许访问内网/保留网段 (env 开关, 内网测试时打开)。"""
    return os.getenv("SSRF_ALLOW_PRIVATE_HOSTS", "") == "1"


def _is_private(ip) -> bool:
    """综合判定一个 ipaddress.IPv4Address/IPv6Address 是否在保留网段。"""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _strip_port(host: str) -> str:
    """从 host:port 形式剥出 host, IPv6 字面量保持原样。

    - "127.0.0.1:8000"  -> "127.0.0.1"
    - "8.8.8.8"         -> "8.8.8.8"
    - "::1:8000"        -> "::1"      (IPv6 末尾被当 port 剥掉)
    - "::1"             -> "::1"
    - "2001:db8::1:443" -> "2001:db8::1"
    - "example.com:443" -> "example.com"
    """
    if not host:
        return host
    # 多冒号: 可能是 IPv6, 也可能是 IPv6:port
    if host.count(":") > 1:
        # 启发式: 末尾是纯数字 (port), 先剥一次看剩余部分是否还是合法 IP
        head, _, tail = host.rpartition(":")
        if tail.isdigit():
            try:
                ipaddress.ip_address(head)
                return head
            except ValueError:
                pass
        return host
    # 单冒号: host:port 或纯 host
    if ":" in host:
        head, _, tail = host.rpartition(":")
        if tail.isdigit():
            return head
    return host


def _resolve_host_is_private(host: str) -> bool:
    """检查 host 字符串是否解析到 RFC1918 / loopback / link-local 等保留网段。

    返回 True 表示是内网, 应该拒绝。
    """
    if not host:
        return True
    # 精确剥方括号 (而不是 strip('[]'), 避免 [::1]:8000 中 ']' 被误吃)
    if host.startswith("["):
        end = host.find("]")
        bare = host[1:end] if end > 0 else host
    else:
        bare = host
    bare = _strip_port(bare)
    # 1) IP 字面量
    try:
        ip = ipaddress.ip_address(bare)
        return _is_private(ip)
    except ValueError:
        pass
    # 2) 域名解析: 任意一条 A/AAAA 命中保留网段就算内网
    import threading
    holder: list = []
    def _do() -> None:
        try:
            holder.append(socket.getaddrinfo(bare, None))
        except Exception:
            pass
    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout=3.0)
    if not holder:
        # 解析超时/失败: 让请求层自己报错, 这里不阻断
        return False
    for info in holder[0]:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _is_private(ip):
            return True
    return False


def _extract_host(url_or_host: str) -> Optional[str]:
    """从 url 或裸 host:port/path 提取 host 部分, 支持 IPv6 字面量。

    例子:
    - "http://[::1]:8000/api" -> "::1"
    - "[::1]:8000/api"        -> "::1"
    - "::1:8000/api"          -> "::1:8000"  (host:port 由 _resolve_host_is_private 内部剥离)
    - "8.8.8.8:443/api"       -> "8.8.8.8:443"
    """
    s = url_or_host.strip()
    if not s:
        return None
    if "://" in s:
        # urlparse 路径: 会自动剥掉 IPv6 方括号, hostname 返回 ::1 这种
        try:
            return urlparse(s).hostname
        except Exception:
            return None
    # 裸 host:port/path
    if "/" in s:
        s = s.split("/", 1)[0]
    if not s:
        return None
    if s.startswith("["):
        end = s.find("]")
        if end > 0:
            return s[1:end]
    return s  # host[:port] 留原样, _resolve_host_is_private 会再处理


def _assert_safe_url(url_or_host: str) -> None:
    """校验 url/host 不指向内网/保留网段, 不通过抛 ValueError。"""
    if _allow_private():
        return
    host = _extract_host(url_or_host)
    if not host:
        return
    if _resolve_host_is_private(host):
        raise ValueError(
            f"SSRF 防护: 拒绝访问内网/保留网段 host={host!r}。"
            f"如需内网测试, 设置环境变量 SSRF_ALLOW_PRIVATE_HOSTS=1 后重启服务。"
        )


class UrlBuilder:
    """URL构建器"""

    CUSTOM_ENV_ID = 99999

    @staticmethod
    async def build(
        interface: Interface,
        env: Optional[EnvModel] = None
    ) -> str:
        """
        构建请求URL

        Args:
            interface: 接口对象
            env: 环境配置

        Returns:
            完整的请求URL

        Raises:
            ValueError: 未提供环境配置时抛出
        """
        if interface.env_id == UrlBuilder.CUSTOM_ENV_ID:
            log.info(f"使用自定义环境URL: {interface.interface_url}")
            _assert_safe_url(interface.interface_url)
            return interface.interface_url

        if env is None:
            raise ValueError(
                f"未提供环境配置，interface_id={interface.id}, "
                f"env_id={interface.env_id}"
            )

        base_url = env.url.rstrip('/')
        path = interface.interface_url.lstrip('/')

        url = f"{base_url}/{path}"
        log.info(f"构建请求URL: {url}")
        _assert_safe_url(url)
        return url
