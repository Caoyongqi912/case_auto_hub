#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/18
# @Author : cyq
# @File : variableTrans
# @Desc:
import io
from typing import Any, Dict, List, Optional, Tuple, TypeVar

from common.fakerClient import FakerClient
from functools import singledispatchmethod
import re

from utils import GenerateTools, log

VARS = TypeVar("VARS", bound=Dict[str, Any] | List[Dict[str, Any]])

# 默认长度，大于该长度的变量使用并行处理（已废弃，保留以兼容旧调用）
MAX_LENGTH = 5


class VariableTrans:
    """
    变量转换类

    vars = {name:cyq,age:123,...}

    {{name}} => cyq
    {{g_data} => global table data（需先通过 load_global_var / set_global_vars 预加载）
    {{f_name}} => faker.name() func
    {{timestamp}} => FakerClient.timestamp func
    """

    def __init__(self, global_vars: Optional[Dict[str, Any]] = None):
        self._vars: Dict[str, Any] = {}
        self._faker = FakerClient()
        # 全局变量缓存，由调用方预加载
        self._g_vars_cache: Dict[str, Any] = global_vars or {}

        self._vars_pattern = re.compile(r"\{\{(.*?)\}\}")
        self._full_vars_pattern = re.compile(r"^\{\{(.*?)\}\}$")

    def __call__(self) -> Dict[str, Any]:
        return self._vars.copy()

    def clear(self):
        """清空变量"""
        self._vars.clear()

    def get_var(self, key: str):
        # 严格模式 (VARIABLE_TRANS_STRICT=1) 抛 KeyError。
        if key not in self._vars:
            import os
            msg = f"get_var 未定义变量 '{key}'"
            if os.environ.get("VARIABLE_TRANS_STRICT") == "1":
                raise KeyError(msg)
            log.warning(msg)
        return self._vars.get(key, key)

    def add_vars(self, data: VARS) -> None:
        """
        添加多个变量
        """
        if isinstance(data, dict):
            self._vars.update(**data)
        elif isinstance(data, list):
            data = GenerateTools.list2dict(data)
            self._vars.update(**data)
        else:
            raise TypeError(f"Unsupported type: {type(data)}")

    def add_var(self, key: str, value: Any):
        """
        添加单个变量
        """
        if not isinstance(key, str):
            raise TypeError("Key must be a string")
        self._vars.update(**{key: value})

    def load_global_var(self, key: str, value: Any) -> None:
        """
        预加载单个全局变量到缓存。

        Args:
            key: 全局变量名（不含 $g_ 前缀）
            value: 变量值
        """
        self._g_vars_cache[key] = value

    def set_global_vars(self, global_vars: Dict[str, Any]) -> None:
        """
        批量设置全局变量缓存。

        Args:
            global_vars: {变量名: 变量值}，变量名不含 $g_ 前缀
        """
        self._g_vars_cache = dict(global_vars)

    @singledispatchmethod
    def trans(self, target: Any) -> Any:
        """
        类型分发（同步）
        """
        return target

    @trans.register(str)
    def _(self, target: str) -> str:
        """处理字符类型转换"""
        if not target:
            return target

        if full_match := self._full_vars_pattern.match(target):
            return self._resolve_vars(full_match.group(1))

        return self._transform_str_with_vars(target)

    @trans.register(dict)
    def _(self, target: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理字典类型的转换
        """
        if not target:
            return {}
        keys, values = zip(*target.items())
        transformed_values = [self.trans(v) for v in values]
        return dict(zip(keys, transformed_values))

    @trans.register(list)
    def _(self, target: List[Any]) -> List[Any]:
        """处理列表类型的转换"""
        return [self.trans(item) for item in target]

    @trans.register(tuple)
    def _(self, target: Tuple[Any, ...]) -> Tuple[Any, ...]:
        """处理元组类型的转换"""
        transformed_items = []
        for item in target:
            # 兼容下 http 请求体中的文件上传
            if isinstance(item, io.BufferedReader):
                transformed_items.append(item)
                continue
            transformed = self.trans(item)
            transformed_items.append(transformed)
        return tuple(transformed_items)

    def _resolve_vars(self, var_name: str) -> Any:
        """
        解析变量名

        :param var_name: 变量名
        :return: 变量值或原始字符串
        """
        var_name = var_name.strip()
        if var_name.startswith("$f_"):
            # 处理 Faker 生成的 内置变量
            return self._faker.value(var_name[1:])
        elif var_name.startswith("$g_"):
            # 处理全局变量（从预加载缓存读取）
            return self._resolve_global_var(var_name[1:])
        # 常规变量
        if var_name not in self._vars:
            import os
            msg = f"引用了未定义的变量 '{var_name}', 将按字面量返回"
            if os.environ.get("VARIABLE_TRANS_STRICT") == "1":
                raise KeyError(msg)
            log.warning(msg)
        return self._vars.get(var_name, f"{var_name}")

    def _resolve_global_var(self, script: str) -> Any:
        """
        从预加载的全局变量缓存中取值。

        背景: 原 __find_g_vars / _find_g_vars 是 async 并查数据库。
        为把 trans 同步化，改为由调用方在执行前预加载全局变量到缓存。
        如果未预加载，给出明确警告并返回原始占位符。
        """
        log.info(f"g var = {script}")
        key = script.split("g_")[-1]
        if key in self._g_vars_cache:
            return self._g_vars_cache[key]
        import os
        msg = (
            f"全局变量 '{key}' 未预加载，将按字面量返回。"
            f"如需使用全局变量，请先调用 VariableManager.load_global_vars()"
        )
        if os.environ.get("VARIABLE_TRANS_STRICT") == "1":
            raise KeyError(msg)
        log.warning(msg)
        return f"{{{{$g_{key}}}}}"

    def _transform_str_with_vars(self, target: str) -> str:
        """
        处理包含变量插值的字符串

        :param target: 原始字符串
        :return: 替换后的字符串
        """
        # 处理字符串中的变量插值
        parts = []
        last_end = 0
        for match in self._vars_pattern.finditer(target):
            # 添加非变量部分
            parts.append(target[last_end:match.start()])
            # 解析变量部分
            var_value = self._resolve_vars(match.group(1))
            parts.append(str(var_value))
            last_end = match.end()

        # 添加剩余部分
        parts.append(target[last_end:])
        return "".join(parts)

    def __repr__(self):
        return f"Vars {self._vars}"
