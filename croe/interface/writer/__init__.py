#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/14
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: 接口执行结果写入器

from .result_writer import ResultWriter

# BUG-F8 修复: 删掉模块级单例 result_writer
# 之前 D1 修复给 InterfaceRunner 加了独立实例, 但 8 个 step_content_*.py +
# task.py 仍 import 这个单例, 导致 STEP_API content_result_cache 永远不被 flush
# (data 静默丢失, case 拿不到 step_result)。
# 现在所有调用方都从上下文/实例拿 result_writer, 不再需要这个单例。
__all__ = [
    'ResultWriter',
]
