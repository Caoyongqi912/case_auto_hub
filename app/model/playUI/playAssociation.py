#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/2
# @Author : cyq
# @File : playAssociation
# @Software: PyCharm
# @Desc:
from sqlalchemy import Column, INTEGER, ForeignKey
from sqlalchemy.orm import relationship

from app.model.basic import base

__all__ = [ "PlayCaseStepContentAssociation", "PlayTaskCasesAssociation","PlayGroupStepAssociation"]



class PlayCaseStepContentAssociation(base):
    """
    case_steps_content 关联表
    """
    __tablename__ = "play_case_step_content_association"

    play_case_id = Column(INTEGER, ForeignKey('play_case.id',ondelete="CASCADE"), primary_key=True)
    play_step_content_id = Column(INTEGER, ForeignKey('play_step_content.id',ondelete="CASCADE"), primary_key=True)
    step_order = Column(INTEGER)

    def __repr__(self):
        return (
            f"<PlayCaseStepContentAssociation(play_case_id={self.play_case_id},"
            f" play_step_content_id={self.play_step_content_id}, "
            f"step_order={self.step_order})>")


class PlayTaskCasesAssociation(base):
    """
    task_cases 关联表
    """
    __tablename__ = "play_task_cases_association"

    play_case_id = Column(INTEGER, ForeignKey('play_case.id'), primary_key=True)
    play_task_id = Column(INTEGER, ForeignKey('play_task.id', ondelete="CASCADE"), primary_key=True)
    case_order = Column(INTEGER)

    def __repr__(self):
        return (f"<PlayTaskCasesAssociation(play_case_id={self.play_case_id},play_task_id={self.play_task_id}"
                f"step_order={self.case_order})>")


class PlayGroupStepAssociation(base):
    """
    接口 接口组 中间表
    """
    __tablename__ = "play_group_step_association"

    group_id = Column(INTEGER, ForeignKey('play_group.id'), primary_key=True)
    play_step_id = Column(INTEGER, ForeignKey('play_steps.id'), primary_key=True)
    step_order = Column(INTEGER)

    def __repr__(self):
        return f"<PlayGroupStepAssociation(group_id={self.group_id}, play_step={self.play_step_id}, step_order={self.step_order}) />"
