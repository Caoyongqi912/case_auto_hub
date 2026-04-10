#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : caseResultModel
# @Software: PyCharm
# @Desc: 用例执行结果模型

from datetime import datetime

from sqlalchemy import Column, INTEGER, ForeignKey, String, TEXT, Float, DATETIME
from sqlalchemy.orm import relationship

from app.model import BaseModel


class InterfaceCaseResult(BaseModel):
    """
    用例执行结果
    
    记录整个用例的执行结果，包含所有步骤的汇总信息
    """
    __tablename__ = "interface_case_result"

    # 关联的用例
    case_id = Column(
        INTEGER,
        ForeignKey('interface_case.id', ondelete='CASCADE'),
        nullable=True,
        comment="关联用例ID"
    )

    # 用例信息（冗余便于查询）
    case_title = Column(String(40), nullable=True, comment="用例标题")
    case_desc = Column(String(200), nullable=True, comment="用例描述")
    case_level = Column(String(10), nullable=True, comment="用例等级")

    # 关联的任务结果
    task_result_id = Column(
        INTEGER,
        ForeignKey('interface_task_result.id', ondelete='CASCADE'),
        nullable=True,
        comment="关联任务结果ID"
    )

    # 执行统计
    total_steps = Column(INTEGER, default=0, comment="总步骤数")
    success_steps = Column(INTEGER, default=0, comment="成功步骤数")
    fail_steps = Column(INTEGER, default=0, comment="失败步骤数")

    # 执行进度
    progress = Column(Float, default=0.0, comment="执行进度 0-100")

    # 执行状态
    status = Column(String(10), nullable=True, comment="执行状态 RUNNING/DONE")
    result = Column(String(10), nullable=True, comment="执行结果 SUCCESS/FAIL")

    # 执行时间
    start_time = Column(DATETIME, default=datetime.now, comment="开始时间")
    end_time = Column(DATETIME, nullable=True, comment="结束时间")
    use_time = Column(String(50), nullable=True, comment="耗时")

    # 执行日志
    log = Column(TEXT, nullable=True, comment="执行日志")

    # 执行人
    starter_id = Column(INTEGER, comment="运行人ID")
    starter_name = Column(String(20), comment="运行人姓名")

    # 环境信息
    env_id = Column(INTEGER, nullable=True, comment="运行环境ID")
    env_name = Column(String(250), nullable=True, comment="运行环境名称")

    # 关联关系
    case = relationship("InterfaceCase", foreign_keys=[case_id], lazy="noload")
    task_result = relationship("TaskStepResult", foreign_keys=[task_result_id], lazy="noload")

    # 步骤结果（通过 content_type 多态）
    step_results = relationship(
        "BaseStepResult",
        back_populates="case_result",
        foreign_keys="BaseStepResult.case_result_id",
        cascade="all, delete-orphan"
    )

    # InterfaceResult 列表（通过 APIStepResult.target_result_id 关联）
    interface_results = relationship(
        "InterfaceResult",
        back_populates="case_result",
        foreign_keys="InterfaceResult.case_result_id",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CaseStepResult(id={self.id}, case_id={self.case_id}, result={self.result}, success={self.success_steps}, fail={self.fail_steps})>"
