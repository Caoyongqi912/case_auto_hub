#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Interface Controller

接口管理控制器
提供接口的增删改查、调试执行、CURL转换、导出等功能
"""
import yaml
from fastapi import APIRouter, Depends, Response as FastResponse

from app.controller import Authentication
from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
from app.mapper.interfaceApi.interfaceScriptMapper import InterfaceScriptMapper
from app.model.base import User
from app.response import Response
from app.schema.api.interfaceSchema import (
    AddInterfaceSchema,
    UpdateInterfaceSchema,
    GetInterfaceApiSchema,
    PageInterfaceApiSchema,
    TryInterfaceApiSchema,
    TryScriptSchema,
    CopyInterfaceToModuleSchema,
    CurlSchema,
)
from croe.a_manager import ScriptManager
from croe.interface.runner import InterfaceRunner
from croe.interface.starter import APIStarter
from utils import MyLoguru
from utils.curlTrans import CurlConverter

log = MyLoguru().get_logger()

router = APIRouter(prefix="/interface", tags=['接口用例'])

API_EXCLUDE_FIELDS = {
    "interface_params", "interface_headers", "interface_extracts",
    "interface_after_script", "interface_asserts", "interface_before_db_id",
    "interface_before_params", "interface_before_script", "interface_before_sql",
    "interface_before_sql_extracts", "interface_body", "interface_body_type",
    "interface_connect_timeout", "interface_response_timeout", "interface_follow_redirects",
    "interface_raw_type"
}


# ==================== 接口基础管理 ====================

@router.post("/page", description="分页查询接口列表")
async def page_interfaces(page_params: PageInterfaceApiSchema, _=Depends(Authentication())):
    """
    分页查询指定模块下的接口列表

    - **page_params**: 分页查询参数
    """
    interfaces = await InterfaceMapper.page_by_module(
        **page_params.model_dump(
            exclude_unset=True,
            exclude_none=True
        )
    )
    return Response.success(data=interfaces, exclude=API_EXCLUDE_FIELDS)


@router.post("/insert", description="新增接口")
async def create_interface(api_info: AddInterfaceSchema, user: User = Depends(Authentication())):
    """
    创建新的接口配置

    - **api_info**: 接口配置信息
    """
    log.info(f"insert interface: {api_info}")
    api = await InterfaceMapper.create_interface(**api_info.model_dump(), user=user)
    return Response.success(api)


@router.get("/detail", description="获取接口详情")
async def get_interface_detail(interface_id: int, _: User = Depends(Authentication())):
    """
    根据接口ID获取接口详细信息

    - **interface_id**: 接口ID
    """
    interface = await InterfaceMapper.get_by_id(interface_id)
    log.info(f"获取接口详情: {interface.interface_body}")
    return Response.success(interface)


@router.post("/update", description="更新接口")
async def update_interface(update_info: UpdateInterfaceSchema, user: User = Depends(Authentication())):
    """
    更新接口配置信息

    - **update_info**: 接口更新信息
    """
    log.info(f"更新接口信息: {update_info}")
    await InterfaceMapper.update_interface(**update_info.model_dump(
        exclude_unset=True,
        exclude_none=True
    ), user=user)
    return Response.success()


@router.post("/remove", description="删除接口")
async def remove_interface(remove_params: GetInterfaceApiSchema, _: User = Depends(Authentication())):
    """
    删除指定的接口

    - **remove_params**: 包含接口ID
    """
    await InterfaceMapper.remove_interface(remove_params.interface_id)
    return Response.success()


@router.post("/copy", description="复制接口")
async def copy_interface(copy_info: GetInterfaceApiSchema, user: User = Depends(Authentication())):
    """
    复制现有接口到公共接口库

    - **copy_info**: 包含源接口ID
    """
    interface = await InterfaceMapper.copy_interface(
        is_common=True,
        interface_id=copy_info.interface_id,
        user=user
    )
    return Response.success(interface)


@router.post("/copy_to_module", description="复制接口到指定模块")
async def copy_interfaces_to_module(copy_info: CopyInterfaceToModuleSchema, user: User = Depends(Authentication())):
    """
    批量复制接口到指定模块

    - **copy_info**: 包含接口ID、目标项目ID和模块ID
    """
    await InterfaceMapper.copy_to_module(user=user, **copy_info.model_dump())
    return Response.success()


# ==================== 接口调试执行 ====================

@router.post("/try", description="接口调试执行")
async def try_interface(debug_params: TryInterfaceApiSchema, user: User = Depends(Authentication())):
    """
    调试执行单个接口

    - **debug_params**: 包含接口ID和环境ID
    """
    response = await InterfaceRunner(
        starter=APIStarter(user),
    ).try_interface(**debug_params.model_dump())
    return Response.success([response])


@router.post("/try_script", description="脚本调试执行")
async def try_script(script_info: TryScriptSchema, _: User = Depends(Authentication())):
    """
    执行并调试脚本代码

    - **script_info**: 包含脚本代码
    """
    script_manager = ScriptManager()
    try:
        result = script_manager.execute(script_info.script)
        return Response.success(result)
    except Exception as e:
        return Response.error(f"脚本执行失败: {str(e)}")


@router.get("/query_script_doc", description="查询脚本文档")
async def query_script_documentation(_: User = Depends(Authentication())):
    """
    获取所有可用的接口脚本文档
    """
    docs = await InterfaceScriptMapper.query_all()
    return Response.success(docs)


# ==================== 工具功能 ====================

@router.post("/trans_curl", description="CURL命令转换")
async def convert_curl_to_api(curl_params: CurlSchema, _: User = Depends(Authentication())):
    """
    将CURL命令转换为接口配置

    - **curl_params**: 包含CURL命令
    """
    try:
        interface_info = CurlConverter(curl_params.script).parse_curl()
        return Response.success(interface_info)
    except Exception:
        return Response.error("CURL解析失败，请检查命令格式")


@router.get("/export/yaml", description="导出接口为YAML")
async def export_interfaces_yaml(module_id: int, _: User = Depends(Authentication())):
    """
    导出模块下所有接口为YAML格式

    - **module_id**: 模块ID
    """
    try:
        interfaces = await InterfaceMapper.query_by(module_id=module_id)
        if interfaces:
            data = {
                "moduleId": module_id,
                "apis": [interface.map for interface in interfaces]
            }
            yaml_data = yaml.dump(data)
        else:
            yaml_data = yaml.dump({"moduleId": module_id, "apis": []})

        return FastResponse(
            content=yaml_data,
            media_type="text/yaml",
            headers={"Content-Disposition": f"attachment; filename=interfaces_{module_id}.yaml"}
        )
    except Exception as e:
        log.error(f"导出YAML失败: {e}")
        raise e
