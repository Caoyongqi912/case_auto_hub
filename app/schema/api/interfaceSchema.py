#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Interface Schema 定义

与 app/model/interfaceAPIModel/interfaceModel.py 中的 Interface 模型对应
使用 Pydantic v2 注解，提供数据验证和序列化
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schema import PageSchema
from enums import ModuleEnum, InterfaceAuthType


class IItem(BaseModel):
    """headers 等的结构定义"""
    id: Union[int, str] = Field(..., description="ID")
    key: str = Field(..., description="键", title="Key")
    value: Optional[Any] = Field(..., description="值")
    desc: Optional[str] = Field(None, description="描述")


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


class IExtract(BaseModel):
    """提取结构定义"""
    key: str = Field(..., description="键", title="Key")
    value: Optional[Any] = Field(..., description="值")
    target: int = Field(..., description="目标")
    extraOpt: str = Field(..., description="类型")


class IBeforeSqlExtracts(BaseModel):
    """前置SQL提取结构定义"""
    id: Union[int, str] = Field(..., description="ID")
    jp: str = Field(..., description="JSONPath", title="jp")
    key: str = Field(..., description="键")


class InterfaceSchema(BaseModel):
    """
    接口 Schema - 完整字段定义
    对应 Interface 模型的完整字段结构
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = Field(None, description="接口ID")
    uid: Optional[str] = Field(None, description="唯一标识")

    interface_name: Optional[str] = Field(None, description="接口名称")
    interface_desc: Optional[str] = Field(None, description="接口描述")
    interface_status: Optional[str] = Field(None, description="接口状态")
    interface_level: Optional[str] = Field(None, description="接口等级")
    interface_url: Optional[str] = Field(None, description="接口地址")
    interface_method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field(
        default="GET",
        description="请求方法"
    )
    interface_params: Optional[List[IItem]] = Field(None, description="请求参数")
    interface_headers: Optional[List[IItem]] = Field(None, description="请求头")
    interface_body_type: Optional[int] = Field(default=0, description="请求体类型: 0无 1raw 2data 3..")
    interface_raw_type: Optional[str] = Field(None, description="raw类型: json/text")
    interface_body: Optional[Any] = Field(None, description="请求体")
    interface_data: Optional[List[IItem]] = Field(None, description="表单数据")
    interface_asserts: Optional[List[IAssert]] = Field(None, description="断言配置")
    interface_extracts: Optional[List[IExtract]] = Field(None, description="响应提取配置")
    interface_follow_redirects: Optional[int] = Field(None, description="是否跟随重定向: 0否 1是")
    interface_connect_timeout: Optional[int] = Field(None, description="连接超时时间(秒)")
    interface_response_timeout: Optional[int] = Field(None, description="响应超时时间(秒)")
    interface_before_script: Optional[str] = Field(None, description="前置脚本")
    interface_before_db_id: Optional[int] = Field(None, description="前置数据库ID")
    interface_before_sql: Optional[List[IBeforeSqlExtracts]] = Field(None, description="前置SQL")
    interface_before_sql_extracts: Optional[List[Dict[str, Any]]] = Field(None, description="SQL提取配置")
    interface_before_params: Optional[List[Dict[str, Any]]] = Field(None, description="前置参数")
    interface_after_script: Optional[str] = Field(None, description="后置脚本")

    interface_auth_type: Optional[int] = Field(None, description="认证类型: 1不认证 2KV 3Basic 4Bearer")
    interface_auth: Optional[Dict[str, Any]] = Field(None, description="认证配置")

    is_common: Optional[int] = Field(None, description="是否公共API: 0否 1是")
    env_id: Optional[int] = Field(None, description="环境ID")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")

    creator: Optional[int] = Field(None, description="创建人ID")
    creatorName: Optional[str] = Field(None, description="创建人姓名")
    updater: Optional[int] = Field(None, description="更新人ID")
    updaterName: Optional[str] = Field(None, description="更新人姓名")
    create_time: Optional[datetime] = Field(None, description="创建时间")
    update_time: Optional[datetime] = Field(None, description="更新时间")

    @model_validator(mode="before")
    @classmethod
    def validate_auth_type_and_auth(cls, values):
        """根据auth_type验证和转换auth字段"""
        auth_type = values.get('interface_auth_type')
        auth_data = values.get('interface_auth', {})

        # 如果没有设置auth_type，则不进行验证
        if auth_type is None:
            return values

        # 根据auth_type创建对应的认证模型
        if auth_type == InterfaceAuthType.No_Auth:
            # 无需认证时，清空auth
            values['interface_auth'] = None
        elif auth_type == InterfaceAuthType.KV_Auth:
            values['interface_auth'] = KVAuth(**auth_data)
        elif auth_type == InterfaceAuthType.BASIC_Auth:
            values["interface_auth"] = BasicAuth(**auth_data)
        elif auth_type == InterfaceAuthType.BEARER_Auth:
            values['interface_auth'] = BearerAuth(**auth_data)

        return values


class InterfaceBriefSchema(BaseModel):
    """
    接口简要 Schema - 用于列表展示
    只包含关键字段，减小数据传输量
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="接口ID")
    uid: str = Field(..., description="唯一标识")
    interface_name: str = Field(..., description="接口名称")
    interface_desc: Optional[str] = Field(None, description="接口描述")
    interface_method: str = Field(..., description="请求方法")
    interface_url: str = Field(..., description="接口地址")
    interface_status: Optional[str] = Field(None, description="接口状态")
    interface_level: Optional[str] = Field(None, description="接口等级")
    project_id: int = Field(..., description="项目ID")
    module_id: int = Field(..., description="模块ID")

    @property
    def desc_brief(self) -> str:
        """
        获取简短的描述
        用于列表展示，超长部分截断
        """
        if not self.interface_desc:
            return ""
        return self.interface_desc[:10] + "..." if len(self.interface_desc) > 10 else self.interface_desc


