#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : test_case
# @Software: PyCharm
# @Desc: 测试用例管理路由
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, Form, File
from fastapi.responses import FileResponse

from app.mapper.test_case import TestCaseMapper, TestCaseStepMapper, CaseDynamicMapper
from app.schema.hub.testCaseSchema import (
    AddTestCaseSchema, PageTestCaseSchema, AddDefaultCaseSchema,
    UpdateTestCaseSchema, QueryTestCaseSchemaByField, RemoveCaseSchema, RemoveCaseStep,
    CopyCase, CopyCaseStep, AddDefaultCaseStep, UpdateTestCaseStep, ReorderCaseStep,
    UpdateTestCaseStatusSchema, SetCasesCommonSchema, UploadPreviewResult,
    UploadCommitSchema, UploadCancelSchema,UpdateTestCasesSchema,DeleteTestCasesSchema
)
from app.service.uploadCacheService import UploadCacheService
from common import rc
from app.controller import Authentication
from app.model.base import User
from app.response import Response
from utils import  log

router = APIRouter(prefix="/hub/cases", tags=['用例'])

_cache_service = UploadCacheService(rc)


@router.get("/info", description="用例信息")
async def case_info(case_id: int, _: User = Depends(Authentication())):
    case = await TestCaseMapper.case_info(case_id=case_id)
    return Response.success(case)


@router.post("/insert", description="添加测试用例")
async def insert_case(data: AddTestCaseSchema, user: User = Depends(Authentication())):
    """
    添加新的测试用例
    :param data: 用例基本信息
    :param user: 认证用户
    :return: 创建的用例ID
    """
    result = await TestCaseMapper.save_case(user=user, **data.model_dump(exclude_unset=True))
    return Response.success(result)


@router.post("/page", description="分页查询用例列表")
async def page_cases(data: PageTestCaseSchema, _: User = Depends(Authentication())):
    """
    分页查询测试用例列表
    - module_id 不为空: 查询该模块(含子节点)下的用例
    - module_id 为空或不传: 查询 module_id 为空的用例(未分类)
    - module_ids 多选: 多个模块各自展开子节点后求并集过滤

    :param data: 分页及筛选参数
    :param _: 认证用户
    :return: 用例分页数据
    """
    payload = data.model_dump(exclude_none=True, exclude_unset=True)
    # module_id 为空 / 不传 -> 代表查询未分类用例(module_id IS NULL)
    if data.module_id is None and data.module_ids is None:
        payload.pop("module_id", None)
        payload["module_id__is_null"] = True
    log.debug(payload)
    result = await TestCaseMapper.page_by_module(**payload) 
        
    return Response.success(result)


@router.post("/addDefault", description="添加默认用例")
async def add_default_case(data: AddDefaultCaseSchema, user: User = Depends(Authentication())):
    """
    根据需求ID添加默认模板用例
    :param data: 需求ID
    :param user: 认证用户
    :return: 创建的用例ID
    """
    result = await TestCaseMapper.add_default_case(user=user, **data.model_dump(exclude_unset=True))
    return Response.success(result)


@router.post("/update", description="更新测试用例信息")
async def update_case(data: UpdateTestCaseSchema, user: User = Depends(Authentication())):
    """
    根据用例ID更新用例基本信息
    :param data: 用例更新数据
    :param user: 认证用户
    :return: 操作结果
    """
    log.info(data)
    await TestCaseMapper.update_case(ur=user, **data.model_dump(exclude_unset=True, exclude_none=True))
    return Response.success()

@router.post("/batchUpdate", description="批量更新测试用例信息")
async def update_cases_batch(data: UpdateTestCasesSchema, user: User = Depends(Authentication())):
    """
    根据用例ID更新用例基本信息
    :param data: 用例更新数据
    :param user: 认证用户
    :return: 操作结果
    """
    rows = await TestCaseMapper.update_batch_cases(user=user, **data.model_dump(exclude_unset=True, exclude_none=True))
    return Response.success(rows)

