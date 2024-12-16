#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : user# @Software: PyCharm# @Desc:from fastapi import APIRouter, Depends, UploadFile, Filefrom app.mapper.user import UserMapperfrom app.model.base import Userfrom app.response import Responsefrom app.schema import PageSchemafrom app.schema.base import RegisterUser, RegisterAdmin, LoginUserfrom app.controller import Authenticationfrom enums import FileEnumfrom utils import MyLogurufrom utils.fileManager import FileManagerfrom fastapi.responses import FileResponseLOG = MyLoguru().get_logger()router = APIRouter(prefix="/user", tags=["用户"])@router.post(path="/pageUser", description="分页查询用户")async def page_user(page: PageSchema, user=Depends(Authentication())) -> Response:    """    分页查询用户    :param page:分页信息    :param user:鉴权    :return:    """    LOG.debug(user)    data = await UserMapper.page_query(**page.dict())    return Response.success(data, exclude=("password",))@router.get(path="/query", description="查询所有用户")async def query_user(_=Depends(Authentication(isAdmin=True))) -> Response:    """    查询所有用户    """    users = await UserMapper.query_all()    return Response.success(users, exclude=("password",))@router.get(path='/query_by_username', description="查询用户")async def query_by_username(username: str | None, _=Depends(Authentication(isAdmin=True))):    """    通过用户名 模糊搜索    :param username:    :param _:    :return:    """    if username is None:        return Response.success([])    users = await UserMapper.filter_user_by_username(username)    return Response.success(users, exclude=("password",))@router.get(path="/currentUser", description="获取当前用户信息")async def current_user_info(user=Depends(Authentication())) -> Response:    """通过userID 获取用户信息"""    return Response.success(user, exclude=("password",))@router.post(path="/registerUser",             description="注册用户")async def register_user(user: RegisterUser, _=Depends(Authentication(isAdmin=True))) -> Response:    await UserMapper.register(**user.dict(        exclude_none=True,        exclude_unset=True    ))    return Response.success()@router.post(path="/registerAdmin", description="添加管理")async def register_admin(user: RegisterAdmin) -> Response:    await UserMapper.register_admin(**user.dict())    return Response.success()@router.post(path="/login", description="登陆")async def login(loginInfo: LoginUser) -> Response:    token = await UserMapper.login(**loginInfo.dict())    return Response.success(token)@router.post(path="/uploadAvatar", description="上传头像")async def upload_avatar(avatar: UploadFile = File(...), user: User = Depends(Authentication())) -> Response:    path = FileManager.writer(avatar, FileEnum.AVATAR)    await UserMapper.set_avatar(path, user)    return Response.success()@router.get(path="/avatar/{userUid}")async def get_avatar(userUid:str) -> Response:    pass