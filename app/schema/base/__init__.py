#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/11/21
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: base模块导出

from .user import RegisterUser, RegisterAdmin, LoginUser
from .project import InsertProjectSchema, PageProjectSchema, UpdateProjectSchema
from .vars import AddVarsSchema, UpdateVarsSchema, PageVarsSchema, DeleteVarsSchema
from .dbConfigSchema import InsertDBConfigSchema, SetByDBConfigIdSchema, PageDBConfigSchema
from .pushConfig import InsertPushSchema, OptPushSchema, PagePushSchema
from .apsSchema import *
from .departSchema import InsertDepartmentSchema