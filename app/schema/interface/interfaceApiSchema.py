#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceApiSchema# @Software: PyCharm# @Desc:from app.schema import BaseSchema, PageSchemafrom pydantic import BaseModel, Field, validatorfrom typing import List, Dict, Any, Literalfrom enums.ModuleEnum import ModuleEnumclass InterfaceApiFieldSchema(BaseModel):    """    接口步骤字段    """    id: int | None = None    uid: str | None = None    name: str | None = None    description: str | None = None    method: Literal["GET", 'POST', 'PUT', "DELETE"] = Field(default="GET", description="请求方法")    status: str | None = None    level: str | None = None    url: str | None = None    headers: List[Dict[str, Any]] | None = None    params: List[Dict[str, Any]] | None = None    body: Dict[str, Any] | None = None    data: List[Dict[str, Any]] | None = None    asserts: List[Dict[str, Any]] | None = None    extracts: List[Dict[str, Any]] | None = None    project_id: int | None = None    connect_timeout: int | None = 6    response_timeout: int | None = 6    before_script: str | None = None    before_db_id: int | None = None    before_sql: str | None = None    before_sql_extracts: List[Dict[str, Any]] | None = None    after_script: str | None = None    before_params: List[Dict[str, Any]] | None = None    env_id: int | None = None    module_id: int | None = None    body_type: int | None = None    follow_redirects: int | None = None    is_common: int | None = None    enable: int | bool | None = None    is_group: int | bool | None = None    group_id: int | None = None    creator: int | None = None    creatorName: str | None = Noneclass SaveRecordSchema(BaseModel):    name: str    is_common: int = 1    module_id: int    project_id: int    status: str | None = None    level: str | None = None    recordId: strclass SaveRecordToCaseSchema(BaseModel):    recordId: str    caseId: intclass SetInterfacesModuleSchema(BaseModel):    module_id: int    interfaces: List[int]class AddInterfaceApiSchema(InterfaceApiFieldSchema):    name: str    description: str    method: str    url: str    project_id: int    module_id = int    status: str    level: str    body_type: int = 0    follow_redirects: int = 0    is_common: int = 1class TryScriptSchema(BaseModel):    script: strclass UploadApiSchema(BaseModel):    valueType: intclass UpdateInterfaceApiSchema(InterfaceApiFieldSchema):    id: intclass RemoveInterfaceApiSchema(BaseModel):    id: intclass CopyInterfaceApiSchema(BaseModel):    id: intclass CurlSchema(BaseModel):    script: strclass TryAddInterfaceApiSchema(InterfaceApiFieldSchema):    interfaceId: intclass PageInterfaceApiSchema(InterfaceApiFieldSchema, PageSchema):    module_type: int = ModuleEnum.APIclass RecordingSchema(BaseModel):    url: str | None = ""    method: List[str] | None__all__ = [    "RecordingSchema",    "CopyInterfaceApiSchema",    "AddInterfaceApiSchema",    "TryAddInterfaceApiSchema",    "PageInterfaceApiSchema",    "InterfaceApiFieldSchema",    "UpdateInterfaceApiSchema",    "RemoveInterfaceApiSchema",    "SetInterfacesModuleSchema",    "CurlSchema"]