
from app.model.basic import BaseModel
from sqlalchemy import Column, String, INTEGER, ForeignKey


class InterfaceCaseVars(BaseModel):
    """
    用例前置变量
    """
    __tablename__ = "interface_case_variables"
    key = Column(String(40), nullable=False, unique=True, comment="key")
    value = Column(String(100), nullable=False, comment="value")
    case_id = Column(INTEGER, ForeignKey('interface_case.id', ondelete="cascade"),
                     nullable=False, comment="所属用例")

    def __repr__(self):
        return (
            f"<InterfaceCaseVars(key='{self.key}', value='{self.value}', caseId='{self.case_id}')>"
        )   