#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : script_manager
# @Software: PyCharm
# @Desc:
import ast
import hashlib
import ipaddress
import multiprocessing
import os
import pickle
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from functools import lru_cache

from faker import Faker
from utils import log, GenerateTools

# ==================== 安全配置 ====================
MAX_SCRIPT_LENGTH = 10000  # 最大脚本长度
SCRIPT_TIMEOUT = 5

# 允许的 AST 节点类型
ALLOWED_NODE_TYPES = {
    ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
    ast.Expr, ast.Name, ast.Constant, ast.Num, ast.Str,
    ast.List, ast.Dict, ast.Tuple, ast.Set,
    ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.BoolOp, ast.And, ast.Or, ast.Not,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot,
    ast.If, ast.For, ast.While,
    ast.Break, ast.Continue, ast.Pass,
    ast.Return, ast.Assign, ast.AugAssign,
    ast.AnnAssign, ast.Subscript, ast.Attribute,
    ast.Call, ast.keyword,
    ast.Starred, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
}

# 不允许的属性访问 / 函数调用名
DISALLOWED_ATTRS = {
    '__import__', '__globals__', '__locals__', '__builtins__',
    '__class__', '__bases__', '__subclasses__', '__mro__',
    'eval', 'exec', 'compile', '__loader__', '__spec__',
    'getattr', 'setattr', 'delattr', 'vars', 'dir',
}

# 安全的内置函数
SAFE_BUILTINS = {
    '__builtins__': {
        'range': range,
        'len': len,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'set': set,
        'abs': abs,
        'min': min,
        'max': max,
        'sum': sum,
        'round': round,
    },
}

# 允许的变量类型
ALLOWED_TYPES = (int, float, str, bool, list, dict, tuple, set, type(None))

class ScriptSecurityError(Exception):
    """脚本安全异常"""
    pass

def _exec_in_subprocess(script_content: str, exec_globals: Dict[str, Any], q) -> None:
    """
    子进程入口:解析并执行脚本,把结果放进队列。
    必须放在模块顶层(可 pickle),不能用 lambda / 闭包。
    """
    try:
        tree = ast.parse(script_content)
        local_vars: Dict[str, Any] = {}
        exec(compile(tree, "<string>", "exec"), exec_globals, local_vars)
        q.put(("ok", local_vars))
    except BaseException as e:  # noqa: BLE001  - 任何异常都序列化带回去
        try:
            q.put(("err", e))
        except Exception:
            pass

def _validate_ast(node: ast.AST) -> None:
    """
    验证 AST 安全性

    Args:
        node: AST 节点

    Raises:
        ScriptSecurityError: 发现不安全的节点
    """
    # 排除上下文类型（Store, Load, Del）
    EXCLUDED_CTX_TYPES = (ast.Store, ast.Load, ast.Del)

    for child in ast.walk(node):
        # 跳过上下文类型
        if isinstance(child, EXCLUDED_CTX_TYPES):
            continue

        # 检查节点类型
        if type(child) not in ALLOWED_NODE_TYPES:
            raise ScriptSecurityError(f"不允许的节点类型: {type(child).__name__}")

        # 检查属性访问
        if isinstance(child, ast.Attribute):
            if child.attr in DISALLOWED_ATTRS or child.attr.startswith("__"):
                raise ScriptSecurityError(f"不允许的属性访问: {child.attr}")

        # 检查函数调用
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                if child.func.id in DISALLOWED_ATTRS:
                    raise ScriptSecurityError(f"不允许的函数调用: {child.func.id}")
            elif isinstance(child.func, ast.Attribute):
                # 链式调用,如 os.system 或 getattr(obj, ...).__bases__
                if child.func.attr in DISALLOWED_ATTRS:
                    raise ScriptSecurityError(f"不允许的链式调用: {child.func.attr}")

