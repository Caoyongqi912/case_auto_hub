#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : ui_task# @Software: PyCharm# @description:from sqlalchemy import Column, String, BOOLEAN, INTEGER, ForeignKey, Table, DATETIME, DATE, TEXT, JSONfrom app.model.basic import BaseModelfrom app.model.enum import IntEnumfrom sqlalchemy.orm import relationship, Mappedfrom app.model.ui.association import case_step_associationfrom enums.CaseEnum import *from datetime import datetime, datecase_task_Table = Table("ui_case_tasks_association", BaseModel.metadata,                        Column('ui_case_id', INTEGER, ForeignKey('ui_case.id')),                        Column('ui_task_id', INTEGER, ForeignKey('ui_task.id')),                        Column('case_order', INTEGER))class UICaseMethodOptionModel(BaseModel):    __tablename__ = "ui_case_method"    label = Column(String(255), comment="请求方法名称")    value = Column(String(255), comment="请求方法值")    description = Column(String(255), nullable=True, comment="请求方法描述")    need_locator = Column(INTEGER, nullable=False, comment="需要填写定位器 1 是 2否")    need_value = Column(INTEGER, nullable=False, comment="需要值 1 是 2否")    def __repr__(self):        return (            f"<UICaseMethodOption (label='{self.label}',"            f" value='{self.value}',"            f" description='{self.description}',"            f" need_locator='{self.need_locator}',"            f" need_value='{self.need_value}')>"        )class UIStepSQLModel(BaseModel):    __tablename__ = "ui_case_step_sql"    sql_str = Column(String(500), nullable=False, comment="sql字符串")    description = Column(String(100), nullable=True, comment="描述")    b_or_a = Column(INTEGER, default=False, comment="前后置 1前置 0后置")    go_on = Column(INTEGER, default=1, nullable=False, comment="断言失败继续 1是 0否")    stepId = Column(INTEGER, ForeignKey("ui_case_steps.id"), nullable=False, comment="UI步骤id")    def __repr__(self):        return (            f"<UIStepAPI(SQL ='{self.sql_str}',前置后置='{self.b_or_a}', description='{self.description}', go_on = {self.go_on})>"        )class UIStepAPIModel(BaseModel):    __tablename__ = "ui_case_step_api"    name = Column(String(40), nullable=False, comment="步骤名称")    description = Column(String(100), nullable=True, comment="步骤描述")    url = Column(String(100), nullable=False, comment="接口url")    method = Column(String(40), nullable=False, comment="步骤方法")    params = Column(JSON, nullable=True, comment="请求参数")    body = Column(JSON, nullable=True, comment="请求体")    body_type = Column(INTEGER, nullable=False, comment="是否有请求体 0无 1有")    stepId = Column(INTEGER, ForeignKey("ui_case_steps.id"), nullable=False, comment="UI步骤id")    b_or_a = Column(INTEGER, default=False, comment="前后置 1前置 0后置")    extracts = Column(JSON, nullable=True, comment="提取器")    asserts = Column(JSON, nullable=True, comment="断言")    go_on = Column(INTEGER, default=1, nullable=False, comment="断言失败继续 1是 0否")    env_id = Column(INTEGER, nullable=False, comment="环境ID")    def __repr__(self):        return (            f"<UIStepAPI (name='{self.name}', description='{self.description}', method='{self.method}',"            f"url ='{self.url}' env='{self.env_id}' "            f"stepId='{self.stepId}')>"        )group_step_Table = Table('ui_group_step_association', BaseModel.metadata,                         Column('ui_group_id', INTEGER, ForeignKey('ui_step_group.id')),                         Column('ui_step_id', INTEGER, ForeignKey('ui_case_steps.id')),                         Column('step_order', INTEGER))class UIStepGroupModel(BaseModel):    """    用例公共组    """    __tablename__ = "ui_step_group"    name = Column(String(40), nullable=False, comment="组名称")    description = Column(String(40), nullable=False, comment="组描述")    step_num = Column(INTEGER, nullable=False, default=0, comment="步骤数量")    steps = relationship("UICaseStepsModel",                         secondary=group_step_Table,                         order_by=group_step_Table.c.step_order,                         lazy='dynamic',                         )class UIVariablesModel(BaseModel):    """    用例前置变量    """    __tablename__ = "ui_variables"    key = Column(String(40), nullable=False, unique=True, comment="key")    value = Column(String(100), nullable=False, comment="value")    case_id = Column(INTEGER, ForeignKey('ui_case.id', ondelete="cascade"),                     nullable=False, comment="所属用例")    def __repr__(self):        return (            f"<Variables(key='{self.key}', value='{self.value}', caseId='{self.case_id}')>"        )class UICaseModel(BaseModel):    """    ui case 模型    """    __tablename__ = "ui_case"    title = Column(String(40), nullable=True, comment="标题")    description = Column(String(200), nullable=True, comment="描述")    level = Column(IntEnum(CaseLevel), comment="用例等级")    status = Column(IntEnum(CaseStatus), comment="用例状态")    env_id = Column(INTEGER, nullable=False, comment="环境ID")    step_num = Column(INTEGER, comment="用例步长")    module_id = Column(INTEGER, nullable=True,comment="所属模块")    project_id: Mapped[int] = Column(INTEGER, ForeignKey("project.id",ondelete= 'set null'), nullable=False,                                     comment="所属项目")    results = relationship("UIResultModel",                           backref="ui_result_cases",                           cascade="all, delete-orphan",                           lazy="dynamic")    tasks = relationship("UITaskModel",                         secondary=case_task_Table,                         back_populates="ui_cases")    variables = relationship("UIVariablesModel",                             cascade="all, delete-orphan",                             backref="variables", lazy="dynamic")    steps = relationship("UICaseStepsModel",                         secondary=case_step_association,                         order_by=case_step_association.c.step_order,                         lazy='dynamic',                         cascade='all, delete',                         back_populates="cases")    def __repr__(self):        return f"<UICaseModel(name='{self.title}', description='{self.description}')>"    def __str__(self):        return f"【{self.title}】 {self.description}"class UITaskModel(BaseModel):    """    UI task 模型    """    __tablename__ = "ui_task"    title = Column(String(20), unique=True, nullable=False, comment="任务标题")    description = Column(String(100), nullable=False, comment="任务描述")    is_auto = Column(BOOLEAN, default=False, comment="是否是自动任务")    cron = Column(String(100), nullable=True, comment="corn")    switch = Column(BOOLEAN, default=False, comment="开关")    status = Column(String(20), nullable=True, default="WAIT", comment="任务状体")    level = Column(String(20), nullable=False, comment="任务等级")    ui_case_num = Column(INTEGER, nullable=False, default=0, comment="用例个数")    retry = Column(INTEGER, nullable=False, default=1, comment="重试次数")    taskResults = relationship("UICaseTaskResultBaseModel", backref="task", lazy="dynamic")    ui_cases = relationship("UICaseModel",                            secondary=case_task_Table,                            lazy="dynamic",                            order_by=case_task_Table.c.case_order,                            back_populates="tasks")    module_id = Column(INTEGER,  nullable=False, comment="所属模块")    project_id = Column(INTEGER, ForeignKey("project.id",ondelete= 'set null'), nullable=False,                        comment="所属项目")    push_id = Column(INTEGER, nullable=True, comment="推送方式1企业微信2邮箱")    def __repr__(self):        return (            f"<UITaskModel(name='{self.title}', description='{self.description}', isAuto='{self.is_auto}',"            f" cron='{self.cron}',switch='{self.switch}', status='{self.status}',"            f" level='{self.level}', ui_case_num='{self.ui_case_num}')>"        )class UIResultModel(BaseModel):    """    单个 UI case 运行结果模型    """    __tablename__ = 'ui_case_result'    ui_case_Id = Column(INTEGER, ForeignKey('ui_case.id', ondelete='CASCADE'), comment="所属UI用例")    ui_case_name = Column(String(50), comment="用例名称")    ui_case_description = Column(String(250), comment="用例描述")    ui_case_step_num = Column(INTEGER, comment="用例步长")    ui_case_err_step = Column(INTEGER, nullable=True, comment="失败用例步骤")    ui_case_err_step_title = Column(String(50), nullable=True, comment="失败用例步骤名称")    ui_case_err_step_msg = Column(TEXT, nullable=True, comment="失败用例步骤信息")    ui_case_err_step_pic_path = Column(String(250), nullable=True, comment="失败截图")    asserts_info = Column(JSON, nullable=True, comment="断言信息")    running_logs = Column(TEXT, nullable=True, comment="运行日志")    start_time = Column(DATETIME, comment="开始时间")    use_time = Column(String(20), comment="用时")    end_time = Column(DATETIME, comment="结束时间")    starter_id = Column(INTEGER, comment="运行人ID")    starter_name = Column(String(20), comment="运行人姓名")    status = Column(String(10), nullable=False, comment="运行状态")  # "RUNNING","DONE"    result = Column(String(10), nullable=True, comment="运行结果")  # SUCCESS FAIL    ui_case_base_id = Column(INTEGER, ForeignKey('ui_case_task_result_base.id', ondelete='CASCADE'),                             comment="所属Group", nullable=True)    def __init__(self,                 ui_case_Id: int,                 ui_case_name: str,                 ui_case_description: str,                 ui_case_step_num: int,                 starter_id: int,                 starter_name: str,                 start_time=None,                 status: str = Status.RUNNING,                 ui_case_base_id: int = None):        """          初始化UI测试结果对象。          :param ui_case_Id: UI测试用例的唯一标识符。          :param ui_case_name: UI测试用例的名称。          :param ui_case_description: UI测试用例的描述。          :param ui_case_step_num: UI测试用例包含的步骤数量。          :param startTime: 测试用例开始时间          :param status: 测试用例的执行状态，默认为RUNNING。          :param ui_case_base_id: UI测试用例Task的基础ID，可为空。          """        self.ui_case_Id = ui_case_Id        self.ui_case_name = ui_case_name        self.ui_case_description = ui_case_description        self.ui_case_step_num = ui_case_step_num        self.start_time = start_time        self.status = status        self.ui_case_base_id = ui_case_base_id        self.starter_id = starter_id        self.starter_name = starter_name        self.assertsInfo = []        super().__init__()    def __repr__(self):        return (            f"<UIResult (ui_case_Id='{self.ui_case_Id}', ui_case_name='{self.ui_case_name}', "            f"status='{self.status}',starterName='{self.starter_name}',ui_case_base_id='{self.ui_case_base_id}')> ")class UICaseTaskResultBaseModel(BaseModel):    """    ui task 批量运行基础信息模型    """    __tablename__ = "ui_case_task_result_base"    status = Column(String(10), default="RUNNING", comment="状态")  # "RUNNING","DONE"    result: Mapped[str] = Column(String(10), nullable=True, comment="运行结果")  # SUCCESS FAIL    total_number = Column(INTEGER, comment="总运行数量")    success_number = Column(INTEGER, default=0, comment="成功数量")    fail_number = Column(INTEGER, default=0, comment="失败梳理")    rate_number = Column(INTEGER, default=0, comment="通过率")    start_by = Column(INTEGER, nullable=False, comment="1user 2robot")    starter_name = Column(String(20), nullable=True, comment="运行人名称")    starter_id = Column(INTEGER, nullable=True, comment="运行人ID")    total_usetime = Column(String(20), comment="运行时间")    start_time = Column(DATETIME, default=datetime.now, nullable=True, comment="开始时间")    end_time = Column(DATETIME, nullable=True, comment="结束时间")    task_id = Column(INTEGER, ForeignKey("ui_task.id", ondelete="CASCADE"), nullable=True)    task_uid = Column(String(10), nullable=False, comment="task索引")    task_name = Column(String(20), nullable=True, comment="任务名称")    details = relationship("UIResultModel", backref="base", lazy="dynamic")    run_day = Column(DATE, default=date.today(), comment="运行日期")    project_id = Column(INTEGER, nullable=False, comment="所属项目")    module_id = Column(INTEGER, nullable=True,comment="所属模块")    def __repr__(self):        return (            f"<UICaseTaskResultBaseModel(taskId='{self.task_id}', taskName='{self.task_name}', "            f"runDay='{self.run_day}',status='{self.status}'),result='{self.result})>'")class UIEnvModel(BaseModel):    __tablename__ = "ui_env"    name = Column(String(100), nullable=False, comment="环境名称")    description = Column(String(200), nullable=True, comment="环境描述")    domain = Column(String(100), nullable=False, comment="域名地址")    def __repr__(self):        return f"<UiENV (name='{self.name}', desc='{self.description}', domain='{self.domain}')>"