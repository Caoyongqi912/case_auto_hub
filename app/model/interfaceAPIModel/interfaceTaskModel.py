from app.model.basic import BaseModel
from sqlalchemy import Column, String, INTEGER, ForeignKey, JSON, BOOLEAN, Text



class InterfaceTask(BaseModel):
    """
    接口任务
    """
    __tablename__ = "interface_task"
    
    interface_task_title = Column(String(20), unique=True, nullable=False, comment="任务标题")
    interface_task_desc = Column(String(100), nullable=False, comment="任务描述")
    interface_task_switch = Column(BOOLEAN, default=False, comment="开关")
    interface_task_status = Column(String(20), nullable=True, default="WAIT", comment="任务状体")
    interface_task_level = Column(String(20), nullable=False, comment="任务等级")
    interface_task_total_cases_num = Column(INTEGER, nullable=False, default=0, comment='cases用例个数')
    interface_task_total_apis_num = Column(INTEGER, nullable=False, default=0, comment='api用例个数')

    project_id = Column(INTEGER, ForeignKey("project.id"), nullable=True,
                        comment="所属产品")
    module_id = Column(INTEGER, nullable=True, comment="所属模块")
    
    
    def __repr__(self):
        return f"InterfaceTask id=\"{self.id}\" uid=\"{self.uid}\" name=\"{self.interface_task_title}\" desc=\"{self.interface_task_desc}\" method=\"{self.interface_task_switch}\" project={self.project_id} module={self.module_id}..."   
