#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : case_plan
# @Software: PyCharm
# @Desc: 测试计划接口
from typing import Optional
from fastapi import APIRouter, Depends

from app.controller import Authentication
from app.model.base import User
from app.response import Response
from app.schema.hub.planSchema import (
    AddPlanSchema, UpdatePlanSchema, RemovePlanSchema,
    MoveCaseToCasePlan, PagePlanSchema,
    AssociateRequirementSchema, DisassociateRequirementSchema,
    QueryPlanRequirementsSchema,CopyOneCaseToCasePlan,
    AddPlanModuleSchema, UpdatePlanModuleSchema,
    RemovePlanModuleSchema, MovePlanModuleSchema,
    UpdatePlanCaseStepResultSchema,AssociatePlanCaseSchema,
    RemovePlanCaseSchema, CopyCaseToCasePlan,
    UpdatePlanPhaseSchema,UpdateCaseToCasePlan,UploadCommitSchema
)
from app.schema.hub.testCaseSchema import AddPlanCaseSchema
from app.mapper.test_case.planMapper import PlanMapper
from app.mapper.test_case.planModuleMapper import PlanModuleMapper
from app.mapper.test_case.planCaseMapper import PlanCaseMapper
from utils import log
from app.service.uploadCacheService import UploadCacheService
from common import rc

router = APIRouter(prefix="/hub/plan", tags=['测试计划'])


@router.post("/insert", description="添加测试计划")
async def insert_plan(data: AddPlanSchema, user: User = Depends(Authentication())):
    """
    添加新的测试计划
    :param data: 计划基本信息
    :param user: 认证用户
    :return: 创建的计划ID
    """
    result = await PlanMapper.add_plan(user=user, **data.model_dump(exclude_unset=True))
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

@router.get("/query", description="查询测试计划列表")
async def query_plans(plan_name:str,_: User = Depends(Authentication())):
    """
    查询所有测试计划
    :param _: 认证用户
    :return: 所有计划列表
    """
    data = await PlanMapper.query_by_plan_name(plan_name=plan_name)
    return Response.success(data)

@router.post("/page", description="分页查询测试计划列表")
async def page_plans(data: PagePlanSchema, _: User = Depends(Authentication())):
    """
    根据条件分页查询测试计划列表
    :param data: 分页及筛选参数
    :param _: 认证用户
    :return: 计划分页数据
    """
    result = await PlanMapper.page_query_with_stats(**data.model_dump(exclude_none=True, exclude_unset=True))
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


@router.get("/modules/stats", description="批量获取计划下各模块用例统计")
async def get_plan_modules_stats(plan_id: int, _: User = Depends(Authentication())):
    """
    一次返回计划下所有模块的用例状态分布
    用于替换前端对每个模块单独调用 /api/hub/plan/cases 的 N+1 模式
    :param plan_id: 计划ID
    :param _: 认证用户
    :return: {module_id: {total, passed, failed, pending, blocked, skipped, pass_rate, execution_rate}}
    """
    data = await PlanCaseMapper.get_module_stats(plan_id=plan_id)
    return Response.success(data=data)


@router.post("/case/associate", description="关联用例到计划")
async def associate_cases(data: AssociatePlanCaseSchema, user: User = Depends(Authentication())):
    """
    批量关联用例到计划

    支持两种模式：
    1) 旧模式：仅传 case_ids + plan_module_id，直接把用例挂到指定计划分组下
    2) 新模式：传 module_ids 时，按"按源目录复制/匹配计划目录"处理
       - 对每个源 module 沿 parent_id 走到根
       - 沿途在 plan 里按 title + parent 关系 find-or-create PlanModule
       - 然后按 case.module_id 把用例挂到对应的（新建/复用）plan module
    :param data: 计划ID、用例ID列表、源模块ID列表（可选）
    :param user: 认证用户
    :return: 关联数量
    """
    count = await PlanCaseMapper.associate_cases(
        user=user,
        plan_id=data.plan_id,
        case_ids=data.case_ids,
        plan_module_id=data.plan_module_id,
        module_ids=data.module_ids,
        merge_same_group=data.merge_same_group,
    )
    return Response.success(data={"count": count})


@router.post("/case/remove", description="移除用例关联")
async def remove_case_association(data: RemovePlanCaseSchema, _: User = Depends(Authentication())):
    """
    移除用例与计划的关联
    :param data: 计划用例关联ID
    :param _: 认证用户
    :return: 操作结果
    """
    count = await PlanCaseMapper.remove_association(case_ids=data.case_ids, plan_id=data.plan_id)
    return Response.success(count)


@router.post("/case/updateStepResult", description="更新用例步骤结果")
async def update_case_step_result(data: UpdatePlanCaseStepResultSchema, user: User = Depends(Authentication())):
    """
    更新用例步骤结果
    :param data: 更新数据
    :param user: 认证用户
    :return: 操作结果
    """
    log.info(data)
    await PlanCaseMapper.update_case_step_result(
        **data.model_dump(exclude_unset=True, exclude_none=True),
        user=user
    )
    return Response.success()


@router.post("/cases/move", description="移动计划用例")
async def move_plan_cases(data: MoveCaseToCasePlan, _: User = Depends(Authentication())):
    """
    将计划关联的用例移动到新的分组下
    :param data: 移动参数
    :param _: 认证用户
    :return: 移动数量
    """
    log.info(data)
    values =  await PlanCaseMapper.move_case(
        **data.model_dump()
    )
    return Response.success(values)


