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
from app.exception import CommonError
from app.model.base import User
from app.response import Response
from app.schema.hub.planSchema import (
    AddPlanSchema, UpdatePlanSchema, RemovePlanSchema,
    MoveCaseToCasePlan, PagePlanSchema,
    AssociateRequirementSchema, DisassociateRequirementSchema,
    QueryPlanRequirementsSchema, PagePlanRequirementsSchema,
    CopyOneCaseToCasePlan,
    AddPlanModuleSchema, UpdatePlanModuleSchema,
    RemovePlanModuleSchema, MovePlanModuleSchema,
    UpdatePlanCaseStepResultSchema,AssociatePlanCaseSchema,
    RemovePlanCaseSchema, CopyCaseToCasePlan,
    UpdateCaseToCasePlan,UploadCommitSchema,
    M2PlanImportCommitSchema,
    ReorderPlanCaseSchema,BulkReorderPlanCaseSchema,
    PlanListStatisticsSchema
)
from app.schema.hub.testCaseSchema import AddPlanCaseSchema
from app.mapper.test_case.planMapper import PlanMapper
from app.mapper.test_case.planModuleMapper import PlanModuleMapper
from app.mapper.test_case.planCaseMapper import PlanCaseMapper
from utils import log
from app.service.uploadCacheService import UploadCacheService
from app.service.m2PlanImportService import M2PlanImportService
from common import rc

router = APIRouter(prefix="/hub/plan", tags=['测试计划'])
_cache_service = UploadCacheService(rc)


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


@router.post("/statistics/list", description="测试计划全量统计")
async def plan_statistics(data: PlanListStatisticsSchema, _: User = Depends(Authentication())):
    """
    测试计划全量统计（不走分页）。

    与 /page 的区别：
    - /page 一次只返回一页数据；前端如果用 page 接口做"全量统计卡片"，
      实际只能拿到当前页的 items，结果严重失真。
    - 本接口直接对满足条件的全量计划做聚合（COUNT / GROUP BY / AVG），
      一次返回 { total, statusCounts, phaseCounts, avgCompletion }。

    :param data: 筛选条件（与 PagePlanSchema 对齐，但无分页 / 排序）
    :param _: 认证用户
    :return: 统计结果
    """
    result = await PlanMapper.list_statistics(data.project_id)
    return Response.success(data=result)


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


