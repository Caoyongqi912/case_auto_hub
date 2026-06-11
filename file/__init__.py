#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/12/17
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc:
import os.path

current_dir = os.path.dirname(__file__)

# 用例导入的空模板, downloadCaseDemo 接口直接 FileResponse 返回
TestCaseDemoFile = os.path.join(current_dir, "用例模版.xlsx")

# 导出-编辑-导回 圆桌的可见编辑指引, ExportCaseService 写入第二个 Sheet
ExportGuideFile = os.path.join(current_dir, "编辑指引.txt")