@router.post("/batchDelete", description="批量删除测试用例信息")
async def delete_cases_batch(data: DeleteTestCasesSchema, user: User = Depends(Authentication())):
    """
    根据用例ID删除用例基本信息
    :param data: 用例更新数据
    :param user: 认证用户
    :return: 操作结果
    """
    rows = await TestCaseMapper.delete_batch_cases(data.delete_case_list)
    return Response.success(rows)

@router.get("/queryByField", description="根据条件查询用例列表")
async def query_cases_by_field(data: QueryTestCaseSchemaByField = Depends(), _: User = Depends(Authentication())):
    """
    根据需求ID及筛选条件查询用例列表
    :param data: 查询条件（需求ID、用例名称、级别、类型、标签、状态）
    :param _: 认证用户
    :return: 用例列表
    """
    result = await TestCaseMapper.query_case_by_field(**data.model_dump(exclude_none=True, exclude_unset=True))
    return Response.success(result)


@router.get("/queryTagsByReqId", description="查询需求下的用例标签列表")
async def query_tags_by_requirement(requirement_id: int, _: User = Depends(Authentication())):
    """
    根据需求ID查询该需求下所有用例的标签列表
    :param requirement_id: 需求ID
    :param _: 认证用户
    :return: 标签列表
    """
    result = await TestCaseMapper.query_tags(requirement_id)
    log.info(result)
    return Response.success(result)


@router.post("/remove", description="删除测试用例")
async def remove_case(data: RemoveCaseSchema, _: User = Depends(Authentication())):
    """
    根据用例ID删除指定的测试用例
    :param data: 用例ID及需求ID
    :param _: 认证用户
    :return: 操作结果
    """
    await TestCaseMapper.remove_case(**data.model_dump())
    return Response.success()


@router.post("/removeStep", description="删除用例步骤")
async def remove_case_step(data: RemoveCaseStep, _: User = Depends(Authentication())):
    """
    根据步骤ID删除用例的某个步骤
    :param data: 步骤ID
    :param _: 认证用户
    :return: 操作结果
    """
    await TestCaseStepMapper.delete_by_id(data.stepId)
    return Response.success()


@router.post("/copy", description="复制用例")
async def copy_case(data: CopyCase, user: User = Depends(Authentication())):
    """
    复制指定用例创建一个新的用例副本
    :param data: 被复制的用例ID及目标需求ID
    :param user: 认证用户
    :return: 操作结果
    """
    await TestCaseMapper.copy_cases(case_ids=[data.caseId], user=user, requirement_id=data.requirementId)
    return Response.success()


@router.post("/copyStep", description="复制用例步骤")
async def copy_case_step(data: CopyCaseStep, user: User = Depends(Authentication())):
    """
    复制指定用例步骤创建一个新的步骤副本
    :param data: 被复制的步骤ID
    :param user: 认证用户
    :return: 操作结果
    """
    await TestCaseStepMapper.copy_step(user=user, **data.model_dump())
    return Response.success()


@router.post("/handleAddStepLine", description="添加用例默认步骤")
async def add_case_step(data: AddDefaultCaseStep, user: User = Depends(Authentication())):
    """
    为指定用例添加一条默认步骤
    :param data: 用例ID
    :param user: 认证用户
    :return: 操作结果
    """
    await TestCaseStepMapper.add_default_step(user=user, **data.model_dump())
    return Response.success()


@router.post("/reorderSupStep", description="用例步骤排序")
async def reorder_case_steps(data: ReorderCaseStep, _: User = Depends(Authentication())):
    """
    对指定用例的步骤进行排序调整
    :param data: 步骤ID列表（新顺序）
    :param _: 认证用户
    :return: 操作结果
    """
    await TestCaseStepMapper.reorder_steps(**data.model_dump())
    return Response.success()


@router.get("/querySubSteps/{caseId}", description="查询用例的所有步骤")
async def query_sub_steps(caseId: int, _: User = Depends(Authentication())):
    """
    :param caseId: 用例ID
    :param _: 认证用户
    :return: 步骤列表
    """
    steps = await TestCaseStepMapper.query_sub_steps(caseId)
    return Response.success(steps)


