#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : taskResultModel
# @Software: PyCharm
# @Desc: 任务执行结果模型

from datetime import datetime

from sqlalchemy import Column, INTEGER, ForeignKey, String, Float, DATETIME, DATE
from sqlalchemy.orm import relationship

from app.model import BaseModel


class TaskStepResult(BaseModel):
    """
    任务执行结果
    
    记录整个任务的执行结果，包含所有用例的汇总信息
    """
    __tablename__ = "interface_task_result"

    # 关联的任务
    task_id = Column(
        INTEGER,
        ForeignKey('interface_task.id', ondelete='CASCADE'),
        nullable=True,
        comment="关联任务ID"
    )

    # 任务信息（冗余便于查询）
    task_name = Column(String(20), nullable=True, comment="任务名称")
    task_uid = Column(String(10), nullable=True, comment="任务Uid")
    task_desc = Column(String(100), nullable=True, comment="任务描述")

    # 执行统计
    total_cases = Column(INTEGER, default=0, comment="总用例数")
    success_cases = Column(INTEGER, default=0, comment="成功用例数")
    fail_cases = Column(INTEGER, default=0, comment="失败用例数")

    total_apis = Column(INTEGER, default=0, comment="总接口数")
    success_apis = Column(INTEGER, default=0, comment="成功接口数")
    fail_apis = Column(INTEGER, default=0, comment="失败接口数")

    # 执行进度
    progress = Column(Float, default=0.0, comment="执行进度 0-100")

    # 执行状态
    status = Column(String(10), default="RUNNING", comment="执行状态 RUNNING/DONE")
    result = Column(String(10), nullable=True, comment="执行结果 SUCCESS/FAIL")

    # 执行时间
    start_time = Column(DATETIME, default=datetime.now, comment="开始时间")
    end_time = Column(DATETIME, nullable=True, comment="结束时间")
    total_use_time = Column(String(20), nullable=True, comment="总耗时")

    # 启动方式
    start_by = Column(INTEGER, nullable=True, comment="启动方式 1用户 2Jenkins 3Robot 4Celery")

    # 执行人
    starter_id = Column(INTEGER, nullable=True, comment="运行人ID")
    starter_name = Column(String(20), nullable=True, comment="运行人姓名")

    # 关联信息
    project_id = Column(INTEGER, nullable=True, comment="所属项目")
    module_id = Column(INTEGER, nullable=True, comment="所属模块")
    env_id = Column(INTEGER, nullable=True, comment="运行环境ID")
    env_name = Column(String(250), nullable=True, comment="运行环境名称")

    # 运行日期
    run_day = Column(DATE, default=datetime.now().date, comment="运行日期")

    # 关联关系
    task = relationship("InterfaceTask", foreign_keys=[task_id], lazy="noload")

    # 用例结果列表
    case_results = relationship(
        "CaseStepResult",
        back_populates="task_result",
        foreign_keys="CaseStepResult.task_result_id",
        cascade="all, delete-orphan"
    )

    @property
    def notify(self) -> dict:
        """通知信息"""
        return {
            "starter": self.starter_name,
            "result_id": self.id,
            "result_uid": self.uid,
            "task_name": self.task_name,
            "task_id": self.task_id,
            "task_uid": self.task_uid,
            "result": self.result,
            "total": self.total_cases,
            "success": self.success_cases,
            "fail": self.fail_cases,
            "use_time": self.total_use_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "project_id": self.project_id
        }

    def __repr__(self):
        return f"<TaskStepResult(id={self.id}, task_id={self.task_id}, status={self.status}, result={self.result})>"
