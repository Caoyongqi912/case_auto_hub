#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/1/23# @Author : cyq# @File : ui_vars# @Software: PyCharm# @Desc:from fastapi import APIRouter, Dependsfrom app.controller import Authenticationfrom app.mapper.ui.uiCaseVariableMapper import UICaseVariableMapperfrom app.model.base import Userfrom app.response import Responsefrom app.schema.base.vars import *from utils import logrouter = APIRouter(prefix="/ui/case/vars", tags=['自动化用例变量'])@router.post('/add', description='添加变量')async def add_vars(varInfo: AddVarsSchema, cr: User = Depends(Authentication())):    await UICaseVariableMapper.insert(user=cr, **varInfo.model_dump(exclude_none=True, exclude_unset=True))    return Response.success()@router.post('/update', description='修改变量')async def add_vars(varInfo: UpdateVarsSchema, cr: User = Depends(Authentication())):    await UICaseVariableMapper.update_by_uid(updateUser=cr, **varInfo.model_dump(exclude_none=True,                                                                           exclude_unset=True))    return Response.success()@router.post('/remove', description='删除变量')async def add_vars(varInfo: DeleteVarsSchema, _: User = Depends(Authentication())):    await UICaseVariableMapper.delete_by_uid(**varInfo.model_dump())    return Response.success()@router.post('/page', description='查询')async def query_vars(varsInfo: PageVarsSchema, _: User = Depends(Authentication())):    datas = await UICaseVariableMapper.page_query(**varsInfo.model_dump(        exclude_none=True,    ))    return Response.success(datas)