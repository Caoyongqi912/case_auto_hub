from sqlalchemy import Column, String, Integer, Index

from app.model import BaseModel


class Module(BaseModel):
    __tablename__ = 'module'

    title = Column(String(50), comment="用例模块")
    parent_id = Column(Integer, comment="父级模块")
    project_id = Column(Integer, comment="项目id")
    module_type = Column(Integer, comment="模块类型")

    # 在 Module 模型中添加
    __table_args__ = (
        Index('idx_parent_id', 'parent_id'),
        Index('idx_module_type', 'module_type'),
    )
    @property
    def map(self):
        return {
            "key": self.id,
            "title": self.title,
            "parent_id": self.parent_id,
            "project_id": self.project_id,
            "module_type": self.module_type
        }

    def __repr__(self):
        return "<Module(title='%s', parent_id='%s', project_id='%s')>" % (
            self.title, self.parent_id, self.project_id
        )
