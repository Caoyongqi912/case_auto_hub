#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : case_config
# @Software: PyCharm
# @Desc: 用例枚举配置管理路由
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.controller import Authentication
from app.mapper.test_case.caseConfigMapper import CaseConfigMapper
from app.model.base import User
from app.response import Response
from app.schema.hub.caseConfigSchema import (
    AddCaseConfigSchema,
    PageCaseConfigSchema,
    RemoveCaseConfigSchema,
    UpdateCaseConfigSchema,
)

router = APIRouter(prefix="/hub/caseConfig", tags=["用例-枚举配置"])




@router.post("/page", description="分页查询用例枚举配置")
async def page_case_config(
    data: PageCaseConfigSchema,
    _: User = Depends(Authentication()),
):
    """
    分页查询用例枚举配置
    """
    result = await CaseConfigMapper.page_query(
        **data.model_dump(exclude_unset=True, exclude_none=True),
    )
    return Response.success(result)


@router.post("/add", description="新增用例枚举配置")
async def add_case_config(
    data: AddCaseConfigSchema,
    user: User = Depends(Authentication()),
):
    """
    新增用例枚举配置

    :param data: ICaseEnumConfig 全量字段
    :param user: 认证用户（用于写入创建人）
    :return: { code, msg, data: null }
    """
    await CaseConfigMapper.add_config(
        user=user,
        **data.model_dump(exclude_unset=True, exclude_none=True),
    )
    return Response.success()


@router.post("/update", description="更新用例枚举配置")
async def update_case_config(
    data: UpdateCaseConfigSchema,
    user: User = Depends(Authentication()),
):
    """
    更新用例枚举配置

    :param data: 必传 uid，其余字段可选（仅更新传入字段）
    :param user: 认证用户
    :return: { code, msg, data: null }
    """
    await CaseConfigMapper.update_config(
        user=user,
        **data.model_dump(exclude_unset=True, exclude_none=True),
    )
    return Response.success()


@router.post("/remove", description="删除用例枚举配置")
async def remove_case_config(
    data: RemoveCaseConfigSchema,
    _: User = Depends(Authentication()),
):
    """
    通过 uid 删除用例枚举配置

    :param data: { uid }
    :return: { code, msg, data: null }
    """
    await CaseConfigMapper.remove_config(uid=data.uid)
    return Response.success()


@router.get("/query", description="根据 config_key 全量查询启用中的枚举配置")
async def query_case_config(
    config_key: str = Query(..., min_length=1, description="配置键，如 CASE_STATUS"),
    enabled_only: Optional[bool] = Query(True, description="是否只查询启用的配置"),
    _: User = Depends(Authentication()),
):
    """
    根据 config_key 全量查询启用中的枚举配置（按 sort 升序）

    :return: { code, data: [...] }
    """
    rows = await CaseConfigMapper.query_by_key(
        config_key=config_key,
        enabled_only=enabled_only,
    )
    return Response.success([row.to_dict() for row in rows])
