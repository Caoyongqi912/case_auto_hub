#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20
# @Author : cyq
# @File : interfaceApi
# @Software: PyCharm
# @Desc: 接口自动化管理API - 提供接口的增删改查、调试、性能测试等功能from fastapi import APIRouter, Depends, BackgroundTasks, Response as FastResponse, Form, UploadFile, Filefrom app.controller import Authenticationfrom app.mapper.interface import InterfaceScriptMapper, InterfaceMapperfrom app.model.base import Userfrom app.response import Responsefrom app.schema.interface import *from app.schema.interface.interfaceApiSchema import TryScriptSchemafrom croe.interface.executor.interface_executor import InterfaceExecutorfrom croe.interface.manager.script_manager import ScriptManagerfrom croe.interface.manager.variable_manager import VariableManagerfrom croe.interface.runner import InterfaceRunnerfrom croe.interface.starter import APIStarterfrom utils import MyLoguru, logfrom utils.curlTrans import CurlConverterfrom common.locust_client import locust_clientfrom utils.fileManager import FileManagerfrom utils import GenerateToolsLOG = MyLoguru().get_logger()router = APIRouter(prefix="/interface", tags=['自动化接口步骤'])API_Exclude_Field = {    "params", "headers", "extracts", "after_script", "asserts", "before_db_id", "before_params", "url"                                                                                                 "before_script",    "before_sql", "before_sql_extracts", "body", "body_type", "connect_timeout",    "follow_redirects"}@router.post("/setInterfaceModule", description="设置接口模块")
async def set_interface_module(info: SetInterfacesModuleSchema, _=Depends(Authentication())):
    """批量设置接口所属模块"""
    await InterfaceMapper.set_interfaces_modules(**info.model_dump())
    return Response.success()

@router.post("/insert", description="新增接口")
async def create_interface(api_info: AddInterfaceApiSchema, creator_user=Depends(Authentication())):
    """创建新的接口测试步骤"""
    api = await InterfaceMapper.save(
        creator_user=creator_user,
        **api_info.model_dump())
    return Response.success(api)

@router.get("/detail", description="获取接口详情")
async def get_interface_detail(interface_id: int, _=Depends(Authentication())):
    """根据接口ID获取接口详细信息"""
    interface = await InterfaceMapper.get_by_id(interface_id)
    log.info(f"获取接口详情: {interface.body}")
    return Response.success(interface)

@router.post("/copy", description="复制接口")
async def copy_interface(copy_info: CopyInterfaceApiSchema, copyer=Depends(Authentication())):
    """复制现有接口到公共接口库"""
    interface = await InterfaceMapper.copy_api(
        is_common=True,
        apiId=copy_info.id,
        creator=copyer
    )
    return Response.success(interface)

@router.post("/tryScript", description="脚本调试")
async def debug_script(script_info: TryScriptSchema, _=Depends(Authentication())):
    """执行并调试脚本代码"""
    script_manager = ScriptManager()
    try:
        result = script_manager.execute(script_info.script)
        return Response.success(result)
    except Exception as e:
        return Response.error(f"脚本执行失败: {str(e)}")@router.get("/queryBy", description="条件查询接口")
async def query_interfaces_by_conditions(query_params: InterfaceApiFieldSchema, _=Depends(Authentication())):
    """根据指定条件查询接口列表"""
    interfaces = await InterfaceMapper.get_by(**query_params.model_dump(
        exclude_unset=True,
        exclude_none=True,
    ))
    return Response.success(interfaces)

@router.post("/page", description="分页查询接口")
async def get_interfaces_by_page(page_params: PageInterfaceApiSchema, _=Depends(Authentication())):
    """分页查询指定模块下的接口"""
    interfaces = await InterfaceMapper.page_by_module(
        **page_params.model_dump(
            exclude_unset=True,
            exclude_none=True
        )
    )
    return Response.success(data=interfaces, exclude=API_Exclude_Field)

@router.post("/pageNoModule", description="全局分页查询")
async def get_interfaces_page_all(page_params: PageInterfaceApiSchema, _=Depends(Authentication())):
    """不分模块的全局分页查询接口"""
    interfaces = await InterfaceMapper.page_query(
        module_id=None,
        **page_params.model_dump(
            exclude_unset=True,
            exclude_none=True
        )
    )
    return Response.success(interfaces, exclude=API_Exclude_Field)

@router.post("/update", description="更新接口")
async def update_interface(update_info: UpdateInterfaceApiSchema, auth=Depends(Authentication())):
    """更新接口配置信息"""
    log.info(f"更新接口信息: {update_info}")
    interface = await InterfaceMapper.update_interface(**update_info.model_dump(
        exclude_unset=True,
    ), user=auth)
    # 更新关联的数据文件
    await InterfaceMapper.update_data_file(interface)
    return Response.success()