@router.post("/requirements/page", description="分页查询计划已关联的需求")
async def page_plan_requirements(data: PagePlanRequirementsSchema, _: User = Depends(Authentication())):
    """
    分页查询指定计划已关联的需求

    与 /queryRequirements 的区别：
    - 支持 current / pageSize 标准分页参数
    - 响应结构使用 { items, pageInfo }，与项目里其它列表接口对齐
    - 支持排序参数 sort（JSON 字典格式，例如 ``{"create_time": "descend"}``）
    - 支持按 uid 精确匹配（用于搜索框直达）

    :param data: 分页及筛选参数
    :param _: 认证用户
    :return: 分页结果
    """
    log.info(data)
    page_data = await PlanMapper.page_associated_requirements(
        plan_id=data.plan_id,
        current=data.current or 1,
        pageSize=data.pageSize or 10,
        requirement_name=data.requirement_name,
        requirement_level=data.requirement_level,
        process=data.process,
        uid=data.uid,
        sort=data.sort,
    )
    return Response.success(data=page_data)


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
    :param data: 复制参数
    :param user: 认证用户
    :return: 复制数量
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
    :param data: 复制参数
    :param user: 认证用户
    :return: 复制数量
    """
    log.info(data)
    values =  await PlanCaseMapper.copy_cases(
        **data.model_dump(),
        user=user
    )
    return Response.success(values)


@router.post("/cases/reorder", description="重排序计划用例（单 case 移动）")
async def reorder_plan_cases(
    data: ReorderPlanCaseSchema,
    user: User = Depends(Authentication()),
):
    """重排序计划下的单个用例。

    相比历史版本（传全量 ``case_ids`` 列表），本接口只传
    "被移动 case + 锚点"两个 ID，传输量与列表规模无关。

    典型用法
    --------
    - 拖拽 A 到 B 上方：``{case_id: A, before_id: B}``
    - 拖拽 A 到 B 下方：``{case_id: A, after_id: B}``
    - 移到 module 末尾：``{case_id: A}``（before/after 都为空）
    - 跨 module 移动：``{case_id: A, target_module_id: M, before_id: X}``

    :param data: 重排序参数
    :param user: 认证用户
    :return: 实际更新行数（0 表示幂等无变化）
    """
    log.info(
        "reorder_plan_cases plan=%s case=%s before=%s after=%s module=%s",
        data.plan_id, data.case_id, data.before_id, data.after_id, data.target_module_id,
    )
    try:
        affected = await PlanCaseMapper.reorder_plan_case(
            plan_id=data.plan_id,
            case_id=data.case_id,
            before_id=data.before_id,
            after_id=data.after_id,
            target_module_id=data.target_module_id,
        )
    except CommonError as err:
        log.warning(f"reorder_plan_cases rejected: {err}")
        return Response.error(msg=str(err))
    except Exception as err:
        log.exception(f"reorder_plan_cases 异常: {err}")
        return Response.error(msg=f"重排序失败: {err}")
    return Response.success(affected)


@router.post("/cases/reorder/bulk", description="批量重排序计划用例")
async def reorder_plan_cases_bulk(
    data: BulkReorderPlanCaseSchema,
    _: User = Depends(Authentication()),
):
    """批量重排序计划用例（多选拖拽 / 跨 module 批量调整）。

    所有 items 在同一事务内顺序应用，任一失败整体回滚。
    返回值为每条 item 的 affected 行数列表。

    :param data: 批量重排序参数（含 plan_id 与 items）
    :param _: 认证用户
    :return: 各 item 的 affected 行数列表
    """
    log.info(
        f"reorder_plan_cases_bulk plan={data.plan_id} item_count={len(data.items)}",
    )
    try:
        # 把 Pydantic model 转成 dict 列表，传给 mapper
        results = await PlanCaseMapper.reorder_plan_cases_bulk(
            plan_id=data.plan_id,
            items=[it.model_dump() for it in data.items],
        )
    except CommonError as err:
        log.warning(f"reorder_plan_cases_bulk rejected: {err}")
        return Response.error(msg=str(err))
    except Exception as err:
        log.exception(f"reorder_plan_cases_bulk 异常: %s", err)
        return Response.error(msg=f"批量重排序失败: {err}")
    return Response.success(results)


@router.post("/cases/update", description="更新计划用例")
async def update_plan_cases(data: UpdateCaseToCasePlan, user: User = Depends(Authentication())):
    """
    更新计划关联的用例信息

    支持批量更新：审核状态、一轮/二轮测试状态。
    入参 ``case_id_list`` 超过 2000 或混入其他计划的用例会被拒绝。

    :param data: 更新参数
    :param user: 认证用户
    :return: 实际更新的关联记录数；所有状态字段均为空时返回 0
    """
    try:
        values = await PlanCaseMapper.update_case(
            **data.model_dump(),
            user=user,
        )
    except CommonError as err:
        # 业务校验失败（如越权 / 长度超限），4xx 透传给前端
        log.warning(f"update_plan_cases rejected: {err}")
        return Response.error(msg=str(err))
    except Exception as err:
        log.exception(f"update_plan_cases 异常: {err}")
        return Response.error(msg=f"更新失败: {err}")
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


@router.post("/cases/delete_permanent", description="彻底删除计划用例（物理删除）")
async def delete_plan_cases_permanent(
    data: RemovePlanCaseSchema,
    _: User = Depends(Authentication()),
):
    """
    彻底删除计划下的用例：
    1) 解除用例与当前计划的关联
    2) 物理删除用例本体及子步骤

    警告：该操作不可恢复。如用例还被其他计划引用，FK 约束触发后事务回滚。
    """
    from sqlalchemy.exc import IntegrityError
    log.info(data)
    try:
        values = await PlanCaseMapper.delete_plan_cases_permanent(
            case_ids=data.case_ids,
            plan_id=data.plan_id,
        )
    except IntegrityError:
        log.exception(
            f"delete_permanent: case 还被其他计划引用,plan_id={data.plan_id}, "
            f"case_ids={data.case_ids}"
        )
        return Response.error(msg="用例还被其他计划引用,无法彻底删除")
    return Response.success(values)

@router.post("/upload/commit", description="确认并入库用例")
async def upload_commit(
        data: UploadCommitSchema,
        user: User = Depends(Authentication())
):
    if await _cache_service.is_committed(data.file_md5, user.id):
        return Response.error(msg="该文件已提交过，不能重复提交")

    preview_data = await _cache_service.get_preview(data.file_md5, user.id)
    if not preview_data:
        return Response.error(msg="预览数据已过期，请重新上传文件")

    valid_cases = preview_data.get("valid_cases", [])

    if not valid_cases:
        return Response.error(msg="请选择要入库的用例")

    try:
        imported_count, skipped_count = await PlanCaseMapper.insert_upload_case(
            cases=valid_cases,
            plan_id=data.plan_id,
            plan_module_id=data.plan_module_id,
            user=user,
            is_review=data.is_review,
            first_status=data.first_status,
            second_status=data.second_status,
            skip_duplicate=data.skip_duplicate,
        )
        await _cache_service.mark_committed(data.file_md5, user.id)
        return Response.success({
            "imported_count": imported_count,
            "skipped_count": skipped_count,
        })
    except Exception as e:
        log.exception(f"入库失败: {e}")
        return Response.error(msg=f"入库失败: {str(e)}")


@router.post("/import/commit", description="M2 协议 commit: 按 case_id 同步更新 / 新增 library 用例 + 写 plan 关联")
async def m2_import_commit(
        data: M2PlanImportCommitSchema,
        user: User = Depends(Authentication())
):
    """M2 协议下, 测试计划的导入 (导回) 入口.

    业务流程:
    1) 加载 Redis 预览缓存, 校验 template_type == M2
    2) 拆 known / new:
       - known (有 case_id): 复用 M2ImportService._apply_known_case 改 library 用例字段 + 步骤
         + 写 case_dynamic. PlanCaseAssociation 不动, 跟 M2 library 行为一致.
       - new (无 case_id): 校验 group_path 在 library 存在 -> find-or-create plan_module
         (写 source_module_id, 跟 M1 走同一套 _resolve_source_to_plan_module_map) -> 写
         library TestCase + Step + PlanCaseAssociation + case_dynamic.
    3) 标记 Redis committed

    跟 /upload/commit (M1) 区别:
    - M1 走 M1 老 import 路径 (insert_upload_case), 无 case_id 概念, 走 plan 内同名去重
    - M2 走 case_id 同步, 已知改, 未知增, 跨 plan 不冲突

    :param data: {file_md5, plan_id}
    :param user: 认证用户
    :return: {inserted, updated, dynamic_count}
    """
    _m2_service = M2PlanImportService()
    try:
        result = await _m2_service.commit(
            file_md5=data.file_md5,
            plan_id=data.plan_id,
            user=user,
        )
        return Response.success(result)
    except CommonError as e:
        log.warning(f"plan M2 commit 业务校验失败: {e}")
        return Response.error(msg=str(e))
    except Exception as e:
        log.exception(f"plan M2 commit 失败: {e}")
        return Response.error(msg=f"M2 导入失败: {str(e)}")




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







# =============== 统计相关==============

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