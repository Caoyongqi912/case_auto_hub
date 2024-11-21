#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : user# @Software: PyCharm# @Desc:from fastapi import APIRouter, Dependsfrom pygments.lexer import defaultfrom app.mapper.user import UserMapperfrom app.response import Responsefrom app.schema import PageSchemafrom app.schema.base import RegisterUser, RegisterAdmin, LoginUserfrom app.controller import Authenticationfrom utils import MyLoguruLOG = MyLoguru().get_logger()router = APIRouter(prefix="/user", tags=["用户"])@router.post(path="/pageUser", description="分页查询用户")async def page_user(page: PageSchema, user=Depends(Authentication())) -> Response:    """    分页查询用户    :param page:分页信息    :param user:鉴权    :return:    """    LOG.debug(user)    data = await UserMapper.page_query(**page.dict())    return Response.success(data, exclude=("password",))@router.get(path="/query", description="查询所有用户")async def query_user() -> Response:    """    查询所有用户    :return:    """    users = await UserMapper.query_all()    return Response.success(users, exclude=("password",))@router.get(path="/currentUserInfo",            description="获取当前用户信息")async def current_user_info(user_id: int) -> Response:    """    通过userID 获取用户信息    :param user_id:    :return:    """    userInfo = await UserMapper.get_by_id(user_id)    return Response.success(userInfo, exclude=("password",))@router.post(path="/registerUser",             description="注册用户")async def register_user(user: RegisterUser) -> Response:    await UserMapper.register(**user.dict(        exclude_none=True,        exclude_unset=True    ))    return Response.success()@router.post(path="/registerAdmin", description="添加管理")async def register_admin(user: RegisterAdmin) -> Response:    await UserMapper.register_admin(**user.dict())    return Response.success()@router.post(path="/login", description="登陆")async def login(loginInfo: LoginUser) -> Response:    token = await UserMapper.login(**loginInfo.dict())    return Response.success(token)