#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
InterfaceTask Controller

接口任务管理控制器
提供任务的增删改查、关联用例/接口管理、任务执行等功能
"""
from fastapi import APIRouter, Depends

from app.controller import Authentication
from app.mapper.interfaceApi.interfaceTaskMapper import InterfaceTaskMapper
from app.model.base import User
from app.response import Response
from app.schema.api.interfaceTaskSchema import (
    InsertInterfaceTaskSchema,
    UpdateInterfaceTaskSchema,
    OptTaskSchema,
    PageInterfaceTaskSchema,
    AssociationCasesSchema,
    RemoveAssociationCasesSchema,
    ExecuteTask,
    AssociationInterfacesSchema,
    RemoveAssociationInterfacesSchema,
)
from croe.interface.starter import APIStarter
from croe.interface.task import TaskRunner, TaskParams

router = APIRouter(prefix="/interface/task", tags=['自动化接口步骤'])


# ==================== 任务基础管理 ====================

@router.post("/insert", description="创建任务")
async def insert_task(task_info: InsertInterfaceTaskSchema,
                     creator_user: User = Depends(Authentication())):
    """
    创建新的接口任务

    - **task_info**: 任务配置信息
    """
    task = await InterfaceTaskMapper.insert_task(
        user=creator_user,
        **task_info.model_dump(
            exclude_unset=True,
            exclude_none=True
        )
    )
    return Response.success(task)


@router.post("/update", description="修改任务")
async def update_task(update: UpdateInterfaceTaskSchema,
                     updater: User = Depends(Authentication())):
    """
    更新任务配置信息

    - **update**: 任务更新信息
    """
    await InterfaceTaskMapper.update_task(
        update_user=updater,
        **update.model_dump(exclude_unset=True, exclude_none=True)
    )
    return Response.success()


@router.get("/basic", description="获取任务详情")
async def get_task_detail(task_id: int, _: User = Depends(Authentication())):
    """
    根据任务ID获取任务详细信息

    - **task_id**: 任务ID
    """
    task = await InterfaceTaskMapper.get_by_id(ident=task_id)
    return Response.success(task)


@router.post("/remove", description="删除任务")
async def remove_task(task: OptTaskSchema, _: User = Depends(Authentication())):
    """
    删除指定的任务

    - **task**: 包含任务ID
    """
    await InterfaceTaskMapper.delete_by_id(ident=task.task_id)
    return Response.success()


@router.post("/page", description="分页查询任务列表")
async def page_tasks(page_info: PageInterfaceTaskSchema, _: User = Depends(Authentication())):
    """
    分页查询任务列表

    - **page_info**: 分页查询参数
    """
    tasks = await InterfaceTaskMapper.page_by_module(**page_info.model_dump(
        exclude_unset=True,
        exclude_none=True
    ))
    return Response.success(tasks)


# ==================== 关联用例管理 ====================

@router.post("/associate/cases", description="关联用例到任务")
async def associate_cases(info: AssociationCasesSchema, _: User = Depends(Authentication())):
    """
    将多个用例关联到任务

    - **info**: 包含任务ID和用例ID列表
    """
    exist_cases = await InterfaceTaskMapper.association_interface_cases(**info.model_dump())
    return Response.success(exist_cases)


@router.post("/associate/remove_cases", description="从任务中移除用例")
async def remove_associated_cases(info: RemoveAssociationCasesSchema,
                                  _: User = Depends(Authentication())):
    """
    从任务中移除指定的用例

    - **info**: 包含任务ID和用例ID
    """
    await InterfaceTaskMapper.remove_association_interface_case(**info.model_dump())
    return Response.success()


@router.get("/associate/query_cases", description="查询任务关联的用例列表")
async def query_associated_cases(task_id: int, _: User = Depends(Authentication())):
    """
    查询任务关联的所有用例

    - **task_id**: 任务ID
    """
    cases = await InterfaceTaskMapper.query_association_interface_cases(task_id=task_id)
    return Response.success(cases)


@router.post("/associate/reorder_cases", description="重排任务中的用例顺序")
async def reorder_associated_cases(info: AssociationCasesSchema,
                                  _: User = Depends(Authentication())):
    """
    重新排序任务中的用例顺序

    - **info**: 包含任务ID和新的用例顺序列表
    """
    await InterfaceTaskMapper.reorder_interface_case(**info.model_dump())
    return Response.success()


# ==================== 关联接口管理 ====================

@router.post("/associate/interfaces", description="关联接口到任务")
async def associate_interfaces(info: AssociationInterfacesSchema, _: User = Depends(Authentication())):
    """
    将多个接口关联到任务

    - **info**: 包含任务ID和接口ID列表
    """
    exist_apis = await InterfaceTaskMapper.association_interfaces(**info.model_dump())
    return Response.success(exist_apis)


@router.post("/associate/remove_interfaces", description="从任务中移除接口")
async def remove_associated_interfaces(info: RemoveAssociationInterfacesSchema,
                                _: User = Depends(Authentication())):
    """
    从任务中移除指定的接口

    - **info**: 包含任务ID和接口ID
    """
    await InterfaceTaskMapper.remove_association_interface(**info.model_dump())
    return Response.success()


@router.get("/associate/query_interfaces", description="查询任务关联的接口列表")
async def query_associated_interfaces(task_id: int, _: User = Depends(Authentication())):
    """
    查询任务关联的所有接口

    - **task_id**: 任务ID
    """
    apis = await InterfaceTaskMapper.query_association_interfaces(task_id)
    return Response.success(apis)


@router.post("/associate/reorder_interfaces", description="重排任务中的接口顺序")
async def reorder_associated_interfaces(info: AssociationInterfacesSchema,
                                _: User = Depends(Authentication())):
    """
    重新排序任务中的接口顺序

    - **info**: 包含任务ID和新的接口顺序列表
    """
    await InterfaceTaskMapper.reorder_interface(**info.model_dump())
    return Response.success()


# ==================== 任务执行 ====================

@router.post("/execute", description="手动执行任务")
async def execute_task(task: ExecuteTask, starter: User = Depends(Authentication())):
    """
    手动执行接口任务

    - **task**: 包含任务ID和环境ID
    """

    _starter = APIStarter(starter)
    params = TaskParams(
        **task.model_dump()
    )

    await TaskRunner(starter=_starter).execute_task(params)
    return Response.success()


@router.post("/execute_by_jenkins", description="Jenkins触发执行任务")
async def execute_task_by_jenkins(task: ExecuteTask):
    """
    通过 Jenkins 外部调用执行任务

    - **task**: 包含任务ID和环境ID
    """
    from common.redis_worker_pool import r_pool, register_interface_task_RoBot

    task_job = await InterfaceTaskMapper.get_by_id(task.task_id)

    await r_pool.submit_to_redis(
        func=register_interface_task_RoBot,
        job_id=task_job.uid,
        job_name=task_job.interface_task_title,
        job_kwargs={
            "task_id": task_job.id,
            "env_id": task.env_id,
            "options": ["API", "CASE"]
        }
    )
    return Response.success()
