#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceApi# @Software: PyCharm# @Desc:import asynciofrom fastapi import APIRouter, Dependsfrom app.controller import Authenticationfrom app.response import Responsefrom app.schema.interface import *from app.mapper.interface import InterfaceMapperfrom utils import MyLogurufrom interface.runner import InterFaceRunnerLOG = MyLoguru().get_logger()router = APIRouter(prefix="/interface", tags=['自动化接口步骤'])@router.post("/insert", description="添加步骤")async def insert_interface_Api(ApiInfo: AddInterfaceApiSchema, auth=Depends(Authentication())):    await InterfaceMapper.save(        creatorUser=auth,        **ApiInfo.dict())    return Response.success()@router.get("/detail", description="接口信息")async def detail_interface(interfaceId: int, _=Depends(Authentication())):    inter = await InterfaceMapper.get_by_id(interfaceId)    return Response.success(inter)@router.get("/queryBy", description="批量查询")async def query_by_interface(inter: InterfaceApiFieldSchema, auth=Depends(Authentication())):    inters = await InterfaceMapper.get_by(**inter.dict(        exclude_unset=True,        exclude_none=True,    ))    return Response.success(inters)@router.post("/page", description="分页查询")async def page_interface(inter: PageInterfaceApiSchema, _=Depends(Authentication())):    inters = await InterfaceMapper.page_query(        **inter.dict(            exclude_unset=True,            exclude_none=True,        )    )    return Response.success(inters)@router.post("/update", description="修改接口")async def update_interface(inter: InterfaceApiFieldSchema, auth=Depends(Authentication())):    await InterfaceMapper.update_by_id(**inter.dict(        exclude_unset=True,        exclude_none=True,    ), updateUser=auth)    return Response.success()@router.post("/remove", description="删除")async def remove_interface(inter: RemoveInterfaceApiSchema, _=Depends(Authentication())):    await InterfaceMapper.delete_by_id(**inter.dict())    return Response.success()@router.post("/try", description="调试")async def try_interface_Api(interId: TryAddInterfaceApiSchema, user=Depends(Authentication())):    resp = await InterFaceRunner(user).try_interface(interfaceId=interId.interfaceId)    return Response.success(resp)@router.post("/asyncTry", description="调试")async def try_interface_Api(interId: TryAddInterfaceApiSchema, user=Depends(Authentication())):    try:        asyncio.create_task(InterFaceRunner(user).try_interface(interfaceId=interId.interfaceId))    except Exception as e:        raise e    return Response.success()