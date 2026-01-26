#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/11/20
# @Author : cyq
# @File : interfaceApiSchema
# @Software: PyCharm
# @Desc: 接口API相关的Schema定义
from typing import List, Dict, Any, Literal, Optional, Union
from pydantic import BaseModel, Field, computed_field
from pydantic.v1 import root_validator

from app.schema import PageSchema
from enums import InterfaceAuthType
from enums.ModuleEnum import ModuleEnum


class IItem(BaseModel):
    """headers 等的结构定义"""
    id: Union[int, str] = Field(..., description="ID")
    key: str = Field(..., description="键", title="Key")
    value: Optional[Any] = Field(..., description="值")
    desc: Optional[str] = Field(None, description="描述")


class IBeforeSqlExtracts(BaseModel):
    """前置SQL提取结构定义"""
    id: Union[int, str] = Field(..., description="ID")
    jp: str = Field(..., description="JSONPath", title="jp")
    key: str = Field(..., description="键")


class IExtract(BaseModel):
    """提取结构定义"""
    key: str = Field(..., description="键", title="Key")
    value: Optional[Any] = Field(..., description="值")
    target: int = Field(..., description="目标")
    extraOpt: str = Field(..., description="类型")


class IAssert(BaseModel):
    """断言结构定义"""
    assert_name: str = Field(..., description="断言名")
    assert_switch: bool = Field(True, description="是否开启断言")
    assert_target: str = Field(..., description="断言目标")
    assert_extract: Optional[str] = Field(None, description="提取")
    assert_text: Optional[str] = Field(None, description="表达式")
    assert_opt: int = Field(..., description="断言类型")
    assert_value: Any = Field(..., description="预期值")


class KVAuth(BaseModel):
    """KV认证模型"""
    key: str
    value: str
    target: Literal['query', 'header'] = 'query'

    class Config:
        title = "KV认证"


class BasicAuth(BaseModel):
    """Basic认证模型"""
    username: str
    password: str

    class Config:
        title = "Basic认证"


class BearerAuth(BaseModel):
    """Bearer Token认证模型"""
    token: str

    class Config:
        title = "Bearer Token认证"


class InterfaceApiFieldSchema(BaseModel):
    """接口步骤字段模型"""
    # 基本信息
    id: Optional[int] = None
    uid: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    method: Literal["GET", "POST", "PUT", "DELETE"] = Field(default="GET", description="请求方法")
    status: Optional[str] = None
    level: Optional[str] = None

    # 请求
    url: Optional[str] = None
    headers: Optional[List[IItem]] = None
    params: Optional[List[IItem]] = None
    data: Optional[List[IItem]] = None
    extracts: Optional[List[IExtract]] = None
    asserts: Optional[List[IAssert]] = None
    body: Optional[Any] = None
    # 超时设置
    connect_timeout: int = Field(default=6, description="连接超时时间（秒）")
    response_timeout: int = Field(default=6, description="响应超时时间（秒）")

    before_script: Optional[str] = None
    before_db_id: Optional[int] = None
    before_sql: Optional[str] = None
    before_sql_extracts: Optional[List[IBeforeSqlExtracts]] = None
    before_params: Optional[List[IItem]] = None
    after_script: Optional[str] = None

    project_id: Optional[int] = None
    env_id: Optional[int] = None
    module_id: Optional[int] = None
    body_type: Optional[int] = None
    raw_type: Optional[str] = Field(None, description='json 类型 json、text')
    follow_redirects: Optional[int] = None
    is_common: Optional[int] = None
    creator: Optional[int] = None
    creatorName: Optional[str] = None

    auth_type: Optional[int] = None
    auth: Optional[Union[KVAuth, BasicAuth, BearerAuth]] = Field(
        None,
        description="认证配置，根据auth_type确定具体类型"
    )

    @root_validator(pre=True)
    def validate_auth_type_and_auth(cls, values):
        """根据auth_type验证和转换auth字段"""
        auth_type = values.get('auth_type')
        auth_data = values.get('auth', {})

        # 如果没有设置auth_type，则不进行验证
        if auth_type is None:
            return values

        # 根据auth_type创建对应的认证模型
        if auth_type == InterfaceAuthType.No_Auth:
            # 无需认证时，清空auth
            values['auth'] = None
        elif auth_type == InterfaceAuthType.KV_Auth:
            values['auth'] = KVAuth(**auth_data)
        elif auth_type == InterfaceAuthType.BASIC_Auth:
            values["auth"] = BasicAuth(**auth_data)
        elif auth_type == InterfaceAuthType.BEARER_Auth:
            values['auth'] = BearerAuth(**auth_data)
        
        return values


