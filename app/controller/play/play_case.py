#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/3
# @Author : cyq
# @File : play_case
# @Software: PyCharm
# @Desc:
from asyncio import create_task

from fastapi import APIRouter, Depends

from app.controller import Authentication
from app.mapper.play import PlayCaseVariablesMapper
from app.model.base import User
from app.response import Response
from app.schema.play import (
    PlayCaseBasicSchema,
    EditPlayCaseBasicSchema,
    GetPlayCaseByCaseId,
    PagePlayCaseSchema,
    ReOrderPlayStepSchema,
    PagePlayCaseResultSchema, InsertPlayCaseVariableSchema, GetPlayCaseVariableSchema, PagePlayCaseVariableSchema,
    EditPlayCaseVariableSchema
)
from app.mapper.play.playCaseMapper import PlayCaseMapper, PlayCaseResultMapper, PlayStepContentMapper
from app.schema.play.playCaseSchema import ExecutePlayCase, AssociationPlayStepSchema, EditPlayStepContentSchema, \
    AssociationPlayGroupSchema
from app.schema.play.playStepSchema import InsertCasePlayStepSchema, RemovePlayStepContentSchema, \
    CopyPlayCaseStepContentSchema
from croe.play.starter import UIStarter
from utils import log

router = APIRouter(prefix="/play/case", tags=['自动化Case'])


@router.get("/detail", description="用例基本信息")
async def get_case_detail(case: GetPlayCaseByCaseId = Depends(), _: User = Depends(Authentication())):
    """
    获取用例详细信息

    Args:
        case: 用例ID查询参数
        _: 当前登录用户（未使用）

    Returns:
        用例详细信息
    """
    case = await PlayCaseMapper.get_by_id(case.caseId)
    return Response.success(case)


@router.post("/insert/basic", description="添加用例基本信息")
async def insert_case_basic(case: PlayCaseBasicSchema, creator_user: User = Depends(Authentication())):
    """
    插入新的用例基本信息

    Args:
        case: 用例基本信息
        creator_user: 当前登录用户

    Returns:
        插入成功的用例信息
    """
    play_case = await PlayCaseMapper.save(creator_user=creator_user, **case.model_dump())
    return Response.success(play_case)


@router.post("/edit/basic", description="修改用例基本信息")
async def update_case(case: EditPlayCaseBasicSchema, ur: User = Depends(Authentication())):
    """
    更新用例基本信息

    Args:
        case: 用例更新信息
        ur: 当前登录用户

    Returns:
        更新后的用例信息
    """
    case = await PlayCaseMapper.update_by_id(
        updateUser=ur,
        **case.model_dump(exclude_none=True, exclude_unset=True))
    return Response.success(case)


@router.post("/delete", description="删除用例")
async def delete_case(case: GetPlayCaseByCaseId, _: User = Depends(Authentication())):
    """
    删除指定的用例

    Args:
        case: 包含用例ID的参数
        _: 当前登录用户（未使用）

    Returns:
        删除成功响应
    """
    await PlayCaseMapper.delete_by_id(ident=case.caseId)
    return Response.success()


@router.post("/associationPlayStep", description="关联公共步骤")
async def association_play_step(association: AssociationPlayStepSchema, user: User = Depends(Authentication())):
    """
    关联公共步骤到用例

    Args:
        association: 关联参数
        user: 当前登录用户

    Returns:
        关联成功响应
    """
    log.info(association)
    await PlayCaseMapper.association_steps(**association.model_dump(), user=user)
    return Response.success()



@router.post("/associationPlayGroup", description="关联公共步骤组")
async def association_play_group(association: AssociationPlayGroupSchema, user: User = Depends(Authentication())):
    """
    关联公共步骤到用例组

    Args:
        association: 关联参数
        user: 当前登录用户

    Returns:
        关联成功响应
    """
    await PlayCaseMapper.association_groups(**association.model_dump())
    return Response.success()


