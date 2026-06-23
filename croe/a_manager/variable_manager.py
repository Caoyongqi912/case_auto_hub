#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : variable_manager
# @Software: PyCharm
# @Desc:
from typing import Any, Dict, List, Optional

from utils import log
from utils.variableTrans import VariableTrans


class VariableManager:
    """变量管理器"""

    def __init__(self, global_vars: Optional[Dict[str, Any]] = None):
        self.vars = VariableTrans(global_vars=global_vars)

    @property
    def variables(self) -> Dict[str, Any]:
        """获取所有变量"""
        return self.vars()

    def clear(self):
        """清空变量"""
        self.vars.clear()

    def get_vars(self) -> Dict[str, Any]:
        """获取所有变量"""
        return self.vars()

    def add_vars(self, data: List[Dict[str, Any]] | Dict[str, Any]):
        """添加变量"""
        self.vars.add_vars(data)

    def add_var(self, key: str, value: Any):
        """添加单个变量"""
        self.vars.add_var(key, value)

    def trans(self, target: Any) -> Any:
        """变量转换（已同步化）"""
        return self.vars.trans(target)

    def get_var(self, key: str):
        """获取变量值"""
        return self.vars.get_var(key)

    async def load_global_vars(self) -> None:
        """
        预加载所有全局变量到缓存。

        背景: VariableTrans.trans 已同步化，无法在执行过程中异步查库。
        调用方应在执行开始前调用此方法，将全局变量批量拉取到内存缓存。
        """
        from app.mapper.project import GlobalVariableMapper

        try:
            g_vars_list = await GlobalVariableMapper.query_all()
            if g_vars_list:
                self.vars.set_global_vars(
                    {gv.key: gv.value for gv in g_vars_list}
                )
        except Exception as e:
            log.warning(f"预加载全局变量失败: {e}")