class AddInterfaceSchema(InterfaceSchema):
    """
    添加接口 Schema - 创建新接口时使用
    必填字段验证
    """
    interface_name: str = Field(..., min_length=1, max_length=100, description="接口名称")
    interface_url: str = Field(..., min_length=1, max_length=500, description="接口地址")
    interface_method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field(
        default="GET",
        description="请求方法"
    )
    interface_desc: Optional[str] = Field(None, description="接口描述")
    interface_status: str = Field(default="1", description="接口状态")
    interface_level: str = Field(default="P0", description="接口等级")
    interface_body_type: int = Field(default=0, description="请求体类型")
    interface_follow_redirects: int = Field(default=0, description="是否跟随重定向")
    is_common: int = Field(default=1, description="是否公共API")

    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")
    env_id: Optional[int] = Field(None, description="环境ID")


class UpdateInterfaceSchema(InterfaceSchema):
    """
    更新接口 Schema - 更新现有接口时使用
    所有字段可选，允许部分更新
    """
    interface_id: int = Field(
        ...,
        validation_alias="id",
        description="接口ID"
    )


class InterfaceListSchema(BaseModel):
    """
    接口列表 Schema - 用于分页查询结果
    包含接口简要信息和分页信息
    """
    items: List[InterfaceBriefSchema] = Field(default_factory=list, description="接口列表")
    page_info: "PageInfoSchema" = Field(..., description="分页信息")


class InterfaceQuerySchema(BaseModel):
    """
    接口查询 Schema - 用于条件查询和分页
    """
    interface_name: Optional[str] = Field(None, description="接口名称(模糊匹配)")
    interface_method: Optional[Literal["GET", "POST", "PUT", "DELETE", "PATCH"]] = Field(
        None,
        description="请求方法"
    )
    interface_status: Optional[str] = Field(None, description="接口状态")
    interface_level: Optional[str] = Field(None, description="接口等级")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    is_common: Optional[int] = Field(None, description="是否公共API")

    page: int = Field(default=1, ge=1, description="页码")
    limit: int = Field(default=20, ge=1, le=100, description="每页记录数")
    sort: Optional[str] = Field(None, description="排序字段，格式: field:asc|desc")


class UpdateInterfaceApiSchema(BaseModel):
    """
    更新接口 Schema - 包含接口ID
    用于通过 API 更新接口信息
    """
    id: int = Field(..., description="接口ID")
    interface_name: Optional[str] = Field(None, min_length=1, max_length=100, description="接口名称")
    interface_url: Optional[str] = Field(None, min_length=1, max_length=500, description="接口地址")
    interface_method: Optional[Literal["GET", "POST", "PUT", "DELETE", "PATCH"]] = Field(
        None,
        description="请求方法"
    )
    interface_desc: Optional[str] = Field(None, description="接口描述")
    interface_status: Optional[str] = Field(None, description="接口状态")
    interface_level: Optional[str] = Field(None, description="接口等级")
    interface_body_type: Optional[int] = Field(None, description="请求体类型")
    interface_follow_redirects: Optional[int] = Field(None, description="是否跟随重定向")
    is_common: Optional[int] = Field(None, description="是否公共API")
    module_id: Optional[int] = Field(None, description="模块ID")
    env_id: Optional[int] = Field(None, description="环境ID")
    interface_params: Optional[Dict[str, Any]] = Field(None, description="请求参数")
    interface_headers: Optional[Dict[str, Any]] = Field(None, description="请求头")
    interface_body: Optional[Dict[str, Any]] = Field(None, description="请求体")
    interface_data: Optional[Dict[str, Any]] = Field(None, description="表单数据")
    interface_asserts: Optional[List[Dict[str, Any]]] = Field(None, description="断言配置")
    interface_extracts: Optional[List[Dict[str, Any]]] = Field(None, description="响应提取配置")
    interface_raw_type: Optional[str] = Field(None, description="raw类型")
    interface_connect_timeout: Optional[int] = Field(None, ge=1, le=300, description="连接超时(秒)")
    interface_response_timeout: Optional[int] = Field(None, ge=1, le=300, description="响应超时(秒)")
    interface_before_script: Optional[str] = Field(None, description="前置脚本")
    interface_before_db_id: Optional[int] = Field(None, description="前置数据库ID")
    interface_before_sql: Optional[str] = Field(None, description="前置SQL")
    interface_before_sql_extracts: Optional[List[Dict[str, Any]]] = Field(None, description="SQL提取配置")
    interface_before_params: Optional[List[Dict[str, Any]]] = Field(None, description="前置参数")
    interface_after_script: Optional[str] = Field(None, description="后置脚本")
    interface_auth_type: Optional[int] = Field(None, ge=1, le=4, description="认证类型")
    interface_auth: Optional[Dict[str, Any]] = Field(None, description="认证配置")


