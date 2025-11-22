from app.schema import PageSchema
from pydantic import BaseModel
from typing import List

from enums import ModuleEnum


class InterfaceCaseTaskFieldSchema(BaseModel):
    id: int | None = None
    uid: str | None = None
    title: str | None = None
    desc: str | None = None
    cron: str | None = None
    status: str | None = "WAIT"
    level: str | None = None
    total_cases_num: int | None = 0
    module_id: int | None = None
    project_id: int | None = None
    is_auto: bool | None = None
    retry: int | None = 0
    parallel: int | None = 0
    push_id: int | None = None


class PageInterfaceCaseTaskSchema(InterfaceCaseTaskFieldSchema, PageSchema):
    module_type: int = ModuleEnum.API_TASK


class InsertInterfaceCaseTaskSchema(InterfaceCaseTaskFieldSchema):
    title: str
    desc: str
    level: str
    module_id: int
    project_id: int


class OptionInterfaceCaseTaskSchema(InterfaceCaseTaskFieldSchema):
    id: int


class GetByTaskId(BaseModel):
    taskId: int


class SetTaskAuto(GetByTaskId):
    is_auto: bool


class ExecuteTask(BaseModel):
    task_id: int
    env_id: int
    options: List[str]


class AssocCasesSchema(BaseModel):
    taskId: int
    caseIds: List[int]


class RemoveAssocCasesSchema(BaseModel):
    taskId: int
    caseId: int


class AssocApisSchema(BaseModel):
    taskId: int
    apiIds: List[int]


class RemoveAssocApisSchema(BaseModel):
    taskId: int
    apiId: int


class InterfaceTaskResultSchema(BaseModel):
    status: str | None = None
    result: str | None = None
    startBy: int | None = None
    starterId: int | None = None
    taskId: int | None = None
    runDay: str | List[str] | None = None
    interfaceProjectId: int | None = None
    interfaceModuleId: int | None = None


class InterfaceTaskResultDetailSchema(BaseModel):
    resultId: int


class RemoveInterfaceTaskResultDetailSchema(BaseModel):
    resultId: int


class PageInterfaceTaskResultSchema(InterfaceTaskResultSchema, PageSchema):
    ...
