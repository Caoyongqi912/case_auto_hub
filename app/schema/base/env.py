from pydantic import BaseModel
from app.schema import PageSchema


class EnvField(BaseModel):
    id: int | None = None
    uid: str | None = None
    method_name: str | None = None
    description: str | None = None
    host: str | None = None
    port: str | None = None
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
