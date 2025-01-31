#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/1/22# @Author : cyq# @File : ui_step# @Software: PyCharm# @Desc:from fastapi import APIRouter, Dependsfrom app.controller import Authenticationfrom app.mapper.ui.uiCaseMapper import *from app.mapper.ui.uiSubStepMapper import SubStepMapperfrom app.model.base import Userfrom app.response import Responsefrom app.schema.ui import *router = APIRouter(prefix="/ui/case/step", tags=['自动化用例步骤'])@router.post("/add", description="添加步骤")async def add_common_step(stepInfo: AddUICaseStep, cr: User = Depends(Authentication())):    # 新增用例并关联case    if stepInfo.case_id and stepInfo.is_common_step is False:        await UICaseMapper.add_step(**stepInfo.dict())    else:        # 新增common step        await UICaseStepMapper.save(            creatorUser=cr,            **stepInfo.dict(                exclude_none=True,                exclude_unset=True            ))    return Response.success()@router.get("/detail", description="用例步骤详情")async def step_detail(stepId: int, _: User = Depends(Authentication())):    """    query_steps    :return:    """    data = await UICaseStepMapper.get_by_id(ident=stepId)    return Response.success(data)@router.post("/update", description="修改步骤")async def put_step(stepInfo: PutUICaseStep, ur: User = Depends(Authentication())):    await UICaseStepMapper.update_by_id(        updateUser=ur,        **stepInfo.dict(            exclude_none=True,            exclude_unset=True        ))    return Response.success()@router.post("/remove", description="删除步骤")async def del_step(stepInfo: RemoveUIStepSchema, _: User = Depends(Authentication())):    await UICaseStepMapper.remove_step(**stepInfo.dict())    return Response.success()@router.post("/order", description="排序步骤")async def order_step(stepInfo: ReOrderUIStepSchema, _: User = Depends(Authentication())):    await UICaseStepMapper.reorder_step(**stepInfo.dict())    return Response.success()@router.post("/copy", description="复制步骤")async def copy_step(stepInfo: CopyUIStepSchema, _: User = Depends(Authentication())):    await UICaseStepMapper.copy_step(**stepInfo.dict())    return Response.success()@router.post("/api/add", description="添加api步骤")async def add_step_api(apiInfo: AddUICaseStepApiSchema, cr: User = Depends(Authentication())):    await UICaseStepApiMapper.insert(        creator=cr,        **apiInfo.dict(exclude_none=True))    return Response.success()@router.post("/api/update", description="修改api步骤")async def update_step_api(apiInfo: UpdateUICaseStepApiSchema, ur: User = Depends(Authentication())):    await UICaseStepApiMapper.update_by_uid(        updateUser=ur,        **apiInfo.dict(exclude_none=True, exclude_unset=True)    )    return Response.success()@router.post("/api/remove", description="修改步骤API")async def delete_step_api(apiInfo: DeleteUICaseStepApiSchema, dr: User = Depends(Authentication())):    """    删除步骤API    """    await UICaseStepApiMapper.deleted(user=dr, **apiInfo.dict(exclude_none=True))    return Response.success()@router.get("/api/detail", description="步骤API")async def get_api_detail(stepId: int, _: User = Depends(Authentication())):    """    删除步骤API    """    data = await UICaseStepApiMapper.get_by(stepId=stepId)    return Response.success(data)@router.post("/sql/add", description="添加sql步骤")async def add_step_sql(sqlInfo: AddUICaseStepSqlSchema, cr: User = Depends(Authentication())):    await UICaseStepSQLMapper.insert(creator=cr, **sqlInfo.dict(exclude_none=True, exclude_unset=True))    return Response.success()@router.post("/sql/update", description="更新sql步骤")async def update_step_sql(sqlInfo: UpdateUICaseStepSqlSchema, ur: User = Depends(Authentication())):    await UICaseStepSQLMapper.update_by_uid(updateUser=ur, **sqlInfo.dict(exclude_none=True, exclude_unset=True))    return Response.success()@router.post("/sql/remove", description="更新sql步骤")async def remove_step_sql(sqlInfo: RemoveUICaseStepSqlSchema, user: User = Depends(Authentication())):    await UICaseStepSQLMapper.deleted(uid=sqlInfo.uid, user=user)    return Response.success()@router.get("/sql/detail", description="更新sql步骤")async def remove_step_sql(stepId: int, _: User = Depends(Authentication())):    data = await UICaseStepSQLMapper.get_by(stepId=stepId)    return Response.success(data)@router.post("/condition/add", description="添加条件")async def step_add_condition(con: AddSubStepConditionSchema, ur: User = Depends(Authentication())):    await UICaseStepMapper.add_condition(**con.dict())    return Response.success()@router.post("/sub/add", description="添加条件步骤")async def add_sub_step(stepInfo: AddStepSchema, cr: User = Depends(Authentication())):    await SubStepMapper.add_sub(        cr=cr,        **stepInfo.dict())    return Response.success()@router.post("/sub/update", description="修改条件步骤")async def update_sub_step(stepInfo: UpdateStepSchema, ur: User = Depends(Authentication())):    await SubStepMapper.update_by_id(        updateUser=ur,        **stepInfo.dict())    return Response.success()@router.post("/sub/remove", description="删除条件步骤")async def remove_sub_step(stepInfo: RemoveStepSchema, _: User = Depends(Authentication())):    await SubStepMapper.delete_by_id(stepInfo.id)    return Response.success()@router.get("/sub/list", description="条件表")async def get_sub_step_list(stepId: int, _: User = Depends(Authentication())):    data = await SubStepMapper.query_by_stepId(stepId=stepId)    return Response.success(data)@router.post("/sub/reorder", description="条件表")async def reorder_sub_step_list(orderInfo: ReorderSubStepSchema, _: User = Depends(Authentication())):    await SubStepMapper.reorder_sub_step(**orderInfo.dict())    return Response.success()@router.post("/sub/detail", description="详情条件步骤")async def detail_sub_step(stepInfo: DetailStepSchema, _: User = Depends(Authentication())):    data = await SubStepMapper.get_by_id(stepInfo.id)    return Response.success(data)