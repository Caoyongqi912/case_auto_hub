from sqlalchemy import Column, String, Integer, Index, UniqueConstraint

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
        # 路径唯一: (project_id, module_type, parent_id, title)
        # MySQL 下 NULL 不参与唯一比较, 故多个根分组 (parent_id IS NULL) 可共存
        UniqueConstraint(
            'project_id', 'module_type', 'parent_id', 'title',
            name='uq_module_path',
        ),
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
