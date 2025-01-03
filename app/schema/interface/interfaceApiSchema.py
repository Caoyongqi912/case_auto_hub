#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceApiSchema# @Software: PyCharm# @Desc:from app.schema import BaseSchema, PageSchemafrom pydantic import BaseModel, Field, validatorfrom typing import List, Dict, Any, Literalclass InterfaceApiFieldSchema(BaseModel):    """    接口步骤字段    """    id: int | None = None    uid: str | None = None    name: str | None = None    desc: str | None = None    method: Literal["GET", 'POST', 'PUT', "DELETE"] = Field(default="GET", description="请求方法")    status: str | None = None    level: str | None = None    url: str | None = None    headers: List[Dict[str, Any]] | None = None    params: List[Dict[str, Any]] | None = None    body: Dict[str, Any] | None = None    data: List[Dict[str, Any]] | None = None    asserts: List[Dict[str, Any]] | None = None    extracts: List[Dict[str, Any]] | None = None    project_id: int | None = None    connectTimeout: int | None = 6    responseTimeout: int | None = 6    beforeScript: str | None = None    afterScript: str | None = None    beforeParams: List[Dict[str, Any]] | None = None    env_id: int | None = None    part_id: int | None = None    bodyType: int | None = None    follow_redirects: int | None = None    is_common: int | None = None    enable: int | bool | None = Noneclass SaveRecordSchema(BaseModel):    name: str    is_common: int = 1    part_id: int    project_id: int    status: str | None = None    level: str | None = None    recordId: strclass SaveRecordToCaseSchema(BaseModel):    recordId: str    caseId: intclass AddInterfaceApiSchema(InterfaceApiFieldSchema):    name: str    desc: str    method: str    url: str    project_id: int    status: str    level: str    bodyType: int = 0    follow_redirects: int = 0    is_common: int = 1    @validator("name", "desc")    def not_empty(cls, v):        return BaseSchema.not_empty(v)class UpdateInterfaceApiSchema(InterfaceApiFieldSchema):    id: intclass RemoveInterfaceApiSchema(BaseModel):    id: intclass CopyInterfaceApiSchema(BaseModel):    id: intclass TryAddInterfaceApiSchema(InterfaceApiFieldSchema):    interfaceId: intclass PageInterfaceApiSchema(InterfaceApiFieldSchema, PageSchema):    ...class RecordingSchema(BaseModel):    url: str | None = ""    method: List[str] | None = ['POST']__all__ = [    "RecordingSchema",    "CopyInterfaceApiSchema",    "AddInterfaceApiSchema",    "TryAddInterfaceApiSchema",    "PageInterfaceApiSchema",    "InterfaceApiFieldSchema",    "UpdateInterfaceApiSchema",    "RemoveInterfaceApiSchema"]