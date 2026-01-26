#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/26
# @Author : cyq
# @File : test_schema_import.py
# @Software: PyCharm
# @Desc: 测试Schema模块导入

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    # 测试导入base模块
    print("测试导入base模块...")
    from app.schema.base.user import *
    from app.schema.base.project import *
    from app.schema.base.vars import *
    from app.schema.base.dbConfigSchema import *
    print("base模块导入成功！")
    
    # 测试导入hub模块
    print("\n测试导入hub模块...")
    from app.schema.hub.requirementSchema import *
    from app.schema.hub.testCaseSchema import *
    from app.schema.hub import *
    print("hub模块导入成功！")
    
    # 测试导入interface模块
    print("\n测试导入interface模块...")
    from app.schema.interface.interfaceGlobalSchema import *
    from app.schema.interface.interfaceApiSchema import *
    from app.schema.interface.interfaceCaseSchema import *
    from app.schema.interface.interfaceCaseTaskSchema import *
    from app.schema.interface.interfaceGroupSchema import *
    from app.schema.interface.interfaceResultSchema import *
    from app.schema.interface import *
    print("interface模块导入成功！")
    
    # 测试导入play模块
    print("\n测试导入play模块...")
    from app.schema.play.playCaseSchema import *
    from app.schema.play.playConfigSchema import *
    from app.schema.play.playStepGroupSchema import *
    from app.schema.play.playStepSchema import *
    from app.schema.play.playTaskSchema import *
    from app.schema.play import *
    print("play模块导入成功！")
    
    # 测试导入整个schema模块
    print("\n测试导入整个schema模块...")
    from app.schema import *
    print("整个schema模块导入成功！")
    
    print("\n所有模块导入成功！")
    
except Exception as e:
    print(f"\n导入失败: {e}")
    import traceback
    traceback.print_exc()
