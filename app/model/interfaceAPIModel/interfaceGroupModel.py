
from app.model.basic import BaseModel
from sqlalchemy import Column, String, INTEGER, ForeignKey


class InterfaceGroup(BaseModel):
    """
    接口组表
    """
    __tablename__ = 'interface_group'
    interface_group_name = Column(String(40), nullable=False, comment="组名称")
    interface_group_desc = Column(String(40), nullable=False, comment="组描述")
    interface_group_api_num = Column(INTEGER, nullable=False, default=0, comment="接口数量")
    
    module_id = Column(INTEGER, nullable=True, comment="所属模块")
    project_id = Column(INTEGER, ForeignKey("project.id", ondelete='set null'), nullable=True,
                        comment="所属项目")

    def __repr__(self):
        return f"<InterfaceGroup (id={self.id}, name={self.interface_group_name}, desc={self.interface_group_desc}, module_id={self.module_id}, project_id={self.project_id})>"

