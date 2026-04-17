#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : interfaceModel
# @Software: PyCharm
# @Desc:

from app.model.basic import BaseModel
from sqlalchemy import Column, String, INTEGER, ForeignKey, JSON, Text


class Interface(BaseModel):
    """
    接口
    """
    __tablename__ = "interface"
    interface_name = Column(String(100), nullable=False, comment="接口名称")
    interface_desc = Column(Text, nullable=True, comment="接口描述")
    interface_status = Column(String(10), nullable=True, comment="接口状态")
    interface_level = Column(String(10), nullable=True, comment="接口等级")
    interface_url = Column(String(500), nullable=True, comment="接口地址")
    interface_method = Column(String(10), nullable=True, comment="请求类型")
    interface_params = Column(JSON, nullable=True, comment="请求参数")
    interface_headers = Column(JSON, nullable=True, comment="请求头")
    interface_body_type = Column(INTEGER, nullable=False, comment="0无 1raw 2data 3raw")
    interface_raw_type = Column(String(10), nullable=True, comment="raw 类型 json text")


    interface_auth_type = Column(INTEGER, nullable=True,default=1, comment="认证类型 1不认证 2.")
    interface_auth=Column(JSON, nullable=True, comment="认证信息")

    interface_body = Column(JSON, nullable=True, comment="请求体")
    interface_data = Column(JSON, nullable=True, comment="表单")
    interface_asserts = Column(JSON, nullable=True, comment="断言")
    interface_extracts = Column(JSON, nullable=True, comment="响应提取")
    interface_follow_redirects = Column(INTEGER, default=0, comment="是否重定向")
    interface_connect_timeout = Column(INTEGER, nullable=True, default=6, comment="连接超时")
    interface_response_timeout = Column(INTEGER, nullable=True, default=6, comment="请求超时")
    interface_before_script = Column(String(500), nullable=True, comment="前置脚本")
    interface_before_db_id = Column(INTEGER, nullable=True, comment="前置数据库ID")
    interface_before_sql = Column(String(500), nullable=True, comment="前置sql")
    interface_before_sql_extracts = Column(JSON, nullable=True, comment="SQL提取")
    interface_after_script = Column(String(500), nullable=True, comment="后置脚本")
    interface_before_params = Column(JSON, nullable=True, comment="前置参数")

    is_common = Column(INTEGER, default=1, comment="是否公共API")
    env_id = Column(INTEGER, nullable=True, comment="所属环境")
    module_id = Column(INTEGER, nullable=True, comment="所属模块")
    project_id = Column(INTEGER, ForeignKey("project.id", ondelete="set null"), nullable=True, comment="所属项目")

    
    @property
    def desc(self):
        if len(self.interface_desc) > 10:
            return self.interface_desc[:10] + "..."
        return self.interface_desc

    def __repr__(self):
        return f"Interface  id=\"{self.id}\" uid=\"{self.uid}\" name=\"{self.interface_name}\" desc=\"{self.interface_desc}\" method=\"{self.interface_method}\" project={self.project_id} module={self.module_id}..."