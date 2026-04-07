#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
InterfaceGroup Controller

接口分组管理控制器
提供接口分组的增删改查、关联接口管理等功能
"""
from fastapi import APIRouter, Depends

from app.controller import Authentication
from app.mapper.interfaceApi.interfaceGroupMapper import InterfaceGroupMapper
from app.model.base import User
from app.response import Response
from app.schema.api.interfaceGroupSchema import (
    InsertInterfaceGroupSchema,
    GetInterfaceGroupSchema,
    UpdateInterfaceGroupSchema,
    AssociationInterfacesToGroupSchema,
    PageInterfaceGroupSchema,
    OptInterfaceGroupSchema,
)
from utils import log

router = APIRouter(prefix="/interface/group", tags=['自动化接口步骤'])


# ==================== 分组基础管理 ====================

@router.post("/insert", description="添加分组")
async def insert_group(group: InsertInterfaceGroupSchema, creator_user: User = Depends(Authentication())):
    """
    创建新的接口分组

    - **group**: 分组配置信息
    """
    group = await InterfaceGroupMapper.save(creator_user=creator_user, **group.model_dump())
    return Response.success(group)


@router.get("/detail", description="获取分组详情")
async def get_group_detail(group_id: int, _: User = Depends(Authentication())):
    """
    根据分组ID获取分组详细信息

    - **group_id**: 分组ID
    """
    group = await InterfaceGroupMapper.get_by_id(ident=group_id)
    return Response.success(group)


@router.post("/update", description="更新分组")
async def update_group(group: UpdateInterfaceGroupSchema, user: User = Depends(Authentication())):
    """
    更新分组配置信息

    - **group**: 分组更新信息
    """
    await InterfaceGroupMapper.update_by_id(
        user=user,
        **group.model_dump(exclude_unset=True, exclude_none=True)
    )
    return Response.success()


@router.post("/page", description="分页查询分组列表")
async def page_group(group: PageInterfaceGroupSchema, _: User = Depends(Authentication())):
    """
    分页查询分组列表

    - **group**: 分页查询参数
    """
    log.debug(group)
    data = await InterfaceGroupMapper.page_by_module(
        **group.model_dump(exclude_unset=True, exclude_none=True)
    )
    return Response.success(data)


@router.post("/remove", description="删除分组")
async def remove_group(group: GetInterfaceGroupSchema, _: User = Depends(Authentication())):
    """
    删除指定的分组

    - **group**: 包含分组ID
    """
    await InterfaceGroupMapper.remove_group(group.id)
    return Response.success()


# ==================== 分组关联接口管理 ====================

@router.post("/associate/add_interfaces", description="关联接口到分组")
async def associate_interfaces(info: AssociationInterfacesToGroupSchema, _: User = Depends(Authentication())):
    """
    将多个接口关联到分组

    - **info**: 包含分组ID和接口ID列表
    """
    await InterfaceGroupMapper.association_interfaces(**info.model_dump())
    return Response.success()


@router.get("/associate/query_interfaces", description="查询分组关联的接口列表")
async def query_associated_interfaces(group_id: int, _: User = Depends(Authentication())):
    """
    查询分组关联的所有接口

    - **group_id**: 分组ID
    """
    apis = await InterfaceGroupMapper.query_association_interfaces(group_id)
    return Response.success(apis)


@router.post("/associate/copy_interface", description="复制接口到分组")
async def copy_interface_to_group(info: OptInterfaceGroupSchema, user: User = Depends(Authentication())):
    """
    将接口复制到分组

    - **info**: 包含分组ID和接口ID
    """
    await InterfaceGroupMapper.copy_interface(user=user, **info.model_dump())
    return Response.success()


@router.post("/associate/remove_interface", description="从分组中移除接口")
async def remove_associated_interface(info: OptInterfaceGroupSchema, _: User = Depends(Authentication())):
    """
    从分组中移除指定的接口

    - **info**: 包含分组ID和接口ID
    """
    await InterfaceGroupMapper.remove_association_interface(**info.model_dump())
    return Response.success()


@router.post("/associate/reorder_interfaces", description="重排分组中的接口顺序")
async def reorder_associated_interfaces(info: OptInterfaceGroupSchema, _: User = Depends(Authentication())):
    """
    重新排序分组中的接口顺序

    - **info**: 包含分组ID和新的接口顺序列表
    """
    await InterfaceGroupMapper.reorder_interfaces(**info.model_dump())
    return Response.success()
