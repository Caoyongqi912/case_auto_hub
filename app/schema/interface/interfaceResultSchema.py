from typing import List

from app.schema import PageSchema
from pydantic import BaseModel


class BaseSchema(BaseModel):
    id: int | None = None
    uid: str | None = None


class RemoveAllCaseResult(BaseModel):
    interfaceCaseID: int



class InterfaceCaseResultFieldSchema(BaseSchema):
    interfaceCaseID: int | None = None
    interfaceCaseName: str | None = None
    interfaceCaseUid: str | None = None
    interfaceCaseProjectId: int | None = None
    interfaceCasePartId: int | None = None
    starterId: int | None = None
    status: str | None = None
    result: str | None = None
    interface_task_result_Id: int | None = None


class InterfaceResultFieldSchema(BaseSchema):
    interfaceID: int | None = None
    interfaceName: str | None = None
    interfaceUid: str | None = None
    interfaceProjectId: int | None = None
    interfaceModuleId: int | None = None
    interfaceEnvId: int | None = None
    starterId: int | None = None
    result: str | None = None
    interface_case_result_Id: int | None = None
    interface_task_result_Id: int | None = None


class PageInterfaceCaseResultFieldSchema(InterfaceCaseResultFieldSchema, PageSchema):
    ...

class PageInterfaceApiResultFieldSchema(InterfaceResultFieldSchema, PageSchema):
    ...