from app.model.basic import BaseModel
from sqlalchemy import Column, INTEGER, String, ForeignKey, Index,Date


class CasePlan(BaseModel):
    """测试计划"""
    __tablename__ = "case_plan"

    project_id = Column(INTEGER,
                        ForeignKey('project.id', ondelete='CASCADE'),
                        nullable=False, index=True, comment="项目所属")
    plan_name = Column(String(50), nullable=False, comment="计划名称")
    plan_description = Column(String(200), nullable=True, comment="计划描述")

    plan_status = Column(INTEGER, default=0, comment="计划状态 0:进行中 1:已完成")
    plan_phase = Column(String(20), nullable=True, comment="执行阶段 准备/一轮/二轮/回归/验收")
    plan_mark = Column(String(200), nullable=True, comment="计划备注")

    charge_id = Column(INTEGER, nullable=False, comment="负责人ID")
    charge_name = Column(String(20), nullable=False, comment="负责人姓名")

    plan_start_time = Column(Date, nullable=True, comment="计划开始时间")
    plan_end_time = Column(Date, nullable=True, comment="计划结束时间")

    __table_args__ = (
        Index('idx_plan_status', 'plan_status'),
    )

    def __repr__(self):
        return f"CasePlan(id={self.id}, project_id={self.project_id}, plan_name={self.plan_name}, plan_status={self.plan_status}, charge_id={self.charge_id})"