class GetInterfaceApiSchema(BaseModel):
    """
    删除接口 Schema
    用于通过 API 删除接口
    """
    interface_id: int = Field(..., description="接口ID")


class TryScriptSchema(BaseModel):
    """尝试执行脚本模型"""
    script: str = Field(..., description="脚本")


class CurlSchema(BaseModel):
    """Curl命令模型"""
    script: str = Field(..., description="脚本")


class CopyInterfaceToModuleSchema(BaseModel):
    """
    复制接口到指定模块 Schema
    用于将接口复制到其他模块
    """
    interface_id: int = Field(..., description="接口ID")
    project_id: int = Field(..., description="目标项目ID")
    module_id: int = Field(..., description="目标模块ID")


class PageInterfaceApiSchema(InterfaceSchema, PageSchema):
    """接口API分页查询模型"""
    module_type: int = ModuleEnum.API


class TryInterfaceApiSchema(BaseModel):
    """尝试添加接口API模型"""
    interface_id: int = Field(..., description="接口ID")
    env_id: int = Field(..., description="环境ID")


# ==================== InterfaceCase 用例相关 Schema ====================

class InterfaceCaseSchema(BaseModel):
    """
    接口用例 Schema - 完整字段定义
    对应 InterfaceCase 模型的完整字段结构
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = Field(None, description="用例ID")
    uid: Optional[str] = Field(None, description="唯一标识")

    case_title: str = Field(..., description="用例标题")
    case_desc: Optional[str] = Field(None, description="用例描述")
    case_level: str = Field(..., description="用例等级")
    case_status: str = Field(default="1", description="用例状态")
    case_api_num: int = Field(default=0, description="接口数量")
    error_stop: int = Field(default=0, description="错误停止: 0否 1是")

    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")

    creator: Optional[int] = Field(None, description="创建人ID")
    creatorName: Optional[str] = Field(None, description="创建人姓名")
    updater: Optional[int] = Field(None, description="更新人ID")
    updaterName: Optional[str] = Field(None, description="更新人姓名")
    create_time: Optional[datetime] = Field(None, description="创建时间")
    update_time: Optional[datetime] = Field(None, description="更新时间")


class InterfaceCaseBriefSchema(BaseModel):
    """
    接口用例简要 Schema - 用于列表展示
    只包含关键字段，减小数据传输量
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="用例ID")
    uid: str = Field(..., description="唯一标识")
    case_title: str = Field(..., description="用例标题")
    case_desc: Optional[str] = Field(None, description="用例描述")
    case_level: str = Field(..., description="用例等级")
    case_status: str = Field(..., description="用例状态")
    case_api_num: int = Field(..., description="接口数量")
    project_id: int = Field(..., description="项目ID")
    module_id: int = Field(..., description="模块ID")

    @property
    def desc_brief(self) -> str:
        """
        获取简短的描述
        """
        if not self.case_desc:
            return ""
        return self.case_desc[:20] + "..." if len(self.case_desc) > 20 else self.case_desc


class AddInterfaceCaseSchema(BaseModel):
    """
    添加接口用例 Schema - 创建新用例时使用
    """
    case_title: str = Field(..., min_length=1, max_length=40, description="用例标题")
    case_desc: Optional[str] = Field(None, max_length=200, description="用例描述")
    case_level: str = Field(default="P0", description="用例等级")
    case_status: str = Field(default="1", description="用例状态")
    error_stop: int = Field(default=0, description="错误停止: 0否 1是")

    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class UpdateInterfaceCaseSchema(BaseModel):
    """
    更新接口用例 Schema - 更新现有用例时使用
    """
    case_title: Optional[str] = Field(None, min_length=1, max_length=40, description="用例标题")
    case_desc: Optional[str] = Field(None, max_length=200, description="用例描述")
    case_level: Optional[str] = Field(None, description="用例等级")
    case_status: Optional[str] = Field(None, description="用例状态")
    error_stop: Optional[int] = Field(None, description="错误停止: 0否 1是")
    module_id: Optional[int] = Field(None, description="模块ID")


