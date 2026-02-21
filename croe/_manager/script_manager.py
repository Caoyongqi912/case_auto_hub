#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : script_manager
# @Software: PyCharm
# @Desc:
import ast
import hashlib
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from functools import lru_cache

from faker import Faker
from utils import log, GenerateTools






# ==================== 安全配置 ====================
MAX_SCRIPT_LENGTH = 10000  # 最大脚本长度
SCRIPT_TIMEOUT = 5  # 脚本执行超时时间（秒）

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
    ast.Import, ast.ImportFrom, ast.alias,
    ast.Starred, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
}

# 不允许的属性访问
DISALLOWED_ATTRS = {
    '__import__', '__globals__', '__locals__', '__builtins__',
    '__class__', '__bases__', '__subclasses__', '__mro__',
    'eval', 'exec', 'compile', '__loader__', '__spec__',
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


class ScriptManager:
    """
    脚本管理器
    """

    def __init__(self):
        self._variables: Dict[str, Any] = {}
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
        self._validate_ast(tree)

        # 4. 执行脚本
        exec_globals = {**SAFE_BUILTINS, **self._allowed_functions}
        local_vars: Dict[str, Any] = {}
        
        try:
            exec(compile(tree, '<string>', 'exec'), exec_globals, local_vars)
        except Exception as e:
            log.exception(f"执行脚本失败: {e}")
            raise

        # 5. 收集结果
        return self._collect_results(local_vars)

    def _collect_results(self, local_vars: Dict[str, Any]) -> Dict[str, Any]:
        """收集执行结果 - 只收集非下划线开头且类型安全的变量"""
        results: Dict[str, Any] = {}
        for name, value in local_vars.items():
            if not name.startswith('_') and isinstance(value, ALLOWED_TYPES):
                results[name] = value
                self._variables[name] = value
        
        log.info(f"脚本执行结果: {results}")
        return results

    def _validate_ast(self, node: ast.AST) -> None:
        """
        验证 AST 安全性
        
        Args:
            node: AST 节点
            
        Raises:
            ScriptSecurityError: 发现不安全的节点
        """
        for child in ast.walk(node):
            # 检查节点类型
            if type(child) not in ALLOWED_NODE_TYPES:
                raise ScriptSecurityError(f"不允许的节点类型: {type(child).__name__}")
            
            # 检查属性访问
            if isinstance(child, ast.Attribute):
                if child.attr in DISALLOWED_ATTRS:
                    raise ScriptSecurityError(f"不允许的属性访问: {child.attr}")
            
            # 检查函数调用
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    if child.func.id in DISALLOWED_ATTRS:
                        raise ScriptSecurityError(f"不允许的函数调用: {child.func.id}")

    def _hub_variables_set(self, key: str, value: Any) -> None:
        """设置变量"""
        self._variables[key] = value

    def _hub_variables_get(self, key: str) -> Optional[Any]:
        """获取变量"""
        return self._variables.get(key)

    def _hub_variables_remove(self, key: str) -> None:
        """删除变量"""
        if key in self._variables:
            del self._variables[key]

    @staticmethod
    def _hub_api_request(url: str, method: str = "GET", **kwargs) -> Any:
        """发送 HTTP 请求"""
        try:
            import httpx
            with httpx.Client(timeout=10) as client:
                response = client.request(method=method, url=url, **kwargs)
                response.raise_for_status()
                return response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        except Exception as e:
            log.error(f"hub_request error: {e}")
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