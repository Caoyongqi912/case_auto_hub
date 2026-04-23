from app.model.basic import BaseModel
from sqlalchemy import Column, String



class InterfaceScriptDesc(BaseModel):
    __tablename__ = 'interface_scriptDesc'

    title = Column(String(100), nullable=False, comment="标题")
    subTitle = Column(String(100), nullable=True, comment="副标题")
    args = Column(String(100), nullable=True, comment="参数")
    desc = Column(String(100), nullable=True, comment="描述")
    example = Column(String(200), nullable=True, comment="例子")
    returnContent = Column(String(200), nullable=True, comment="返回")
