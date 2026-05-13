#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : case_plan
# @Software: PyCharm
# @Desc: 测试计划接口
from fastapi import APIRouter, Depends

from app.controller import Authentication
from app.model.base import User
from app.response import Response
from app.schema.hub.planSchema import (
    AddPlanSchema, UpdatePlanSchema, RemovePlanSchema,
    GetPlanSchema, PagePlanSchema,
    AssociateRequirementSchema, DisassociateRequirementSchema,
    QueryPlanRequirementsSchema,
    AddPlanModuleSchema, UpdatePlanModuleSchema,
    RemovePlanModuleSchema, MovePlanModuleSchema
)
from app.mapper.test_case.planMapper import PlanMapper
from app.mapper.test_case.planModuleMapper import PlanModuleMapper
from utils import log

router = APIRouter(prefix="/hub/plan", tags=['测试计划'])


@router.post("/insert", description="添加测试计划")
async def insert_plan(data: AddPlanSchema, user: User = Depends(Authentication())):
    """
    添加新的测试计划
    :param data: 计划基本信息
    :param user: 认证用户
    :return: 创建的计划ID
    """
    result = await PlanMapper.save(creator_user=user, **data.model_dump(exclude_unset=True))
    return Response.success(result)


@router.post("/update", description="更新测试计划信息")
async def update_plan(data: UpdatePlanSchema, user: User = Depends(Authentication())):
    """
    根据计划ID更新计划信息
    :param data: 计划更新数据
    :param user: 认证用户
    :return: 操作结果
    """
    log.info(data)
    await PlanMapper.update_by_id(update_user=user, **data.model_dump(exclude_unset=True, exclude_none=True))
    return Response.success()


@router.post("/remove", description="删除测试计划")
async def remove_plan(data: RemovePlanSchema, _: User = Depends(Authentication())):
    """
    根据计划ID删除指定的测试计划
    :param data: 计划ID
    :param _: 认证用户
    :return: 操作结果
    """
    await PlanMapper.delete_by_id(ident=data.plan_id)
    return Response.success()


@router.get("/info", description="获取测试计划信息")
async def get_plan_info(plan_id: int, _: User = Depends(Authentication())):
    """
    获取指定的测试计划详情
    :param plan_id: 计划ID
    :param _: 认证用户
    :return: 计划信息
    """
    data = await PlanMapper.plan_info(plan_id=plan_id)
    return Response.success(data)


@router.post("/page", description="分页查询测试计划列表")
async def page_plans(data: PagePlanSchema, _: User = Depends(Authentication())):
    """
    根据条件分页查询测试计划列表
    :param data: 分页及筛选参数
    :param _: 认证用户
    :return: 计划分页数据
    """
    log.info(data.model_dump(exclude_none=True, exclude_unset=True))
    result = await PlanMapper.page_query(**data.model_dump(exclude_none=True, exclude_unset=True))
    return Response.success(result)


@router.post("/associateRequirements", description="关联需求到计划")
async def associate_requirements(data: AssociateRequirementSchema, _: User = Depends(Authentication())):
    """
    将多个需求关联到指定计划
    :param data: 计划ID和需求ID列表
    :param _: 认证用户
    :return: 关联结果
    """
    count = await PlanMapper.associate_requirements(
        plan_id=data.plan_id,
        requirement_ids=data.requirement_ids
    )
    return Response.success(data={"count": count})


@router.post("/disassociateRequirements", description="解除计划关联的需求")
async def disassociate_requirements(data: DisassociateRequirementSchema, _: User = Depends(Authentication())):
    """
    解除计划关联的多个需求
    :param data: 计划ID和需求ID列表
    :param _: 认证用户
    :return: 解除关联结果
    """
    count = await PlanMapper.disassociate_requirements(
        plan_id=data.plan_id,
        requirement_ids=data.requirement_ids
    )
    return Response.success(data={"count": count})


@router.get("/requirements", description="查询计划关联的需求列表")
async def get_plan_requirements(plan_id: int, _: User = Depends(Authentication())):
    """
    查询指定计划关联的所有需求
    :param plan_id: 计划ID
    :param _: 认证用户
    :return: 需求列表
    """
    requirements = await PlanMapper.get_associated_requirements(plan_id=plan_id)
    return Response.success(data=requirements)


@router.post("/queryRequirements", description="根据需求字段查询关联需求")
async def query_plan_requirements(data: QueryPlanRequirementsSchema, _: User = Depends(Authentication())):
    """
    根据需求名称、等级、进度等字段筛选查询计划关联的需求
    :param data: 查询条件
    :param _: 认证用户
    :return: 需求列表
    """
    log.info(data)
    requirements = await PlanMapper.query_requirements_by_field(
        plan_id=data.plan_id,
        requirement_name=data.requirement_name,
        requirement_level=data.requirement_level,
        process=data.process
    )
    return Response.success(data=requirements)


@router.post("/module/insert", description="添加计划分组")
async def insert_module(data: AddPlanModuleSchema, user: User = Depends(Authentication())):
    """
    在计划下创建新的分组
    :param data: 分组信息
    :param user: 认证用户
    :return: 创建的分组
    """
    result = await PlanModuleMapper.add_module(
        plan_id=data.plan_id,
        title=data.title,
        user=user,
        parent_id=data.parent_id,
        order=data.order or 0
    )
    return Response.success(result)


@router.post("/module/update", description="更新计划分组")
async def update_module(data: UpdatePlanModuleSchema, user: User = Depends(Authentication())):
    """
    更新计划分组信息
    :param data: 更新数据
    :param user: 认证用户
    :return: 操作结果
    """
    log.info(data)
    await PlanModuleMapper.update_module(
        module_id=data.id,
        user=user,
        title=data.title,
        parent_id=data.parent_id,
        order=data.order
    )
    return Response.success()


@router.post("/module/remove", description="删除计划分组")
async def remove_module(data: RemovePlanModuleSchema, _: User = Depends(Authentication())):
    """
    删除计划分组（级联删除子分组）
    :param data: 分组ID
    :param _: 认证用户
    :return: 删除数量
    """
    count = await PlanModuleMapper.remove_module(module_id=data.module_id)
    return Response.success(data={"count": count})


@router.post("/module/move", description="移动计划分组")
async def move_module(data: MovePlanModuleSchema, _: User = Depends(Authentication())):
    """
    将分组移动到新的父级分组下
    :param data: 移动参数
    :param _: 认证用户
    :return: 操作结果
    """
    log.info(data)
    await PlanModuleMapper.move_module(
        module_id=data.module_id,
        new_parent_id=data.new_parent_id,
        order=data.order
    )
    return Response.success()


@router.get("/modules", description="获取计划分组树")
async def get_module_tree(plan_id: int, _: User = Depends(Authentication())):
    """
    获取计划下所有分组（树形结构）
    :param plan_id: 计划ID
    :param _: 认证用户
    :return: 树形分组列表
    """
    modules = await PlanModuleMapper.build_tree(plan_id=plan_id)
    return Response.success(data=modules)