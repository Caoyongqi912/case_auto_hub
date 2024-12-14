#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceModel# @Software: PyCharm# @Desc:from app.model.basic import BaseModelfrom sqlalchemy import Column, String, INTEGER, ForeignKey, JSON, Table, BOOLEANfrom sqlalchemy.orm import relationship# 接口与用例关联表inter_case_association = Table('interface_case_association', BaseModel.metadata,                               Column('interface_id', INTEGER, ForeignKey('interface.id')),                               Column('inter_case_id', INTEGER, ForeignKey('interface_case.id')),                               Column('step_order', INTEGER)  # 存储排序顺序                               )# 任务与用例关联表case_task_association = Table('interface_task_association', BaseModel.metadata,                              Column('inter_case_id', INTEGER, ForeignKey('interface_case.id')),                              Column('task_id', INTEGER, ForeignKey('interface_task.id')),                              Column('step_order', INTEGER)  # 存储排序顺序                              )# 任务与api关联表api_task_association = Table('interface_api_task_association', BaseModel.metadata,                             Column('api_id', INTEGER, ForeignKey('interface.id')),                             Column('task_id', INTEGER, ForeignKey('interface_task.id')),                             Column('step_order', INTEGER)  # 存储排序顺序                             )class InterfaceModel(BaseModel):    """    接口表    """    __tablename__ = 'interface'    name = Column(String(40), nullable=False, comment="接口名称")    desc = Column(String(200), nullable=False, comment="接口描述")    status = Column(String(10), nullable=False, comment="接口状态")    level = Column(String(10), nullable=False, comment="接口等级")    url = Column(String(500), nullable=False, comment="接口地址")    method = Column(String(10), nullable=False, comment="请求类型")    params = Column(JSON, nullable=True, comment="请求参数")    headers = Column(JSON, nullable=True, comment="请求头")    bodyType = Column(INTEGER, nullable=False, comment="0无 1JSON 2data 3..")    body = Column(JSON, nullable=True, comment="请求体")    data = Column(JSON, nullable=True, comment="表单")    asserts = Column(JSON, nullable=True, comment="断言")    extracts = Column(JSON, nullable=True, comment="响应提取")    follow_redirects = Column(INTEGER, default=0, comment="是否重定向")    connectTimeout = Column(INTEGER, nullable=True, default=6, comment="连接超时")    responseTimeout = Column(INTEGER, nullable=True, default=6, comment="请求超时")    beforeScript = Column(String(500), nullable=True, comment="前置脚本")    afterScript = Column(String(500), nullable=True, comment="后置脚本")    beforeParams = Column(JSON, nullable=True, comment="前置参数")    project_id = Column(INTEGER, ForeignKey("project.id", ondelete="set null"), nullable=True, comment="所属项目")    part_id = Column(INTEGER, ForeignKey("part.id", ondelete="set null"), nullable=True, comment="所属模块")    part_root_id = Column(INTEGER, ForeignKey("part.id", ondelete="set null"), nullable=True, comment="所属Root模块")    env_id = Column(INTEGER, ForeignKey("env.id", ondelete="set null"), nullable=True, comment="所属环境")    is_common = Column(INTEGER, default=1, comment="是否公共API")    enable = Column(INTEGER, default=1, comment="调试1开启0关闭")    @property    def description(self):        if len(self.desc) > 10:            return self.desc[:10] + "..."        return self.desc    def __repr__(self):        return f"API name=\"{self.name}\" desc=\"{self.description}\" method=\"{self.method}\" ..."class InterFaceCaseModel(BaseModel):    """    接口用例    """    __tablename__ = 'interface_case'    title = Column(String(40), nullable=True, comment="标题")    desc = Column(String(200), nullable=True, comment="描述")    http = Column(String(10), default="HTTP", comment='请求类型')    level = Column(String(10), comment="接口用例等级")    status = Column(String(10), comment="接口用例状态")    apiNum = Column(INTEGER, default=0, comment="接口数量")    part_id = Column(INTEGER, ForeignKey('part.id'), nullable=True,                     comment="所属模块")    project_id = Column(INTEGER, ForeignKey("project.id"), nullable=True,                        comment="所属产品")    error_stop = Column(INTEGER, default=0, comment="错误停止 1是 0否")    # results = relationship("InterfaceResultModel", backref="interface", lazy="dynamic")    interfaces = relationship("InterfaceModel",                              secondary=inter_case_association,                              order_by=inter_case_association.c.step_order,                              lazy='dynamic')    def __repr__(self):        return f"<CaseResult(id={self.id}, uid={self.uid} title={self.title} status={self.status})>"class InterfaceTask(BaseModel):    """    接口任务    """    __tablename__ = 'interface_task'    title = Column(String(20), unique=True, nullable=False, comment="任务标题")    desc = Column(String(100), nullable=False, comment="任务描述")    switch = Column(BOOLEAN, default=False, comment="开关")    status = Column(String(20), nullable=True, default="WAIT", comment="任务状体")    level = Column(String(20), nullable=False, comment="任务等级")    total_cases_num = Column(INTEGER, nullable=False, default=0, comment='cases用例个数')    total_apis_num = Column(INTEGER, nullable=False, default=0, comment='api用例个数')    part_id = Column(INTEGER, ForeignKey('part.id'), nullable=True,                     comment="所属模块")    project_id = Column(INTEGER, ForeignKey("project.id"), nullable=True,                        comment="所属产品")    is_auto = Column(INTEGER, default=0, comment="定时执行1是0否")    cron = Column(String(29), nullable=True, comment="corn")    retry = Column(INTEGER, default=0, comment='重试次数')    is_send = Column(INTEGER, default=0, comment="结果推送")    send_type = Column(INTEGER, nullable=True, comment="推送方式1企业微信2邮箱")    send_key = Column(String(50), nullable=True, comment="推送key")    def __repr__(self):        return f"<InterfaceTask(id={self.id}, uid={self.uid} title={self.title})>"