#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : associationModel
# @Software: PyCharm
# @Desc: 接口模块关联表

from app.model.basic import base
from sqlalchemy import Column, INTEGER, ForeignKey, Index, UniqueConstraint


class InterfaceCaseStepContentAssociation(base):
    """
    用例-步骤关联表
    
    业务含义：一个用例包含多个步骤，step_order 表示执行顺序
    """
    __tablename__ = "interface_case_content_association"
    
    interface_case_id = Column(
        INTEGER, 
        ForeignKey('interface_case.id', ondelete="CASCADE"), 
        primary_key=True
    )
    interface_case_content_id = Column(
        INTEGER, 
        ForeignKey('interface_case_step_content.id', ondelete="CASCADE"),
        primary_key=True
    )
    step_order = Column(INTEGER, nullable=False, default=0, comment="步骤顺序")

    __table_args__ = (
        Index('idx_case_step_order', 'interface_case_id', 'step_order'),
        UniqueConstraint('interface_case_id', 'step_order', name='uq_case_step_order'),
    )

    def __repr__(self):
        return f"<CaseStepAssociation(case_id={self.interface_case_id}, content_id={self.interface_case_content_id}, order={self.step_order})>"


class InterfaceCaseTaskAssociation(base):
    """
    用例-任务关联表
    
    业务含义：一个任务包含多个用例，step_order 表示用例在任务中的执行顺序
    """
    __tablename__ = "interface_case_task_association"
    
    interface_case_id = Column(
        INTEGER, 
        ForeignKey('interface_case.id', ondelete="CASCADE"), 
        primary_key=True
    )
    interface_task_id = Column(
        INTEGER, 
        ForeignKey('interface_task.id', ondelete="CASCADE"), 
        primary_key=True
    )
    step_order = Column(INTEGER, nullable=False, default=0, comment="用例在任务中的顺序")

    __table_args__ = (
        Index('idx_task_case_order', 'interface_task_id', 'step_order'),
        UniqueConstraint('interface_task_id', 'step_order', name='uq_task_case_order'),
    )

    def __repr__(self):
        return f"<CaseTaskAssociation(case_id={self.interface_case_id}, task_id={self.interface_task_id}, order={self.step_order})>"


class InterfaceAPITaskAssociation(base):
    """
    接口-任务关联表
    
    业务含义：一个任务直接包含多个接口（不通过用例），step_order 表示执行顺序
    """
    __tablename__ = "interface_api_task_association"
    
    interface_api_id = Column(
        INTEGER, 
        ForeignKey('interface.id', ondelete="CASCADE"), 
        primary_key=True
    )
    interface_task_id = Column(
        INTEGER, 
        ForeignKey('interface_task.id', ondelete="CASCADE"), 
        primary_key=True
    )
    step_order = Column(INTEGER, nullable=False, default=0, comment="接口在任务中的顺序")

    __table_args__ = (
        Index('idx_task_api_order', 'interface_task_id', 'step_order'),
        UniqueConstraint('interface_task_id', 'step_order', name='uq_task_api_order'),
    )

    def __repr__(self):
        return f"<APITaskAssociation(api_id={self.interface_api_id}, task_id={self.interface_task_id}, order={self.step_order})>"


class InterfaceGroupAPIAssociation(base):
    """
    接口组-接口关联表
    
    业务含义：一个接口组包含多个接口，step_order 表示顺序
    """
    __tablename__ = "interface_group_api_association"
    
    group_id = Column(
        INTEGER, 
        ForeignKey('interface_group.id', ondelete="CASCADE"), 
        primary_key=True
    )
    interface_id = Column(
        INTEGER, 
        ForeignKey('interface.id', ondelete="CASCADE"), 
        primary_key=True
    )
    step_order = Column(INTEGER, nullable=False, default=0, comment="接口在组中的顺序")

    __table_args__ = (
        Index('idx_group_api_order', 'group_id', 'step_order'),
        UniqueConstraint('group_id', 'step_order', name='uq_group_api_order'),
    )

    def __repr__(self):
        return f"<GroupAPIAssociation(group_id={self.group_id}, api_id={self.interface_id}, order={self.step_order})>"


class InterfaceConditionAPIAssociation(base):
    """
    条件-接口关联表
    
    业务含义：条件判断通过后执行的接口列表
    """
    __tablename__ = "interface_condition_association"
    
    condition_id = Column(
        INTEGER, 
        ForeignKey('interface_condition.id', ondelete="CASCADE"), 
        primary_key=True
    )
    interface_api_id = Column(
        INTEGER, 
        ForeignKey('interface.id', ondelete="CASCADE"), 
        primary_key=True
    )
    step_order = Column(INTEGER, nullable=False, default=0, comment="接口执行顺序")

    __table_args__ = (
        Index('idx_condition_api_order', 'condition_id', 'step_order'),
        UniqueConstraint('condition_id', 'step_order', name='uq_condition_api_order'),
    )

    def __repr__(self):
        return f"<ConditionAPIAssociation(condition_id={self.condition_id}, api_id={self.interface_api_id}, order={self.step_order})>"


class InterfaceLoopAPIAssociation(base):
    """
    循环-接口关联表
    
    业务含义：循环体内执行的接口列表
    """
    __tablename__ = "interface_loop_association"
    
    loop_id = Column(
        INTEGER, 
        ForeignKey('interface_loop.id', ondelete="CASCADE"), 
        primary_key=True
    )
    interface_api_id = Column(
        INTEGER, 
        ForeignKey('interface.id', ondelete="CASCADE"), 
        primary_key=True
    )
    step_order = Column(INTEGER, nullable=False, default=0, comment="接口执行顺序")

    __table_args__ = (
        Index('idx_loop_api_order', 'loop_id', 'step_order'),
        UniqueConstraint('loop_id', 'step_order', name='uq_loop_api_order'),
    )

    def __repr__(self):
        return f"<LoopAPIAssociation(loop_id={self.loop_id}, api_id={self.interface_api_id}, order={self.step_order})>"