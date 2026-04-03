


from sqlalchemy import Column, String, ForeignKey, INTEGER

from app.model import BaseModel





class InterfaceGlobalHeader(BaseModel):
    """全局header"""
    __tablename__ = 'interface_global_header'
    key = Column(String(40), nullable=False, unique=True, comment="key")
    value = Column(String(500), nullable=False, comment="value")
    description = Column(String(100), nullable=True, comment="描述")
    project_id = Column(INTEGER, ForeignKey('project.id', ondelete="cascade"),
                        nullable=False, comment="所属项目")

    @property
    def map(self) -> dict:
        return {self.key: self.value}

    def __repr__(self):
        return (
            f"<InterfaceGlobalHeader(key='{self.key}', value='{self.value}' project={self.project_id})>"
        )




class InterfaceGlobalFunc(BaseModel):
    """全局变量函数"""
    __tablename__ = 'interface_global_func'

    label = Column(String(40), nullable=False, unique=True, comment="label")
    value = Column(String(100), nullable=False, comment="value")
    description = Column(String(100), nullable=True, comment="描述")
    demo = Column(String(100), nullable=True, comment="实例")

    def __repr__(self):
        return (
            f"<InterfaceGlobalFunc (label='{self.label}', value='{self.value}', description='{self.description}')"
        )
