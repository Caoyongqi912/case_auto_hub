

from app.model.base import BaseModel
from sqlalchemy import Column, INTEGER, String, Float, ForeignKey

class CasePlan(BaseModel):
    """测试计划"""
    __tablename__ = "case_plan"
    
    project_id = Column(INTEGER,
                        ForeignKey('project.id', ondelete='CASCADE'),
                        nullable=False, comment="项目所属")
    plan_name = Column(String(50), nullable=False, comment="计划名称")
    plan_description = Column(String(200), nullable=True, comment="计划描述")

    plan_status = Column(String(10), nullable=False, comment="状态")  # "RUNNING","DONE"
    plan_completion_rate = Column(Float, nullable=True, comment="完成率")
    plan_mark = Column(String(200), nullable=True, comment="计划备注")
    
    
    charge_id = Column(INTEGER, nullable=False, comment="负责人")
    charge_name = Column(String(20), nullable=False, comment="负责人姓名")

    
    plan_start_time = Column(String(20), nullable=False, comment="计划开始时间")
    plan_end_time = Column(String(20), nullable=False, comment="计划结束时间")
    
    def __repr__(self):
        return f"CasePlan(id={self.id}, project_id={self.project_id}, plan_name={self.plan_name},  plan_status={self.plan_status},  charge_id={self.charge_id}, charge_name={self.charge_name})"
        
        
