from pydantic import BaseModel
from app.schema import PageSchema
from typing import Optional

class EnvField(BaseModel):
    id: int | None = None
    uid: Optional[str] = None
    method_name: Optional[str] = None
    description: Optional[str] = None
    host: Optional[str] = None
    port: Optional[str] = None
    project_id: int | None = None


class InsertEnvSchema(EnvField):
    name: str
    host: str
    project_id: int


class FilterByEnvSchema(EnvField):
    ...


class PageEnvSchema(EnvField, PageSchema):
    ...



class UpdateEnvSchema(EnvField):
    id: int


class DeleteEnvSchema(EnvField):
    id: int
