#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/3
# @Author : cyq
# @File : play_step
# @Software: PyCharm
# @Desc:

from fastapi import APIRouter, Depends

from app.controller import Authentication
from app.mapper.play.playStepMapper import PlayStepV2Mapper
from app.model.base import User
from app.response import Response
from app.schema.play import InsertPlayStepSchema, CopyPlayStepSchema
from app.schema.play.playStepSchema import EditPlayStepSchema, RemovePlayStepByIdSchema, PageCommonPlayStepSchema
from utils import log

router = APIRouter(prefix="/play/step", tags=['公共步骤管理'])


@router.post("/insert", description="插入步骤")
async def insert_step(stepInfo: InsertPlayStepSchema, user: User = Depends(Authentication())):
    """
    新增公共步骤

    Args:
        stepInfo: 步骤信息
        user: 当前登录用户

    Returns:
        新增成功的步骤信息
    """
    step = await PlayStepV2Mapper.save(
        creator_user=user,
        **stepInfo.model_dump(
            exclude_none=True,
            exclude_unset=True
        )
    )
    return Response.success(step)


@router.get("/detail", description="步骤详情")
async def get_step_detail(step_id: int, _: User = Depends(Authentication())):
    """
    获取公共步骤详情信息

    Args:
        step_id: 步骤ID
        _: 当前登录用户（未使用）

    Returns:
        步骤详细信息
    """
    step = await PlayStepV2Mapper.get_by_id(ident=step_id)
    return Response.success(step)


@router.post("/edit", description="修改步骤")
async def update_step(stepInfo: EditPlayStepSchema, user: User = Depends(Authentication())):
    """
    更新公共步骤信息

    Args:
        stepInfo: 步骤更新信息
        user: 当前登录用户

    Returns:
        更新后的步骤信息
    """
    log.info(stepInfo)
    step = await PlayStepV2Mapper.update_step(
        updateUser=user,
        **stepInfo.model_dump(
            exclude_none=True,
            exclude_unset=True
        ))
    return Response.success(step)


@router.post("/remove", description="删除步骤")
async def remove_step(stepInfo: RemovePlayStepByIdSchema, _: User = Depends(Authentication())):
    """
    删除公共步骤

    Args:
        stepInfo: 包含步骤ID的参数
        _: 当前登录用户（未使用）

    Returns:
        删除成功响应
    """
    await PlayStepV2Mapper.delete_by_id(ident=stepInfo.step_id)
    return Response.success()


@router.post("/page", description="分页")
async def page_step(pageInfo: PageCommonPlayStepSchema, _: User = Depends(Authentication())):
    """
    分页查询公共步骤列表

    Args:
        pageInfo: 分页查询参数
        _: 当前登录用户（未使用）

    Returns:
        分页查询结果
    """
    data = await PlayStepV2Mapper.page_by_module(**pageInfo.model_dump(
        exclude_unset=True,
        exclude_none=True
    ))
    return Response.success(data)


@router.post("/copy", description="step 复制")
async def copy_step(step: CopyPlayStepSchema, user: User = Depends(Authentication())):
    """
    复制公共步骤

    Args:
        step: 步骤复制参数，包含步骤ID和是否为公共步骤标识
        user: 当前登录用户

    Returns:
        复制后的步骤信息
    """
    data = await PlayStepV2Mapper.copy_step(step_id=step.step_id,
                                            user=user,
                                            copy_step_name=False,
                                            is_common=step.is_common)
    return Response.success(data)
