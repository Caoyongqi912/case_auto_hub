#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: 接口执行结果写入器

from .result_writer import ResultWriter

result_writer = ResultWriter()

__all__ = [
    'ResultWriter',
    'result_writer',
]