@router.post("/insertCasePlayStep", description="关联公共步骤")
async def insert_case_play_step(insert_info: InsertCasePlayStepSchema, user: User = Depends(Authentication())):
    """
    插入用例步骤关联

    Args:
        insert_info: 步骤插入信息
        user: 当前登录用户

    Returns:
        插入成功响应
    """
    await PlayCaseMapper.insert_step_association(**insert_info.model_dump(
        exclude_none=True,
        exclude_unset=True
    ), user=user)
    return Response.success()


@router.get("/queryContent", description="查询步骤")
async def query_play_content(case_id: int, _: User = Depends(Authentication())):
    """
    查询用例的步骤内容

    Args:
        case_id: 用例ID
        _: 当前登录用户（未使用）

    Returns:
        步骤内容列表
    """
    contents = await PlayCaseMapper.query_content_steps(case_id=case_id)
    return Response.success(contents)


@router.post("/reorder_content_step", description="排序步骤")
async def reorder_content_step(stepInfo: ReOrderPlayStepSchema, _: User = Depends(Authentication())):
    """
    重新排序用例步骤

    Args:
        stepInfo: 步骤重排序参数
        _: 当前登录用户（未使用）

    Returns:
        重排序成功响应
    """
    await PlayCaseMapper.reorder_content_step(**stepInfo.model_dump())
    return Response.success()


@router.post("/copy_content", description="复制")
async def copy_content(content: CopyPlayCaseStepContentSchema, user: User = Depends(Authentication())):
    """
    复制步骤内容

    Args:
        content: 步骤复制参数
        user: 当前登录用户

    Returns:
        复制成功响应
    """
    await PlayCaseMapper.copy_content(**content.model_dump(), user=user)
    return Response.success()


@router.post("/remove_content", description="删除步骤")
async def remove_step(stepInfo: RemovePlayStepContentSchema, _: User = Depends(Authentication())):
    """
    移除步骤内容

    Args:
        stepInfo: 步骤移除参数
        _: 当前登录用户（未使用）

    Returns:
        移除成功响应
    """
    await PlayCaseMapper.remove_step(**stepInfo.model_dump())
    return Response.success()


@router.post("/edit_content", description="修改步骤")
async def update_content(content: EditPlayStepContentSchema, user: User = Depends(Authentication())):
    """
    更新步骤内容

    Args:
        content: 步骤更新信息
        user: 当前登录用户

    Returns:
        更新成功响应
    """
    await PlayStepContentMapper.update_by_id(**content.model_dump(
        exclude_none=True,
        exclude_unset=True
    ), updateUser=user)
    return Response.success()


@router.get("/query_all", description="查询所有用例")
async def query_all_cases(_: User = Depends(Authentication())):
    """
    查询所有用例

    Args:
        _: 当前登录用户（未使用）

    Returns:
        所有用例列表
    """
    cases = await PlayCaseMapper.query_all()
    return Response.success(cases)


@router.post("/page", description="分页查询")
async def page_cases(pageInfo: PagePlayCaseSchema, _: User = Depends(Authentication())):
    """
    分页查询用例

    Args:
        pageInfo: 分页查询参数
        _: 当前登录用户（未使用）

    Returns:
        分页查询结果
    """
    data = await PlayCaseMapper.page_by_module(**pageInfo.model_dump(exclude_none=True,
                                                                     exclude_unset=True))
    return Response.success(data)


@router.post("/copy", description="复制用例")
async def copy_case(case: GetPlayCaseByCaseId, cr: User = Depends(Authentication())):
    """
    复制用例

    Args:
        case: 包含用例ID的参数
        cr: 当前登录用户

    Returns:
        复制后的用例信息
    """
    case = await PlayCaseMapper.copy_case(
        caseId=case.caseId, cr=cr)

    return Response.success(case)


# =====================================  RESUlT ===========================================================

@router.post("/page_result", description="用例结果分页查询")
async def page_case_result(pageInfo: PagePlayCaseResultSchema, _: User = Depends(Authentication())):
    """
    分页查询用例执行结果

    Args:
        pageInfo: 分页查询参数
        _: 当前登录用户（未使用）

    Returns:
        分页查询结果
    """
    data = await PlayCaseResultMapper.page_query(**pageInfo.model_dump(exclude_none=True,
                                                                       exclude_unset=True))
    return Response.success(data,exclude={
        "asserts_info","running_logs",
    })

