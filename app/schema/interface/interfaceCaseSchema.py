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

from app.schema.interface.interfaceApiSchema import IBeforeSqlExtracts
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


class InsertInterfaceCaseBaseInfoSchema(InterfaceCaseSchema):
    title: str
    desc: str
    level: str
    status: str
    module_id: int
    project_id: int


class OptionInterfaceCaseSchema(InterfaceCaseSchema):
    id: int


class ExecuteInterfaceCaseSchema(BaseModel):
    case_id: int
    env_id: int
    error_stop: bool


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
    assert_key: str
    assert_value: str
    assert_type: int


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


class UpdateDBSchema(BaseModel):
    id: int
    sql_text: str | None = None
    sql_extracts: List[IBeforeSqlExtracts] | None = None
    db_id: int | None = None


class UpdateCaseContentStepSchema(BaseModel):
    id: int
    content_name: str | None = None
    enable: bool = None
    api_wait_time: int = None
    api_script_text: str = None
    api_assert_list: List[UpdateCaseContentAssert] = None


class AddCaseContentStepSchema(BaseModel):
    case_id: int
    content_type: int
    enable: bool = None
    api_wait_time: int = None
    api_script_text: str = None
    api_assert_list: List[UpdateCaseContentAssert] = None
