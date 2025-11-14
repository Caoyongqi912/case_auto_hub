from typing import List

from app.schema import PageSchema
from pydantic import BaseModel

__all__ = [
    "InterfaceCaseSchema",
    "InsertInterfaceCaseBaseInfoSchema",
    "OptionInterfaceCaseSchema",
    "ExecuteInterfaceCaseSchema",
    "PageInterfaceCaseSchema",
    "AssociationApisSchema",
    "AddInterfaceCaseCommonGROUPSchema",
    "AddInterfaceApi2Case",
    "RemoveCaseContentSchema",
    "CopyContentStepSchema",
    "ReorderContentStepSchema",
    "AssociationConditionSchema",
    "UpdateConditionSchema",
    "AssociationConditionAPISchema",
    "RemoveAssociationConditionAPISchema",
    "UpdateCaseContentStepSchema",
    "AddCaseContentStepSchema",
    "UpdateCaseContentAssert",
    "AssociationApiSchema"
]

from enums import ModuleEnum


class InterfaceCaseSchema(BaseModel):
    id: int | None = None
    uid: str | None = None
    title: str | None = None
    desc: str | None = None
    level: str | None = None
    status: str | None = None
    module_id: int | None = None
    project_id: int | None = None
    error_stop: int | None = None


class InsertInterfaceCaseBaseInfoSchema(InterfaceCaseSchema):
    title: str
    desc: str
    level: str
    status: str
    module_id: int
    project_id: int


class OptionInterfaceCaseSchema(InterfaceCaseSchema):
    id: int


class ExecuteInterfaceCaseSchema(InterfaceCaseSchema):
    caseId: int


class PageInterfaceCaseSchema(InterfaceCaseSchema, PageSchema):
    module_type: int = ModuleEnum.API_CASE


class AssociationApisSchema(BaseModel):
    interface_case_id: int
    interface_id_list: List[int]


class AssociationApiSchema(BaseModel):
    case_id: int
    module_id: int
    project_id: int


class UpdateCaseContentAssert(BaseModel):
    id: int
    assert_key: str | None
    assert_value: str | None
    assert_type: int | None = None


class AddInterfaceCaseCommonGROUPSchema(BaseModel):
    interface_case_id: int
    api_group_id_list: List[int]


class AddInterfaceApi2Case(BaseModel):
    caseId: int
    apiId: int


class RemoveCaseContentSchema(BaseModel):
    case_id: int
    content_step_id: int


class ReorderContentStepSchema(BaseModel):
    case_id: int
    content_step_order: List[int]


class AssociationConditionSchema(BaseModel):
    interface_case_id: int


class AssociationConditionAPISchema(BaseModel):
    condition_id: int
    interface_id_list: List[int]


class RemoveAssociationConditionAPISchema(BaseModel):
    condition_id: int
    interface_id: int


class ConditionAddGroups(BaseModel):
    condition_api_id: int
    group_id_list: List[int]


class ConditionAddCommons(BaseModel):
    condition_api_id: int
    common_api_list: List[int]


class CopyContentStepSchema(BaseModel):
    case_id: int
    content_id: int


class UpdateConditionSchema(BaseModel):
    id: int
    condition_key: str
    condition_value: str | None = None
    condition_operator: int


class UpdateCaseContentStepSchema(BaseModel):
    id: int
    content_name: str | None = None
    enable: bool = None
    api_wait_time: int = None
    api_script_text: str = None


class AddCaseContentStepSchema(BaseModel):
    case_id: int
    content_type: int
    enable: bool = None
    api_wait_time: int = None
    api_script_text: str = None
