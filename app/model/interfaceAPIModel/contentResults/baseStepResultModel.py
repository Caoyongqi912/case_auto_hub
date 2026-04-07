#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : baseStepResultModel
# @Software: PyCharm
# @Desc: 用例步骤执行结果基类 - Joined Table Inheritance

from abc import abstractmethod
from datetime import datetime

from sqlalchemy import Column, INTEGER, ForeignKey, DATETIME, String, Boolean
from sqlalchemy.orm import relationship

from app.model import BaseModel


def step_result_id_column():
    """子表主键生成器"""
    return Column(
        INTEGER,
        ForeignKey('interface_case_content_result.id', ondelete='CASCADE'),
        primary_key=True
    )


class BaseStepResult(BaseModel):
    """
    步骤执行结果基类 - Joined Table Inheritance
    
    设计说明：
    - content_name/content_desc 通过 relationship 从原始步骤获取，不存储冗余数据
    - 子类通过 @property 提供虚拟的 content_name, content_desc
    - 子类存储各自特有的执行结果字段
    """
    __tablename__ = "interface_case_content_result"

    # 外键关联到用例结果
    case_result_id = Column(
        INTEGER,
        ForeignKey('interface_case_result.id', ondelete='CASCADE'),
        nullable=True,
        comment="所属用例结果ID"
    )

    # 关联的步骤内容ID（用于查询原始步骤）
    content_id = Column(
        INTEGER,
        ForeignKey('interface_case_step_content.id', ondelete='SET NULL'),
        nullable=True,
        comment="关联的步骤内容ID"
    )

    # 步骤类型 - 用于多态
    content_type = Column(INTEGER, nullable=False, index=True, comment="步骤类型")

    # 执行顺序
    step_order = Column(INTEGER, nullable=False, default=0, comment="执行顺序")

    # 执行状态
    is_success = Column(Boolean, default=False, comment="执行结果")

    # 执行时间
    start_time = Column(DATETIME, default=datetime.now, comment="开始时间")
    end_time = Column(DATETIME, nullable=True, comment="结束时间")
    use_time = Column(String(50), nullable=True, comment="耗时")

    # 执行人
    starter_id = Column(INTEGER, comment="运行人ID")
    starter_name = Column(String(20), comment="运行人姓名")

    # 错误信息
    error_message = Column(String(500), nullable=True, comment="错误信息")

    # relationship
    content = relationship(
        "InterfaceCaseContents",
        foreign_keys=[content_id],
        lazy="noload"
    )

    case_result = relationship(
        "CaseStepResult",
        foreign_keys=[case_result_id],
        back_populates="step_results",
        lazy="noload"
    )

    __mapper_args__ = {
        'polymorphic_on': content_type,
        'polymorphic_identity': None,
        'with_polymorphic': '*',
    }

    @property
    @abstractmethod
    def content_name(self) -> str:
        """步骤名称 - 由子类实现"""
        pass

    @property
    @abstractmethod
    def content_desc(self) -> str:
        """步骤描述 - 由子类实现"""
        pass

    def __repr__(self):
        return f"<BaseStepResult(id={self.id}, content_id={self.content_id}, type={self.content_type}, success={self.is_success})>"
