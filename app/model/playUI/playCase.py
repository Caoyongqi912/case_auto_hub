#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/2
# @Author : cyq
# @File : playCase
# @Software: PyCharm
# @Desc:
from sqlalchemy.orm import relationship

from app.model import BaseModel
from sqlalchemy import Column, String, BOOLEAN, INTEGER, ForeignKey, DATETIME, DATE, TEXT, JSON



class PlayCase(BaseModel):
    """
    UI Case
    """
    __tablename__ = "play_case"
    title = Column(String(40), nullable=True, comment="标题")
    description = Column(String(200), nullable=True, comment="描述")
    status = Column(String(10), nullable=False, comment="状态")
    level = Column(String(10), nullable=False, comment="等级")
    step_num = Column(INTEGER, comment="用例步长")
    module_id = Column(INTEGER, nullable=True, comment="所属模块")
    project_id = Column(INTEGER, ForeignKey("project.id", ondelete="set null"), nullable=True, comment="所属项目")

    @property
    def desc(self):
        if len(self.description) > 10:
            return self.description[:10] + "..."
        return self.description

    def __repr__(self):
        return f"<PlayCase(name='{self.title}', description='{self.desc}')>"

    def __str__(self):
        return f"【{self.title}】 {self.description}"


class PlayCaseResult(BaseModel):
    """
    UI Case Result
    """
    __tablename__ = "play_case_result"
    # ui case 信息
    ui_case_Id = Column(INTEGER, ForeignKey('play_case.id', ondelete='CASCADE'), comment="所属UI用例")
    ui_case_name = Column(String(50), comment="用例名称")
    ui_case_description = Column(String(250), comment="用例描述")
    ui_case_step_num = Column(INTEGER, comment="用例步长")
    ui_case_err_step = Column(INTEGER, nullable=True, comment="失败用例步骤")
    ui_case_err_step_title = Column(String(50), nullable=True, comment="失败用例步骤名称")
    ui_case_err_step_msg = Column(TEXT, nullable=True, comment="失败用例步骤信息")
    ui_case_err_step_pic_path = Column(String(250), nullable=True, comment="失败截图")
    # 运行信息
    asserts_info = Column(JSON, nullable=True, comment="断言信息")
    vars_info = Column(JSON, nullable=True, comment="变量信息")
    running_logs = Column(TEXT, nullable=True, comment="运行日志")
    start_time = Column(DATETIME, comment="开始时间")
    use_time = Column(String(20), comment="用时")
    end_time = Column(DATETIME, comment="结束时间")
    starter_id = Column(INTEGER, comment="运行人ID")
    starter_name = Column(String(20), comment="运行人姓名")
    status = Column(String(10), nullable=False, comment="运行状态 RUNNING DONE")  # "RUNNING","DONE"
    result = Column(String(10), nullable=True, comment="运行结果 SUCCESS FAIL")  # SUCCESS FAIL
    task_result_id = Column(INTEGER, ForeignKey('play_task_result.id', ondelete='CASCADE'),
                            comment="所属TASK", nullable=True)

    # BUG-P-1-2 修复: 之前 ui_case_Id 大写 I 错属性名, Python 习惯 snake_case
    # (跟 task_result_id 一致), 调用方容易写错。修: 加 ui_case_id property
    # (读+写) 兼容到 ui_case_Id 字段, 1-2 release 过渡后彻底改字段名。
    # 为什么用 property 不用 Column rename: rename Column 需 DB migration,
    # 且 mapper._to_dict_impl 走 SQLAlchemy inspect 会拿 column key, 重命名
    # 字段名也要同步改所有 mapper 调用, 改动面大。property 是零迁移 + 向后
    # 兼容最稳的过渡方案。
    @property
    def ui_case_id(self):
        """snake_case 别名: 读 ui_case_Id"""
        return self.ui_case_Id

    @ui_case_id.setter
    def ui_case_id(self, value):
        """snake_case 别名: 写 ui_case_Id"""
        self.ui_case_Id = value


class PlayCaseVariables(BaseModel):
    """
    用例前置变量
    """
    __tablename__ = "play_case_vars"
    key = Column(String(40), nullable=False, unique=True, comment="key")
    value = Column(String(100), nullable=False, comment="value")
    play_case_id = Column(INTEGER, ForeignKey('play_case.id', ondelete="cascade"),
                          nullable=False, comment="所属用例")

    def __repr__(self):
        return (
            f"<PlayCaseVariables(key='{self.key}', value='{self.value}', caseId='{self.play_case_id}')>"
        )
