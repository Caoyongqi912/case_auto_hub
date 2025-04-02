#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : user# @Software: PyCharm# @Desc:from fastapi import APIRouter, Depends, UploadFile, Filefrom sqlalchemy.orm import deferfrom app.mapper.file import FileMapperfrom app.mapper.user import UserMapperfrom app.model.base import Userfrom app.response import Responsefrom app.schema import PageSchemafrom app.schema.base import RegisterUser, RegisterAdmin, LoginUserfrom app.controller import Authenticationfrom app.schema.base.user import UserOptSchema, UpdateUserSchema, PasswordUserSchemafrom enums import FileEnumfrom utils import MyLoguru, logfrom utils.fileManager import FileManagerfrom fastapi.responses import FileResponseLOG = MyLoguru().get_logger()router = APIRouter(prefix="/user", tags=["用户"])@router.post(path="/pageUser", description="分页查询用户")async def page_user(page: PageSchema, user=Depends(Authentication())):    """    分页查询用户    :param page:分页信息    :param user:鉴权    :return:    """    LOG.debug(user)    data = await UserMapper.page_query(**page.model_dump())    return Response.success(data, exclude=("password",))@router.post("/updatePwd", description="修改密码")async def update_pwd(pwdInfo: PasswordUserSchema, user: User = Depends(Authentication())):    """    修改密码    :param pwdInfo:    :param user:    :return:    """    # await UserMapper.update_pwd(user.id, pwd)    return Response.success()@router.get(path="/query", description="查询所有用户")async def query_user(_=Depends(Authentication(isAdmin=True))):    """    查询所有用户    """    users = await UserMapper.query_all()    return Response.success(users, exclude=("password",))@router.get(path='/query_by_username', description="查询用户")async def query_by_username(username: str | None, _=Depends(Authentication(isAdmin=True))):    """    通过用户名 模糊搜索    :param username:    :param _:    :return:    """    if username is None:        return Response.success([])    users = await UserMapper.filter_user_by_username(username)    return Response.success(users, exclude=("password",))@router.get(path="/currentUser", description="获取当前用户信息")async def current_user_info(user=Depends(Authentication())):    """通过userID 获取用户信息"""    return Response.success(user, exclude={"password"})@router.post(path="/registerUser",             description="注册用户")async def register_user(user: RegisterUser, _=Depends(Authentication(isAdmin=True))):    await UserMapper.register(**user.model_dump(        exclude_none=True,        exclude_unset=True    ))    return Response.success()@router.post(path="/registerAdmin", description="添加管理")async def register_admin(user: RegisterAdmin):    await UserMapper.register_admin(**user.model_dump())    return Response.success()@router.post(path="/remove", description="用户删除")async def remove_user(user: UserOptSchema, _: User = Depends(Authentication(isAdmin=True))):    await UserMapper.delete_by_id(user.userId)    return Response.success()@router.post(path="/update", description="用户删除")async def update_user(user: UpdateUserSchema, _: User = Depends(Authentication(isAdmin=True))):    await UserMapper.update_by_id(**user.model_dump())    return Response.success()@router.post(path="/login", description="登陆")async def login(loginInfo: LoginUser):    token = await UserMapper.login(**loginInfo.model_dump())    log.debug(token)    return Response.success(token)@router.post(path="/uploadAvatar", description="上传头像")async def upload_avatar(avatar: UploadFile = File(...), user: User = Depends(Authentication())):    await FileManager.save_avatar(avatar, user)    return Response.success()