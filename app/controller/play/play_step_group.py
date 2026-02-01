#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/8
# @Author : cyq
# @File : play_step_group
# @Software: PyCharm
# @Desc:
from fastapi import APIRouter, Depends

from app.controller import Authentication
from app.mapper.play.playStepGroupMapper import PlayStepGroupMapper
from app.model.base import User
from app.response import Response
from app.schema.play.playGroupSchema import *

router = APIRouter(prefix="/play/stepGroup", tags=['自动化用例组'])


@router.post("/insert", description="插入组")
async def insert_group(group: InsertPlayGroupSchema, creator_user: User = Depends(Authentication())):
    """
    插入新的自动化用例组

    Args:
        group: 用例组信息
        creator_user: 当前登录用户

    Returns:
        插入成功的用例组信息
    """
    group = await PlayStepGroupMapper.save(**group.model_dump(), creator_user=creator_user)
    return Response.success(group)


@router.get("/detail", description="组详情")
async def get_group(group_id: int, _: User = Depends(Authentication())):
    """
    获取用例组详情信息

    Args:
        group_id: 用例组ID
        _: 当前登录用户（未使用）

    Returns:
        用例组详细信息
    """
    data = await PlayStepGroupMapper.get_by_id(ident=group_id)
    return Response.success(data)


@router.post("/update", description="修改组")
async def update_group(group: EditPlayStepSchema, user: User = Depends(Authentication())):
    """
    更新用例组信息

    Args:
        group: 用例组更新信息
        user: 当前登录用户

    Returns:
        更新后的用例组信息
    """
    group = await PlayStepGroupMapper.update_by_id(**group.model_dump(
        exclude_unset=True,
        exclude_none=True
    ), updateUser=user)
    return Response.success(group)


@router.post("/remove", description="删除组")
async def remove_group(group: GetPlayStepGroupByIdSchema, _: User = Depends(Authentication())):
    """
    删除指定的用例组

    Args:
        group: 包含用例组ID的参数
        _: 当前登录用户（未使用）

    Returns:
        删除成功响应
    """
    await PlayStepGroupMapper.remove_group(group_id=group.group_id)
    return Response.success()


@router.post("/copy", description="复制组")
async def copy_group(group: GetPlayStepGroupByIdSchema, user: User = Depends(Authentication())):
    """
    复制指定的用例组

    Args:
        group: 包含用例组ID的参数
        user: 当前登录用户

    Returns:
        删除成功响应
    """
    await PlayStepGroupMapper.copy_group(group_id=group.group_id, user=user)
    return Response.success()


@router.post("/page", description="分页")
async def page_step(pageInfo: PagePlayGroupSchema, _: User = Depends(Authentication())):
    """
    分页查询用例组列表

    Args:
        pageInfo: 分页查询参数
        _: 当前登录用户（未使用）

    Returns:
        分页查询结果
    """
    data = await PlayStepGroupMapper.page_by_module(**pageInfo.model_dump(
        exclude_unset=True,
        exclude_none=True
    ))
    return Response.success(data)


@router.get("/querySteps", description="查询步骤")
async def query_sub_steps(group_id: int, _: User = Depends(Authentication())):
    """
    查询指定用例组下的所有步骤

    Args:
        group_id: 用例组ID
        _: 当前登录用户（未使用）

    Returns:
        步骤列表
    """
    data = await PlayStepGroupMapper.query_steps_by_group_id(group_id)
    return Response.success(data)


@router.post("/insertStep", description="插入子私有步骤")
async def insert_sub_step(step: InsertPlayGroupStepSchema, user: User = Depends(Authentication())):
    """
    插入私有子步骤到用例组

    Args:
        step: 步骤信息
        user: 当前登录用户

    Returns:
        插入成功响应
    """
    await PlayStepGroupMapper.insert_play_step(**step.model_dump(), user=user)
    return Response.success()


@router.post("/copyStep", description="复制子步骤")
async def copy_sub_step(step: CopyRemovePlayGroupStepSchema, user: User = Depends(Authentication())):
    """
    复制子步骤

    Args:
        step: 步骤复制参数
        user: 当前登录用户

    Returns:
        复制成功响应
    """
    await PlayStepGroupMapper.copy_step(**step.model_dump(), user=user)
    return Response.success()


@router.post("/removeStep", description="删除子步骤")
async def remove_sub_step(step: CopyRemovePlayGroupStepSchema, cr: User = Depends(Authentication())):
    """
    删除子步骤

    Args:
        step: 步骤删除参数
        cr: 当前登录用户（未使用）

    Returns:
        删除成功响应
    """
    await PlayStepGroupMapper.remove_step(**step.model_dump())
    return Response.success()


@router.post("/reorderSteps", description="调整子步骤")
async def reorder_sub_step(step: ReOrderPlayStepsSchema, _: User = Depends(Authentication())):
    """
    调整子步骤顺序

    Args:
        step: 步骤重排序参数
        _: 当前登录用户（未使用）

    Returns:
        重排序成功响应
    """
    await PlayStepGroupMapper.reorder_step(**step.model_dump())
    return Response.success()


@router.post("/associationPlayGroupStep", description="关联公共步骤")
async def association_play_step(association: AssociationPlayGroupStepSchema, user: User = Depends(Authentication())):
    """
    关联公共步骤到用例组

    Args:
        association: 关联参数
        user: 当前登录用户

    Returns:
        关联成功响应
    """
    await PlayStepGroupMapper.association_steps(**association.model_dump(), user=user)
    return Response.success()


@router.get('/query_steps', description='查询关联公共步骤')
async def query_groups_steps(group_id: int, _: User = Depends(Authentication())):
    """
    查询关联的公共步骤

    Args:
        group_id: 用例组ID
        _: 当前登录用户（未使用）

    Returns:
        关联的公共步骤列表
    """
    data = await PlayStepGroupMapper.query_steps_by_group_id(group_id)
    return Response.success(data)
