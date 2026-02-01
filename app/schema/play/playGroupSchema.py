from typing import Optional, List

from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum
from app.schema.play.playStepSchema import InsertPlayStepSchema


class InsertPlayGroupSchema(BaseModel):
    """插入play步骤模型"""
    name: str = Field(..., description="名称")
    description: str = Field(..., description="描述")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class EditPlayStepSchema(BaseModel):
    """编辑play步骤模型"""
    id: int = Field(..., description="ID")
    description: Optional[str] = Field(None, description="描述")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class GetPlayStepGroupByIdSchema(BaseModel):
    """根据ID获取play步骤组模型"""
    group_id: int = Field(..., description="步骤ID")


class InsertPlayGroupStepSchema(InsertPlayStepSchema):
    group_id: int = Field(..., description="步骤组ID")


class CopyRemovePlayGroupStepSchema(BaseModel):
    """复制删除play步骤模型"""
    group_id: int = Field(..., description="步骤组ID")
    step_id: int = Field(..., description="步骤ID")


class PagePlayGroupSchema(PageSchema):
    """play步骤分页查询模型"""
    uid: Optional[str] = Field(None, title="步骤id", description="步骤ID")
    name: Optional[str] = Field(None, title="步骤名称", description="步骤名称")
    module_id: Optional[int] = Field(None, title="模块id", description="模块ID")
    project_id: Optional[int] = Field(None, title="项目id", description="项目ID")
    module_type: int = ModuleEnum.UI_STEP


class ReOrderPlayStepsSchema(BaseModel):
    """重排序play子步骤模型"""
    group_id: int = Field(..., description="组ID")
    step_list: List[int] = Field(..., description="步骤ID列表")

class AssociationPlayGroupStepSchema(BaseModel):
    """case 关联 公共 step"""
    quote: bool = Field(..., description="是否引用")
    group_id: int = Field(..., description="用例ID")
    play_step_id_list: List[int] = Field(..., description="步骤Id")



__all__ = [
    "InsertPlayGroupSchema",
    "EditPlayStepSchema",
    "GetPlayStepGroupByIdSchema",
    "InsertPlayGroupStepSchema",
    "CopyRemovePlayGroupStepSchema",
    "PagePlayGroupSchema",
    "ReOrderPlayStepsSchema",
    "AssociationPlayGroupStepSchema"
]