@router.post("/remove", description="删除接口")
async def delete_interface(remove_params: RemoveInterfaceApiSchema, _=Depends(Authentication())):
    """删除指定的接口"""
    await InterfaceMapper.remove(remove_params.id)
    return Response.success()

@router.post("/try", description="接口调试")
async def debug_interface(debug_params: TryAddInterfaceApiSchema, user=Depends(Authentication())):
    """调试执行单个接口"""
    response = await InterfaceRunner(
        starter=APIStarter(user),
    ).try_interface(**debug_params.model_dump())
    LOG.info(f"接口调试结果: {response}")
    return Response.success([response])@router.get("/query/script_doc", description="获取脚本文档")
async def get_script_documentation(_: User = Depends(Authentication())):
    """获取所有可用的接口脚本文档"""
    docs = await InterfaceScriptMapper.query_all()
    return Response.success(docs)

@router.post("/transCurl", description="CURL转换")
async def convert_curl_to_api(curl_params: CurlSchema, _: User = Depends(Authentication())):
    """将CURL命令转换为接口配置"""
    try:
        interface_info = CurlConverter(curl_params.script).parse_curl()
        return Response.success(interface_info)
    except Exception:
        return Response.error("CURL解析失败，请检查命令格式")@router.post("/debugPerf", description="性能测试")
async def start_performance_test(background_tasks: BackgroundTasks,
                               interface_id: int = Form(..., description="接口ID"),
                               perf_user: int = Form(..., description="并发用户数"),
                               perf_duration: float = Form(..., description="测试持续时间(秒)"),
                               perf_spawn_rate: int = Form(..., description="用户生成速率"),
                               wait_range: str = Form(..., description="等待时间范围"),
                               use_var: bool = Form(..., description="是否替换变量"),
                               api_file: UploadFile | None = File(None, description="性能测试API文件"),
                               user: User = Depends(Authentication())):    # 1. 创建性能测试配置    perf_setting = PerfSchema(        interfaceId=interface_id,        perf_user=perf_user,        perf_duration=perf_duration,        perf_spawn_rate=perf_spawn_rate,        wait_range=wait_range    )    log.info(f"性能测试配置: {perf_setting}")
    # 2. 获取接口信息
    starter = APIStarter(user)
    interface_executor = InterfaceExecutor(starter=starter, variable_manager=VariableManager())
    interface_info = await interface_executor.request_info(request_id=interface_id,
                                                          use_var=use_var)
    log.debug(f"获取到的接口信息: {interface_info}")
    # 3. 转换接口数据结构
    interface_info['body'] = interface_info.pop('json', None)
    interface_info['data'] = interface_info.pop('content', None)
    api = InterfaceApiSchema(**interface_info)
    task_id = f"interface_{GenerateTools.uid()}"    # 5. 处理上传文件
    if api_file:
        file_name = await FileManager.save_perf_file(
            file=api_file,
            interfaceId=task_id
        )
        perf_setting.file_name = file_name
        log.info(f"文件已保存: {file_name}")    try:        background_tasks.add_task(            locust_client.start_locust,            api=api,            setting=perf_setting,            perf_api_name=task_id,            io=starter        )        log.info(f"性能测试任务已启动, task_id: {task_id}")    except Exception as e:        raise e    return Response.success(task_id)@router.get("/stopPerf", description="停止性能测试")
async def stop_performance_test(task_id: str, background_tasks: BackgroundTasks, user: User = Depends(Authentication())):
    """停止正在运行的性能测试任务"""
    io = APIStarter(user)
    try:
        background_tasks.add_task(
            locust_client.stop,
            taskId=task_id,
            io=io
        )
        return Response.success()
    except Exception as e:
        log.exception(e)
        return Response.error(f"停止测试失败: {str(e)}")

@router.post("/copy2Module", description="复制到模块")
async def copy_interfaces_to_module(copy_info: Copy2Module, user: User = Depends(Authentication())):
    """批量复制接口到指定模块"""
    await InterfaceMapper.copy_to_module(user=user, **copy_info.model_dump())
    return Response.success()

@router.get("/apisInfo/yaml", description="导出YAML")
async def export_interfaces_yaml(module_id: int, _: User = Depends(Authentication())):
    """导出模块下所有接口为YAML格式"""
    import yaml
    yaml_data = yaml.dump({"moduleId": module_id, "apis": []})
    try:
        interfaces = await InterfaceMapper.query_by(module_id=module_id)
        if interfaces:
            data = {
                "moduleId": module_id,
                "apis": [interface.map for interface in interfaces]
            }
            yaml_data = yaml.dump(data)
        return FastResponse(
            content=yaml_data,
            media_type="text/yaml",
            headers={"Content-Disposition": f"attachment; filename=interfaces_{module_id}.yaml"}
        )
    except Exception as e:
        raise e