@router.post("/cases/copy_one", description="复制单个计划用例")
async def copy_plan_case(data: CopyOneCaseToCasePlan, user: User = Depends(Authentication())):
    """
    复制单个计划用例到新的分组下
    :param data: 种制参数
    :param user: 认证用户
    :return: 种制数量
    """
    log.info(data)
    values =  await PlanCaseMapper.copy_plan_case(
        **data.model_dump(),
        user=user
    )
    return Response.success(values)

@router.post("/cases/copy", description="复制计划用例")
async def copy_plan_cases(data: CopyCaseToCasePlan, user: User = Depends(Authentication())):
    """
    将计划关联的用例复制到新的分组下
    :param data: 种制参数
    :param user: 认证用户
    :return: 种制数量
    """
    log.info(data)
    values =  await PlanCaseMapper.copy_cases(
        **data.model_dump(),
        user=user
    )
    return Response.success(values)


@router.post("/cases/update", description="更新计划用例")
async def update_plan_cases(data: UpdateCaseToCasePlan, user: User = Depends(Authentication())):
    """
    更新计划关联的用例信息
    :param data: 更新参数
    :param user: 认证用户
    :return: 更新数量
    """
    log.info(data)
    values =  await PlanCaseMapper.update_case(
        **data.model_dump(),
        user=user
    )
    return Response.success(values)


@router.post("/cases/insert", description="添加计划用例")
async def insert_plan_cases(data: AddPlanCaseSchema, user: User = Depends(Authentication())):
    """
    添加计划关联的用例
    :param data: 添加参数
    :param user: 认证用户
    """
    log.info(data)
    values =  await PlanCaseMapper.insert_plan_case(
        user=user,
        **data.model_dump(),
    )
    return Response.success(values)

@router.post("/upload/commit", description="确认并入库用例")
async def upload_commit(
        data: UploadCommitSchema,
        user: User = Depends(Authentication())
):
    _cache_service = UploadCacheService(rc)
    if await _cache_service.is_committed(data.file_md5, user.id):
        return Response.error(msg="该文件已提交过，不能重复提交")

    preview_data = await _cache_service.get_preview(data.file_md5, user.id)
    if not preview_data:
        return Response.error(msg="预览数据已过期，请重新上传文件")

    valid_cases = preview_data.get("valid_cases", [])

    if not valid_cases:
        return Response.error(msg="请选择要入库的用例")

    try:
        await PlanCaseMapper.insert_upload_case(
            cases=valid_cases,
            plan_id=data.plan_id,
            plan_module_id=data.plan_module_id,
            user=user,
            is_review=data.is_review,
            first_status=data.first_status,
            second_status=data.second_status,
        )
        await _cache_service.mark_committed(data.file_md5, user.id)
        return Response.success({"imported_count": len(valid_cases)})
    except Exception as e:
        log.exception(f"入库失败: {e}")
        return Response.error(msg=f"入库失败: {str(e)}")




@router.get("/cases", description="获取计划用例列表")
async def get_plan_cases(
    plan_id: int,
    plan_module_id: Optional[int] = None,
    case_level: Optional[str] = None,
    is_review: Optional[int] = None,
    _: User = Depends(Authentication())
):
    """
    分页获取计划关联的用例列表
    :param plan_id: 计划ID
    :param plan_module_id: 计划分组ID
    :param case_level: 用例等级
    :param is_review: 是否审核
    :param current: 当前页
    :param pageSize: 每页大小
    :param _: 认证用户
    :return: 用例分页列表
    """
    result = await PlanCaseMapper.get_plan_cases(
        plan_id=plan_id,
        plan_module_id=plan_module_id,
        case_level=case_level,
        is_review=is_review,
    )
    return Response.success(result)


@router.post("/phase", description="更新计划执行阶段")
async def update_plan_phase(data: UpdatePlanPhaseSchema, user: User = Depends(Authentication())):
    """
    更新计划执行阶段
    :param data: 计划ID和阶段
    :param user: 认证用户
    :return: 操作结果
    """
    log.info(data)
    await PlanMapper.update_by_id(
        update_user=user,
        id=data.plan_id,
        plan_phase=data.plan_phase
    )
    return Response.success()


@router.get("/phase", description="获取计划执行阶段")
async def get_plan_phase(plan_id: int, _: User = Depends(Authentication())):
    """
    获取计划执行阶段
    :param plan_id: 计划ID
    :param _: 认证用户
    :return: 阶段信息
    """
    plan = await PlanMapper.get_by_id(ident=plan_id)
    if not plan:
        return Response.success(data=None)
    return Response.success(data={"plan_phase": plan.plan_phase})


@router.get("/overview", description="获取计划概览统计")
async def get_plan_overview(plan_id: int, _: User = Depends(Authentication())):
    """
    获取计划概览统计数据
    :param plan_id: 计划ID
    :param _: 认证用户
    :return: 统计数据
    """
    data = await PlanCaseMapper.get_overview(plan_id=plan_id)
    return Response.success(data=data)


@router.get("/statistics", description="获取计划详细统计")
async def get_plan_statistics(plan_id: int, _: User = Depends(Authentication())):
    """
    获取计划详细统计数据
    :param plan_id: 计划ID
    :param _: 认证用户
    :return: 详细统计
    """
    data = await PlanCaseMapper.get_statistics(plan_id=plan_id)
    return Response.success(data=data)