class UpdateInterfaceCaseApiSchema(BaseModel):
    """
    更新接口用例 Schema - 包含用例ID
    用于通过 API 更新用例信息
    """
    id: int = Field(..., description="用例ID")
    case_title: Optional[str] = Field(None, min_length=1, max_length=40, description="用例标题")
    case_desc: Optional[str] = Field(None, max_length=200, description="用例描述")
    case_level: Optional[str] = Field(None, description="用例等级")
    case_status: Optional[str] = Field(None, description="用例状态")
    error_stop: Optional[int] = Field(None, description="错误停止: 0否 1是")
    module_id: Optional[int] = Field(None, description="模块ID")


class GetInterfaceCaseApiSchema(BaseModel):
    """
    获取/删除/复制接口用例 Schema
    """
    case_id: int = Field(..., description="用例ID")


class ExecuteInterfaceCaseSchema(BaseModel):
    """
    执行接口用例 Schema
    """
    case_id: int = Field(..., description="用例ID")
    env_id: int = Field(..., description="环境ID")
    error_stop: bool = Field(..., description="错误是否停止")


class PageInterfaceCaseSchema(InterfaceCaseSchema, PageSchema):
    """
    接口用例分页查询 Schema
    """
    module_type: int = Field(ModuleEnum.API_CASE, description="模块类型")


class AssociationApisSchema(BaseModel):
    """
    关联接口列表 Schema
    用于将多个接口关联到用例
    """
    case_id: int = Field(..., description="用例ID")
    interface_id_list: List[int] = Field(..., description="接口ID列表")


class AddInterfaceApi2CaseSchema(BaseModel):
    """
    添加单个接口到用例 Schema
    """
    case_id: int = Field(..., description="用例ID")
    interface_id: int = Field(..., description="接口ID")


class RemoveCaseContentSchema(BaseModel):
    """
    删除用例内容 Schema
    """
    case_id: int = Field(..., description="用例ID")
    content_step_id: int = Field(..., description="内容步骤ID")


class ReorderContentStepSchema(BaseModel):
    """
    重排序用例内容步骤 Schema
    """
    case_id: int = Field(..., description="用例ID")
    content_step_order: List[int] = Field(..., description="内容步骤ID列表")


class InterfaceCaseListSchema(BaseModel):
    """
    接口用例列表 Schema - 用于分页查询结果
    """
    items: List[InterfaceCaseBriefSchema] = Field(default_factory=list, description="用例列表")
    page_info: "PageInfoSchema" = Field(..., description="分页信息")


class InterfaceCaseQuerySchema(BaseModel):
    """
    接口用例查询 Schema - 用于条件查询和分页
    """
    case_title: Optional[str] = Field(None, description="用例标题(模糊匹配)")
    case_level: Optional[str] = Field(None, description="用例等级")
    case_status: Optional[str] = Field(None, description="用例状态")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")

    page: int = Field(default=1, ge=1, description="页码")
    limit: int = Field(default=20, ge=1, le=100, description="每页记录数")
    sort: Optional[str] = Field(None, description="排序字段")


__all__ = [
    # Interface Schema
    'InterfaceSchema',
    'AddInterfaceSchema',
    'UpdateInterfaceSchema',
    'UpdateInterfaceApiSchema',
    'GetInterfaceApiSchema',
    'CopyInterfaceToModuleSchema',
    'InterfaceListSchema',
    'InterfaceBriefSchema',
    'InterfaceQuerySchema',
    'PageInterfaceApiSchema',
    "TryScriptSchema",
    "TryInterfaceApiSchema",
    "CurlSchema",
    # InterfaceCase Schema
    'InterfaceCaseSchema',
    'InterfaceCaseBriefSchema',
    'AddInterfaceCaseSchema',
    'UpdateInterfaceCaseSchema',
    'UpdateInterfaceCaseApiSchema',
    'GetInterfaceCaseApiSchema',
    'ExecuteInterfaceCaseSchema',
    'PageInterfaceCaseSchema',
    'AssociationApisSchema',
    'AddInterfaceApi2CaseSchema',
    'RemoveCaseContentSchema',
    'ReorderContentStepSchema',
    'InterfaceCaseListSchema',
    'InterfaceCaseQuerySchema',
]