@router.post("/updateSubSteps", description="更新用例步骤")
async def update_sub_step(data: UpdateTestCaseStep, user: User = Depends(Authentication())):
    """
    更新指定步骤的内容、预期结果或排序
    :param data: 步骤ID及更新内容
    :param user: 认证用户
    :return: 操作结果
    """
    await TestCaseStepMapper.update_step(
        user=user,
        **data.model_dump(exclude_unset=True, exclude_none=True),
    )
    return Response.success()


@router.get("/queryDynamic/{caseId}", description="查询用例动态信息")
async def query_case_dynamic(caseId: int, plan_id: Optional[int] = None, _: User = Depends(Authentication())):
    """
    查询指定用例的动态信息（如创建人、创建时间、修改记录等）

    :param caseId: 用例ID
    :param plan_id: 计划ID（可选，为None时只查用例自身变更，非None时同时查该计划的变更）    
    :param _: 认证用户
    :return: 用例动态信息
    """
    result = await CaseDynamicMapper.query_dynamic(caseId, plan_id)
    return Response.success(result)


@router.post("/setTestCaseResult", description="更新用例测试结果")
async def set_test_case_result(data: UpdateTestCaseStatusSchema, user: User = Depends(Authentication())):
    """
    更新指定用例的测试执行状态
    :param data: 用例ID及状态
    :param user: 认证用户
    :return: 操作结果
    """
    await TestCaseMapper.update_case(user=user, **data.model_dump(exclude_unset=True, exclude_none=True))
    return Response.success()





@router.get("/downloadCaseDemo", description="下载用例导入模板")
async def download_case_template(_: User = Depends(Authentication())):
    """
    下载用例导入的Excel模板文件
    :param _: 认证用户
    :return: 模板文件
    """
    from file import TestCaseDemoFile
    return FileResponse(
        path=TestCaseDemoFile,
        filename="用例模板.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/updateCommon", description="批量设置公共用例")
async def batch_set_common(data: SetCasesCommonSchema, _: User = Depends(Authentication())):
    """
    批量将多个用例设置为公共用例
    :param data: 用例ID列表及目标模块、项目ID
    :param _: 认证用户
    :return: 操作结果
    """
    await TestCaseMapper.update_cases_common(**data.model_dump())
    return Response.success()



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
        await TestCaseMapper.insert_upload_case(
            cases=valid_cases,
            project_id=data.project_id,
            module_id=data.module_id,
            requirement_id=data.requirement_id,
            user=user,
            is_common=data.is_common
        )
        await _cache_service.mark_committed(data.file_md5, user.id)
        return Response.success({"imported_count": len(valid_cases)})
    except Exception as e:
        log.exception(f"入库失败: {e}")
        return Response.error(msg=f"入库失败: {str(e)}")


@router.post("/upload/cancel", description="取消上传")
async def upload_cancel(
        data: UploadCancelSchema,
        user: User = Depends(Authentication())
):
    await _cache_service.delete(data.file_md5, user.id)
    return Response.success()


@router.post("/upload", description="批量导入用例")
async def upload_cases(
        file: UploadFile = File(..., description="Excel文件"),
        user: User = Depends(Authentication())
):
    from utils.aioFileReader import AsyncFilesReader
    from utils.caseEnumResolver import load_case_enum_config
    enum_config = await load_case_enum_config()
    try:
        result = await AsyncFilesReader(enum_config=enum_config).async_read_excel_for_case(file)
    except Exception as e:
        log.exception(f"文件解析失败: {e}")
        return Response.error(msg=f"文件解析失败: {str(e)}")

    await _cache_service.save_preview(
        file_md5=result.file_md5,
        user_id=user.id,
        valid_cases=result.valid_cases,
        errors=result.errors,
        total_count=result.total_count,
    )


    return Response.success(UploadPreviewResult(
        file_md5=result.file_md5,
        total_count=result.total_count,
        valid_count=result.valid_count,
        invalid_count=result.invalid_count,
        errors=result.errors,
    ).model_dump())
