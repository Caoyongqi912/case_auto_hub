from app.model.basic import  base
from sqlalchemy import Column, INTEGER, ForeignKey


class InterfaceCaseStepContentAssociation(base):
    """
    接口 业务用例 步骤 中间表
    """
    __tablename__ = "interface_case_content_association"
    interface_case_id = Column(INTEGER, ForeignKey('interface_case.id', ondelete="CASCADE"), primary_key=True)
    interface_case_content_id = Column(INTEGER, ForeignKey('interface_case_step_content.id', ondelete="CASCADE"),
                                       primary_key=True)
    step_order = Column(INTEGER)

    def __repr__(self):
        return (f"<InterfaceCaseStepAssociation(interface_case_id={self.interface_case_id},"
                f" interface_case_content_id={self.interface_case_content_id},"
                f" step_order={self.step_order}) />")


class CaseTaskAssociation(base):
    """
    业务用例与任务中间表
    """
    __tablename__ = "interface_task_association"

    inter_case_id = Column(INTEGER, ForeignKey('interface_case.id',ondelete="CASCADE"), primary_key=True)
    task_id = Column(INTEGER, ForeignKey('interface_task.id',ondelete="CASCADE"), primary_key=True)
    step_order = Column(INTEGER)

    def __repr__(self):
        return f"<CaseTaskAssociation(inter_case_id={self.inter_case_id}, task_id={self.task_id}, step_order={self.step_order}) />"


#
class ApiTaskAssociation(base):
    """
    接口 任务中间表
    """
    __tablename__ = "interface_api_task_association"

    api_id = Column(INTEGER, ForeignKey('interface.id',ondelete="CASCADE"), primary_key=True)
    task_id = Column(INTEGER, ForeignKey('interface_task.id',ondelete="CASCADE"), primary_key=True)
    step_order = Column(INTEGER)

    def __repr__(self):
        return f"<ApiTaskAssociation(api_id={self.api_id}, task_id={self.task_id}, step_order={self.step_order}) />"


class GroupApiAssociation(base):
    """
    接口 接口组 中间表
    """
    __tablename__ = "interface_group_api_association"

    api_group_id = Column(INTEGER, ForeignKey('interface_group.id'), primary_key=True)
    api_id = Column(INTEGER, ForeignKey('interface.id'), primary_key=True)
    step_order = Column(INTEGER)

    def __repr__(self):
        return f"<GroupApiAssociation(api_group_id={self.api_group_id}, api_id={self.api_id}, step_order={self.step_order}) />"


class ConditionAPIAssociation(base):
    """
    接口 条件 中间表

    """
    __tablename__ = "interface_condition_association"
    condition_id = Column(INTEGER, ForeignKey('interface_condition.id', ondelete="CASCADE"), primary_key=True)
    api_id = Column(INTEGER, ForeignKey('interface.id', ondelete="CASCADE"), primary_key=True)
    step_order = Column(INTEGER)

    def __repr__(self):
        return f"<ConditionAPIAssociation(condition_id={self.condition_id}, api_id={self.api_id}, step_order={self.step_order}) />"




class LoopAPIAssociation(base):
    """
    接口 Loop 关系
    """
    __tablename__ = "interface_loop_association"

    loop_id = Column(INTEGER, ForeignKey('interface_loop.id', ondelete="CASCADE"), primary_key=True)
    api_id = Column(INTEGER, ForeignKey('interface.id', ondelete="CASCADE"), primary_key=True)
    step_order = Column(INTEGER)

    def __repr__(self):
        return f"<LoopAPIAssociation(loop_id={self.loop_id}, api_id={self.api_id}, step_order={self.step_order}) />"