@router.get("/queryContentResults",description="查询步骤详情")
async def query_content_results(case_result_id:int, _: User = Depends(Authentication())):
    data = await PlayCaseResultMapper.query_contents(case_result_id)
    return Response.success(data)

@router.get("/result_detail", description="用例结果详情")
async def get_case_result(case_result_id: int, _: User = Depends(Authentication())):
    """
    获取用例执行结果详情

    Args:
        uid: 结果唯一标识
        _: 当前登录用户（未使用）

    Returns:
        用例执行结果详情
    """
    result = await PlayCaseResultMapper.get_by_id(case_result_id)
    return Response.success(result)


@router.get("/result_clear", description="清空调试历史")
async def clear_result(caseId: int, _: User = Depends(Authentication())):
    """
    清空用例的调试历史记录

    Args:
        caseId: 用例ID
        _: 当前登录用户（未使用）

    Returns:
        清空成功响应
    """
    await PlayCaseResultMapper.clear_case_result(caseId=caseId)
    return Response.success()


# =====================================  VARs ====================================================


@router.post("/add_variable", description="添加前置变量")
async def add_variable(var: InsertPlayCaseVariableSchema, user: User = Depends(Authentication())):
    """
    添加前置变量

    Args:
        var: 变量信息
        user: 当前登录用户

    Returns:
        添加成功响应
    """
    await PlayCaseVariablesMapper.insert(**var.model_dump(), user=user)
    return Response.success()


@router.post("/remove_variable", description="添加前置变量")
async def remove_variable(var: GetPlayCaseVariableSchema, _: User = Depends(Authentication())):
    """
    移除前置变量

    Args:
        var: 包含变量UID的参数
        _: 当前登录用户（未使用）

    Returns:
        移除成功响应
    """
    await PlayCaseVariablesMapper.delete_by_uid(var.uid)
    return Response.success()


@router.post("/edit_variable", description="添加前置变量")
async def update_variable(var: EditPlayCaseVariableSchema, _: User = Depends(Authentication())):
    """
    更新前置变量

    Args:
        var: 变量更新信息
        _: 当前登录用户（未使用）

    Returns:
        更新成功响应
    """
    await PlayCaseVariablesMapper.update_by_id(**var.model_dump(exclude_none=True),
                                               updateUser=_)
    return Response.success()


@router.post("/page_variable", description="前置变量分页")
async def page_variable(pageInfo: PagePlayCaseVariableSchema, _: User = Depends(Authentication())):
    """
    分页查询前置变量

    Args:
        pageInfo: 分页查询参数
        _: 当前登录用户（未使用）

    Returns:
        分页查询结果
    """
    data = await PlayCaseVariablesMapper.page_query(**pageInfo.model_dump(
        exclude_none=True
    ))
    return Response.success(data)


@router.get("/query_variable", description="前置变量")
async def query_variable(caseId: int, _: User = Depends(Authentication())):
    """
    查询前置变量

    Args:
        caseId: 用例ID
        _: 当前登录用户（未使用）

    Returns:
        前置变量列表
    """
    data = await PlayCaseVariablesMapper.query_by(play_case_id=caseId)
    return Response.success(data)


@router.post("/execute_back", description='后台执行')
async def execute_back(info: ExecutePlayCase, sr: User = Depends(Authentication())):
    """
    后台执行用例

    Args:
        info: 执行参数
        sr: 当前登录用户

    Returns:
        执行成功响应
    """
    starter = UIStarter(sr)
    from croe.play.play_runner import PlayRunner
    create_task(PlayRunner(starter).run_case(**info.model_dump()))
    return Response.success()


@router.post("/execute_io", description='后台执行')
async def execute_io(info: ExecutePlayCase, sr: User = Depends(Authentication())):
    """
    IO方式执行用例

    Args:
        info: 执行参数
        sr: 当前登录用户

    Returns:
        执行成功响应
    """
    starter = UIStarter(sr)
    # create_task(Player(starter).run_case(**info.model_dump()))
    return Response.success()
