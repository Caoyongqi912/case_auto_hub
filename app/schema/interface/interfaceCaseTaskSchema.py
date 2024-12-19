from app.schema import PageSchema
from pydantic import BaseModel
from typing import List


class InterfaceCaseTaskFieldSchema(BaseModel):
    id: int | None = None
    uid: str | None = None
    title: str | None = None
    desc: str | None = None
    cron: str | None = None
    status: str | None = "WAIT"
    level: str | None = None
    total_cases_num: int | None = 0
    part_id: int | None = None
    project_id: int | None = None

    is_auto: bool | None = None
    is_send: bool | None = None
    retry: int | None = 0
    send_type: int | None = None
    send_key: str | None = None


class PageInterfaceCaseTaskSchema(InterfaceCaseTaskFieldSchema, PageSchema):
    ...


class InsertInterfaceCaseTaskSchema(InterfaceCaseTaskFieldSchema):
    title: str
    desc: str
    level: str
    part_id: int
    project_id: int


class OptionInterfaceCaseTaskSchema(InterfaceCaseTaskFieldSchema):
    id: int


class GetByTaskId(BaseModel):
    taskId: int


class SetTaskAuto(GetByTaskId):
    is_auto: bool


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
    interfacePartId: int | None = None


class InterfaceTaskResultDetailSchema(BaseModel):
    resultId: int


class RemoveInterfaceTaskResultDetailSchema(BaseModel):
    resultId: int


class PageInterfaceTaskResultSchema(InterfaceTaskResultSchema, PageSchema):
    ...