def _check_ssrf(url: str) -> None:
    """
    [
    抛出 ValueError 走原有的 try/except, 调用方收到 None, 跟 "请求失败" 不可区分,
    攻击者通过观察响应时间 / 行为差分也无意义 (都是 None)。

    HUB_REQUEST_ALLOW_PRIVATE=1 时跳过 IP 检查 (内部测试场景需要打内网时显式开),
    但 scheme 限制仍然生效 (file:// 这种不该开逃生口)。
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)

    # 1. Scheme 白名单
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"hub_request 不允许 scheme '{parsed.scheme}' (仅 http/https)"
        )

    # 2. 必须有 host
    if not parsed.hostname:
        raise ValueError(f"hub_request URL 缺少 host: {url!r}")

    # 3. DNS 解析 + IP 黑名单
    import socket
    try:
        # getaddrinfo 返回所有解析结果 (含 IPv4 + IPv6), 任何一个命中就拒
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 80, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError(f"hub_request DNS 解析失败: {parsed.hostname!r}: {e}") from e

    for family, _, _, _, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            if os.environ.get("HUB_REQUEST_ALLOW_PRIVATE") == "1":
                log.warning(
                    f"hub_request 命中内网 IP {ip} 但环境变量 HUB_REQUEST_ALLOW_PRIVATE=1 放行"
                )
                return
            raise ValueError(
                f"hub_request 拒绝访问内网/loopback/link-local IP: {ip} (host={parsed.hostname!r})"
            )

def _is_blocked_ip(ip) -> bool:
    """
    [
    覆盖: 127.0.0.0/8 (loopback), 10.0.0.0/8 (private), 172.16.0.0/12 (private),
          192.168.0.0/16 (private), 169.254.0.0/16 (link-local + 云元数据),
          0.0.0.0/8, IPv6 ::1/128, fc00::/7 (IPv6 private), fe80::/10 (IPv6 link-local)
    """
    if isinstance(ip, ipaddress.IPv4Address):
        return (
            ip.is_loopback        # 127.0.0.0/8
            or ip.is_private      # 10/8, 172.16/12, 192.168/16
            or ip.is_link_local    # 169.254/16 (含云元数据)
            or ip.is_reserved      # 0.0.0.0/8, 240/4 等
            or ip.is_multicast
            or ip.is_unspecified   # 0.0.0.0
        )
    # IPv6
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )

class ScriptManager:
    """
    脚本管理器
    """

    SCRIPT_TIMEOUT: int = SCRIPT_TIMEOUT  # 暴露给测试,便于断言

    def __init__(self):
        # 单实例内的本地上下文, 跨实例不共享
        self._script_locals: Dict[str, Any] = {}
        self._faker = Faker(locale="zh_CN")

        # 允许的函数和变量
        self._allowed_functions = {
            'ts': self._ts,
            'date': self._date,
            'hub_variables_set': self._hub_variables_set,
            'hub_variables_get': self._hub_variables_get,
            'hub_variables_remove': self._hub_variables_remove,
            'hub_request': self._hub_api_request,
            'hub_faker': self._faker,
            'hub_md5': self._md5,
            'hub_random': self._random,
            'hub_month_begin': GenerateTools.getMonthFirst
        }

    def execute(self, script_content: str) -> Dict[str, Any]:
        """
        执行脚本

        Args:
            script_content: 脚本内容

        Returns:
            Dict[str, Any]: 执行结果变量

        Raises:
            ScriptSecurityError: 脚本安全检查失败
            SyntaxError: 脚本语法错误
            Exception: 执行异常
        """
        # 1. 检查脚本长度
        if len(script_content) > MAX_SCRIPT_LENGTH:
            raise ScriptSecurityError(f"脚本过长，最大长度: {MAX_SCRIPT_LENGTH}")

        # 2. 解析 AST
        try:
            tree = ast.parse(script_content)
        except SyntaxError as e:
            log.exception(f"解析脚本失败: {e}")
            raise

        # 3. 安全验证 AST
        _validate_ast(tree)

        # 用 multiprocessing 隔离执行, 子进程最多 SCRIPT_TIMEOUT 秒
        exec_globals = {**SAFE_BUILTINS, **self._allowed_functions}
        ctx = multiprocessing.get_context("spawn")  # macOS/Linux/Windows 行为一致
        q = ctx.Queue()
        proc = ctx.Process(
            target=_exec_in_subprocess,
            args=(script_content, exec_globals, q),
        )
        proc.start()
        proc.join(timeout=self.SCRIPT_TIMEOUT)

        if proc.is_alive():
            log.warning(f"脚本执行超时 ({self.SCRIPT_TIMEOUT}s),强杀子进程")
            proc.terminate()
            proc.join(timeout=2)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1)
            raise ScriptSecurityError(
                f"脚本执行超时 ({self.SCRIPT_TIMEOUT}s),已强制终止"
            )

        if proc.exitcode != 0:
            # 子进程非 0 退出往往是 unhandled exception
            raise ScriptSecurityError(
                f"脚本执行异常,exitcode={proc.exitcode}"
            )

        if q.empty():
            raise ScriptSecurityError("脚本未产生结果")

        status, payload = q.get_nowait()
        if status == "err":
            raise payload
        local_vars = payload

        # 5. 收集结果
        return self._collect_results(local_vars)

    def _collect_results(self, local_vars: Dict[str, Any]) -> Dict[str, Any]:
        """收集执行结果 - 收集 local_vars 和 self._script_locals 中的变量。
"""
        results: Dict[str, Any] = {}

        # 收集 local_vars 中的变量
        for name, value in local_vars.items():
            if not name.startswith('_') and isinstance(value, ALLOWED_TYPES):
                results[name] = value
                self._script_locals[name] = value

        # 收集 self._script_locals 中的变量 (本地上下文跨 exec 累积)
        for name, value in self._script_locals.items():
            if name not in results and not name.startswith('_') and isinstance(value, ALLOWED_TYPES):
                results[name] = value
        log.info(f"脚本执行结果: {results}")
        return results

    def _hub_variables_set(self, key: str, value: Any) -> None:
        """设置变量 (写到本地上下文)"""
        self._script_locals[key] = value

    def _hub_variables_get(self, key: str) -> Optional[Any]:
        """获取变量 (从本地上下文)"""
        return self._script_locals.get(key)

    def _hub_variables_remove(self, key: str) -> None:
        """删除变量 (从本地上下文)"""
        if key in self._script_locals:
            del self._script_locals[key]

    @staticmethod
    def _hub_api_request(url: str, method: str = "GET", **kwargs) -> Any:
        """
        发送 HTTP 请求 。

        子进程里没有现成 event loop,直接 asyncio.run 即可;主进程若将来
        在 async 上下文里调,需要再换成直接 await(本入口设计上仍是同步)。
"""
        import asyncio

        try:
            _check_ssrf(url)
        except ValueError as e:
            log.warning(f"hub_request SSRF 拦截: {e}")
            return None

        async def _do_request() -> Any:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.request(method=method, url=url, **kwargs)
                response.raise_for_status()
                if response.headers.get("content-type", "").startswith("application/json"):
                    return response.json()
                return response.text

        try:
            return asyncio.run(_do_request())
        except Exception as e:  # noqa: BLE001 - 调用方按 None 处理
            log.exception(f"hub_request error: {e}")
            return None

    @staticmethod
    @lru_cache(maxsize=128)
    def _ts(t: Optional[str] = None) -> Optional[int]:
        """
        返回对应时间戳

        Args:
            t: 时间偏移，如 "+1s"、"-2m"、"+3h"

        Returns:
            时间戳（秒）
        """
        if t is None:
            return int(time.time())

        if not isinstance(t, str) or len(t) < 2:
            return None

        operator = t[0]
        if operator not in "+":
            return None

        unit = t[-1]
        if unit not in "smh":
            return None

        try:
            value = int(t[1:-1])
        except ValueError:
            return None

        now = datetime.now()
        delta_map = {
            "s": timedelta(seconds=value),
            "m": timedelta(minutes=value),
            "h": timedelta(hours=value),
        }
        delta = delta_map.get(unit)
        if not delta:
            return None

        result = now + delta if operator == "+" else now - delta
        return int(result.timestamp())

    @staticmethod
    @lru_cache(maxsize=128)
    def _date(t: Optional[str] = None, ft: str = "%Y-%m-%d") -> Optional[str]:
        """
        获取当前日期

        Args:
            t: 日期偏移，如 "+1d"、"-2m"、"+3y"
            ft: 日期格式，默认 "%Y-%m-%d"

        Returns:
            格式化的日期字符串
        """
        if t is None:
            return datetime.today().strftime(ft)

        try:
            if not isinstance(t, str) or len(t) < 2:
                return None

            op = t[0]
            unit = t[-1]
            value_str = t[1:-1]

            delta_map = {
                "d": lambda v: timedelta(days=v),
                "m": lambda v: timedelta(days=v * 30),
                "y": lambda v: timedelta(days=v * 365),
            }

            if not (value_str.isdigit() and unit in delta_map):
                return None

            ts = int(value_str)
            delta = delta_map[unit](ts)
            base_date = datetime.today()

            if op == "+":
                result = base_date + delta
            elif op == "-":
                result = base_date - delta
            else:
                return None

            return result.strftime(ft)
        except Exception:
            return None

    @staticmethod
    def _md5(value: str) -> str:
        """计算 MD5 哈希"""
        return hashlib.md5(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _random(values: List[Any]) -> Any:
        """从列表中随机选择一个元素"""
        if not values:
            return None
        return random.choice(values)

__all__ = ["ScriptManager", "ScriptSecurityError"]