class SaveRecordSchema(BaseModel):
    """保存记录模型"""
    name: str
    is_common: int = 1
    module_id: int
    project_id: int
    status: Optional[str] = None
    level: Optional[str] = None
    recordId: str


class SaveRecordToCaseSchema(BaseModel):
    """保存记录到用例模型"""
    recordId: str
    caseId: int


class SetInterfacesModuleSchema(BaseModel):
    """设置接口模块模型"""
    module_id: int
    interfaces: List[int]


class AddInterfaceApiSchema(InterfaceApiFieldSchema):
    """添加接口API模型"""
    name: str
    description: str
    method: str
    url: str
    project_id: int
    module_id: int = Field(ModuleEnum.API, description="模块类型")
    status: str
    level: str
    body_type: int = 0
    follow_redirects: int = 0
    is_common: int = 1


class TryScriptSchema(BaseModel):
    """尝试执行脚本模型"""
    script: str


class UploadApiSchema(BaseModel):
    """上传API模型"""
    valueType: int


class UpdateInterfaceApiSchema(InterfaceApiFieldSchema):
    """更新接口API模型"""
    id: int


class RemoveInterfaceApiSchema(BaseModel):
    """删除接口API模型"""
    id: int


class CopyInterfaceApiSchema(BaseModel):
    """复制接口API模型"""
    id: int


class CurlSchema(BaseModel):
    """Curl命令模型"""
    script: str


class TryAddInterfaceApiSchema(BaseModel):
    """尝试添加接口API模型"""
    interface_id: int
    env_id: int


class PageInterfaceApiSchema(InterfaceApiFieldSchema, PageSchema):
    """接口API分页查询模型"""
    module_type: int = ModuleEnum.API


class RecordingSchema(BaseModel):
    """录制模型"""
    url: Optional[str] = ""
    method: Optional[List[str]] = None


class PerfSchema(BaseModel):
    """性能测试模型"""
    interfaceId: int = Field(..., title="接口ID", description="接口id")
    perf_user: int = Field(..., description="用户数量")
    perf_duration: float = Field(..., description="执行时长")
    perf_spawn_rate: int = Field(..., description="生成率")
    wait_range: Optional[str] = Field(None)
    file_name: Optional[str] = Field(None)

    @computed_field
    @property
    def perf_duration_per_minute(self) -> float:
        """
        实际运行时间
        perf_duration * 60
        """
        return self.perf_duration * 60

    @computed_field
    @property
    def perf_wait_range(self) -> List[int]:
        """
        等待区间
        """
        if not self.wait_range:
            return [0, 0]
        else:
            try:
                return [int(i) for i in self.wait_range.split(",")]
            except Exception as e:
                return [0, 0]


class InterfaceApiSchema(BaseModel):
    """接口API模型"""
    name: str
    method: str
    url: str
    host: str
    headers: Optional[Dict[str, Any]] = Field(None)
    data: Optional[Union[Dict[str, Any], str]] = Field(None)
    body: Optional[Dict[str, Any]] = Field(None)
    params: Optional[Dict[str, Any]] = Field(None)
    asserts: Optional[List[IAssert]] = None

    @property
    def requestInfo(self):
        """获取请求信息"""
        return {
            "headers": self.headers,
            "data": self.data,
            "json": self.body,
            "params": self.params,
        }


class Copy2Module(BaseModel):
    """复制到模块模型"""
    inter_id: int = Field(..., description="接口id")
    project_id: int = Field(..., description="项目id")
    module_id: int = Field(..., description="模块id")