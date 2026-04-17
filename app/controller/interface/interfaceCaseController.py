#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
InterfaceCase Controller

接口用例管理控制器
提供用例的增删改查、关联接口、条件、循环等功能
"""
import asyncio

from fastapi import APIRouter
from fastapi.params import Depends

from app.controller import Authentication
from app.mapper.interfaceApi.interfaceCaseContentMapper import InterfaceCaseContentMapper
from app.mapper.interfaceApi.interfaceCaseMapper import InterfaceCaseMapper
from app.mapper.interfaceApi.interfaceConditionMapper import InterfaceConditionMapper
from app.mapper.interfaceApi.interfaceLoopMapper import InterfaceLoopMapper
from app.mapper.interfaceApi.interfaceVarsMapper import InterfaceVarsMapper
from app.mapper.project.dbConfigMapper import DBExecuteMapper
from app.model.base import User
from app.response import Response
from app.schema.api.interfaceCaseSchema import (
    AddInterfaceCaseSchema,
    UpdateInterfaceCaseSchema,
    OptInterfaceCaseSchema,
    PageInterfaceCaseSchema,
    AssociationApisSchema,
    CopyContentStepSchema,
    AssociationLoopSchema,
    UpdateLoopSchema,
    AssociationLoopAPISchema,
    AssociationConditionSchema,
    AssociationConditionAPISchema,
    UpdateConditionSchema,
    ExecuteInterfaceCaseSchema,
    RemoveCaseContentSchema,
    ReorderContentStepSchema, AssociationApiSchema, ReorderAssociationConditionAPISchema, CreateConditionAPISchema,
    AssociationGroupSchema, InsertCaseContentStepSchema, UpdateCaseContentStepSchema, AssociationDBSchema,
    UpdateAssociationDBSchema,
)
from app.schema.base import AddVarsSchema, UpdateVarsSchema, DeleteVarsSchema
from app.schema.base.vars import QueryVarsSchema
from app.schema.interface import (
    RemoveAssociationLoopAPISchema,
    RemoveAssociationConditionAPISchema,
)
from croe.interface.runner import InterfaceRunner
from croe.interface.starter import APIStarter
from utils import log

router = APIRouter(prefix="/interfaceCase", tags=['自动化业务接口'])


# ==================== 用例基础管理 ====================

@router.post("/insert", description="插入用例基本信息")
async def insert_case(info: AddInterfaceCaseSchema, creator_user: User = Depends(Authentication())):
    """
    创建新的接口用例

    - **info**: 用例基本信息
    """
    case = await InterfaceCaseMapper.insert_interface_case(
        user=creator_user,
        **info.model_dump()
    )
    return Response.success(case)


@router.get("/basic", description="获取用例基本信息")
async def get_case_basic_info(case_id: int, _: User = Depends(Authentication())):
    """
    根据用例ID获取用例基本信息

    - **case_id**: 用例ID
    """
    case = await InterfaceCaseMapper.get_by_id(ident=case_id)
    return Response.success(case)


@router.post("/page", description="分页查询用例列表")
async def page_case(page_info: PageInterfaceCaseSchema, _=Depends(Authentication())):
    """
    分页查询用例列表，支持按模块ID等条件筛选

    - **page_info**: 分页查询参数
    """
    cases = await InterfaceCaseMapper.page_by_module(**page_info.model_dump(
        exclude_unset=True,
        exclude_none=True,
    ))
    return Response.success(cases)


@router.post("/update", description="修改用例基本信息")
async def update_case_base_info(info: UpdateInterfaceCaseSchema, user: User = Depends(Authentication())):
    """
    更新用例基本信息

    - **info**: 用例更新信息
    """
    await InterfaceCaseMapper.update_interface_case(
        user=user,
        **info.model_dump(exclude_none=True)
    )
    return Response.success()


@router.post("/remove", description="删除用例")
async def remove_case(info: OptInterfaceCaseSchema, _: User = Depends(Authentication())):
    """
    根据用例ID删除用例

    - **info**: 包含用例ID
    """
    await InterfaceCaseMapper.remove_case(info.case_id)
    return Response.success()


@router.post("/copy", description="复制用例")
async def copy_case(info: OptInterfaceCaseSchema, user: User = Depends(Authentication())):
    """
    复制指定用例，创建新的用例副本

    - **info**: 包含源用例ID
    """
    await InterfaceCaseMapper.copy_case(
        case_id=info.case_id,
        user=user
    )
    return Response.success()


# ==================== 用例内容步骤管理 ====================


@router.post("/content/insert", description="添加步骤")
async def insert_content(info: InsertCaseContentStepSchema, user: User = Depends(Authentication())):
    """
    复制用例中的指定步骤

    - **info**: 包含用例ID和内容步骤ID
    """
    await InterfaceCaseMapper.associate_content(
        **info.model_dump(),
        user=user
    )
    return Response.success()


@router.post("/content/update", description="更新步骤")
async def update_content(info: UpdateCaseContentStepSchema, _: User = Depends(Authentication())):
    """
    复制用例中的指定步骤

    - **info**: 包含用例ID和内容步骤ID
    """
    content =  await InterfaceCaseContentMapper.update_content(
        **info.model_dump(exclude_none=True, exclude_unset=True),
    )
    return Response.success(content)


@router.post("/content/copy_step", description="复制步骤")
async def copy_step(info: CopyContentStepSchema, user: User = Depends(Authentication())):
    """
    复制用例中的指定步骤

    - **info**: 包含用例ID和内容步骤ID
    """
    await InterfaceCaseMapper.copy_step(
        **info.model_dump(),
        user=user
    )
    return Response.success()


@router.post("/content/remove_step", description="从用例中移除步骤")
async def remove_step(remove_info: RemoveCaseContentSchema, _=Depends(Authentication())):
    """
    从用例中移除指定的步骤

    - **remove_info**: 包含用例ID和内容步骤ID
    """
    await InterfaceCaseMapper.remove_step(**remove_info.model_dump())
    return Response.success()


@router.get("/content/query_contents", description="查询用例关联的步骤列表")
async def query_contents(case_id: int, _=Depends(Authentication())):
    """
    查询用例关联的所有步骤

    - **case_id**: 用例ID
    """
    contents = await InterfaceCaseMapper.query_steps(case_id=case_id)
    return Response.success(contents)


@router.post("/content/reorder_contents", description="重新排序用例内容步骤")
async def reorder_content(order_info: ReorderContentStepSchema, _=Depends(Authentication())):
    """
    重新排序用例中的步骤顺序

    - **order_info**: 包含用例ID和新的步骤顺序列表
    """
    await InterfaceCaseMapper.reorder_steps(**order_info.model_dump())
    return Response.success()


# ==================== 关联接口管理 ====================

@router.post("/associate/associate_interface", description="关联接口到用例")
async def associate_interface(interface: AssociationApiSchema, user: User = Depends(Authentication())):
    """
    将多个接口关联到用例

    - **interfaces**: 包含用例ID和接口ID列表
    return interface
    """
    data = await InterfaceCaseMapper.associate_interface(**interface.model_dump(), user=user)
    return Response.success(data)


@router.post("/associate/associate_interfaces", description="关联接口到用例")
async def associate_interfaces(interfaces: AssociationApisSchema, user: User = Depends(Authentication())):
    """
    将多个接口关联到用例

    - **interfaces**: 包含用例ID和接口ID列表
    """
    await InterfaceCaseMapper.associate_interfaces(**interfaces.model_dump(), user=user)
    return Response.success()


# ==================== 关联接口组管理 ====================


@router.post("/associate/associate_group")
async def associate_group(group: AssociationGroupSchema, user: User = Depends(Authentication())):
    await InterfaceCaseMapper.associate_groups(**group.model_dump(), user=user)
    return Response.success()


# =================  db ==============

@router.post("/associate/associate_db")
async def associate_db(db_info:AssociationDBSchema, user: User = Depends(Authentication())):
    await InterfaceCaseMapper.associate_db(user=user,**db_info.model_dump())
    return Response.success()


@router.post("/associate/update_db")
async def update_db(db_info:UpdateAssociationDBSchema, user: User = Depends(Authentication())):
    await DBExecuteMapper.update_by_id(user=user,**db_info.model_dump(exclude_none=True))
    return Response.success()

# ==================== 循环管理 ====================

@router.post("/associate/associate_loop", description="添加循环内容")
async def associate_loop(loop: AssociationLoopSchema, user: User = Depends(Authentication())):
    """
    为用例添加循环控制

    - **loop**: 循环配置信息
    """
    loop_data = await InterfaceCaseMapper.associate_loop(**loop.model_dump(exclude_none=True), user=user)
    return Response.success(loop_data)


@router.post("/associate/update_loop", description="更新循环内容")
async def update_loop(loop: UpdateLoopSchema, user: User = Depends(Authentication())):
    """
    更新用例中的循环配置

    - **loop**: 循环更新信息
    """
    loop = await InterfaceLoopMapper.update_by_id(**loop.model_dump(exclude_none=True), update_user=user)
    return Response.success(loop)


@router.post("/associate/associate_loop_interface", description="关联接口到循环")
async def association_loop_interface(association_loop: AssociationLoopAPISchema,
                                     user: User = Depends(Authentication())):
    """
    将接口关联到循环中

    - **association_loop_interface**: 包含循环ID和接口ID列表
    """
    data = await InterfaceLoopMapper.associate_interfaces(user=user, **association_loop.model_dump())
    return Response.success(data)


@router.post("/associate/remove_loop_interface", description="从循环中移除接口")
async def remove_loop_interface(association_loop: RemoveAssociationLoopAPISchema,
                                _: User = Depends(Authentication())):
    """
    从循环中移除指定的接口

    - **association_loop_interface**: 包含循环ID和接口ID
    """
    await InterfaceLoopMapper.disassociate_api(**association_loop.model_dump())
    return Response.success()


@router.post("/associate/reorder_loop_interfaces", description="重排循环中的接口顺序")
async def reorder_loop_interfaces(association_loop: AssociationLoopAPISchema,
                                  _: User = Depends(Authentication())):
    """
    重新排序循环中的接口顺序

    - **association_loop_interface**: 包含循环ID和新的接口顺序列表
    """
    await InterfaceLoopMapper.reorder_loop_apis(**association_loop.model_dump())
    return Response.success()


@router.get("/associate/get_loop_content", description="查询循环内容详情")
async def get_loop_content(loop_id: int, _: User = Depends(Authentication())):
    """
    根据循环ID查询循环内容详情

    - **loop_id**: 循环ID
    """
    data = await InterfaceLoopMapper.get_by_id(loop_id)
    return Response.success(data)


@router.get("/associate/query_loop_interface", description="查询循环接口")
async def query_loop_interface(loop_id: int, _: User = Depends(Authentication())):
    """
    根据循环ID查询循环内容详情

    - **loop_id**: 循环ID
    """
    data = await InterfaceLoopMapper.query_interfaces_by_loop_id(loop_id)
    return Response.success(data)


# ==================== 条件管理 ====================

@router.post("/condition/insert_condition", description="初始化条件")
async def init_condition(info: AssociationConditionSchema, user: User = Depends(Authentication())):
    await InterfaceCaseMapper.associate_condition(**info.model_dump(), user=user)
    return Response.success()


@router.get("/condition/get_condition_content", description="查询条件内容详情")
async def get_condition_content(condition_id: int, _: User = Depends(Authentication())):
    """
    根据条件ID查询条件内容详情

    - **condition_id**: 条件ID
    """
    data = await InterfaceConditionMapper.get_by_id(condition_id)
    return Response.success(data)


@router.post("/condition/update_condition_content", description="更新条件内容")
async def update_condition_content(condition: UpdateConditionSchema, user: User = Depends(Authentication())):
    """
    更新条件配置

    - **condition**: 条件更新信息
    """
    await InterfaceConditionMapper.update_by_id(**condition.model_dump(), update_user=user)
    return Response.success()


@router.get("/condition/query_condition_apis", description="查询条件关联的接口列表")
async def query_condition_apis(content_condition_id: int, _: User = Depends(Authentication())):
    """
    查询条件关联的所有接口

    - **content_condition_id**: 条件ID
    """
    data = await InterfaceConditionMapper.query_interfaces_by_condition_id(content_condition_id)
    return Response.success(data)


@router.post("/condition/associate_condition_api", description="关联接口到条件")
async def associate_condition_api(association_condition_api: AssociationConditionAPISchema,
                                  user: User = Depends(Authentication())):
    """
    将接口关联到条件中

    - **association_condition_api**: 包含条件ID和接口ID列表
    """
    data = await InterfaceConditionMapper.associate_interfaces(user=user, **association_condition_api.model_dump())
    return Response.success(data)


@router.post("/condition/create_condition_api", description="关联接口到条件")
async def create_condition_api(condition: CreateConditionAPISchema,
                               user: User = Depends(Authentication())):
    """
    创建私有接口关联到条件中

    - **association_condition_api**: 包含条件ID和接口ID列表
    """
    data = await InterfaceConditionMapper.associate_self_interface(user=user, **condition.model_dump())
    return Response.success(data)


@router.post("/condition/remove_condition_api", description="从条件中移除接口")
async def remove_condition_api(remove_condition: RemoveAssociationConditionAPISchema,
                               _: User = Depends(Authentication())):
    """
    从条件中移除指定的接口

    - **remove_condition_api**: 包含条件ID和接口ID
    """
    await InterfaceConditionMapper.remove_association_interface(**remove_condition.model_dump())
    return Response.success()


@router.post("/condition/reorder_condition_apis", description="重排条件中的接口顺序")
async def reorder_condition_apis(association_condition: ReorderAssociationConditionAPISchema,
                                 _: User = Depends(Authentication())):
    """
    重新排序条件中的接口顺序

    - **association_condition_api**: 包含条件ID和新的接口顺序列表
    """
    await InterfaceConditionMapper.reorder_condition_apis(**association_condition.model_dump())
    return Response.success()




# === vars ====


@router.post('/vars/add', description='添加变量')
async def add_vars(varInfo: AddVarsSchema, user: User = Depends(Authentication())):
    await InterfaceVarsMapper.insert_vars(user=user,
                                          **varInfo.model_dump(exclude_none=True, exclude_unset=True))

    return Response.success()


@router.post('/vars/update', description='修改变量')
async def update_vars(varInfo: UpdateVarsSchema, user: User = Depends(Authentication())):
    await InterfaceVarsMapper.update_by_uid(update_user=user, **varInfo.model_dump(exclude_none=True,
                                                                                   exclude_unset=True))

    return Response.success()


@router.post('/vars/remove', description='删除变量')
async def remove_vars(varInfo: DeleteVarsSchema, _: User = Depends(Authentication())):
    await InterfaceVarsMapper.delete_by_uid(**varInfo.model_dump())
    return Response.success()


@router.post('/vars/query', description='查询变量')
async def query_vars(varsInfo: QueryVarsSchema, _: User = Depends(Authentication())):
    datas = await InterfaceVarsMapper.query_by(**varsInfo.model_dump())
    return Response.success(datas)




@router.post("/execute/io", description="用例执行")
async def execute_case_api(case: ExecuteInterfaceCaseSchema, starter: User = Depends(Authentication())):
    _starter = APIStarter(starter)
    # asyncio.create_task()
    try:
        await InterfaceRunner(starter=_starter,
                              ).run_interface_case(interface_case_id=case.case_id,
                                                   env=case.env_id,
                                                   error_stop=case.error_stop
                                                   )
    except Exception as e:
        log.exception(e)
    return Response.success()


@router.post("/execute/back", description="用例执行")
async def execute_case_api(case: ExecuteInterfaceCaseSchema, starter: User = Depends(Authentication())):
    _starter = APIStarter(starter)
    asyncio.create_task(InterfaceRunner(starter=_starter,
                                        ).run_interface_case(interface_case_id=case.case_id,
                                                             env=case.env_id,
                                                             error_stop=case.error_stop
                                                             ))
    return Response.success()