#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : __init__.py# @Software: PyCharm# @Desc:import functoolsfrom fastapi import Headerfrom utils import MyLogurufrom app.mapper.user import UserMapperfrom ..exception import AuthErrorLOG = MyLoguru().get_logger()class Authentication:    def __init__(self, isAdmin: bool = False):        self.isAdmin = isAdmin    async def __call__(self, token: str = Header(None)):        if not token:            raise AuthError("请先登录")        current_user_dict = await UserMapper.parse_token(token)        # 要求admin。但是是普通用户        if self.isAdmin is True and current_user_dict["isAdmin"] is False:            raise AuthError("无权操作")        current_user = await UserMapper.get_by_id(current_user_dict["id"], )        LOG.info(f"current user {current_user}")        return current_userfrom app.controller import filefrom .project import project, partfrom .user import user, departmentfrom .ui import ui_case, ui_task, ui_step_group, ui_env, ui_method, ui_step,ui_varsfrom .interface import interfaceCase, interfaceApi, interfaceTask, interfaceResult, interfaceRecordRegisterRouterList = [    file,    project,    part,    user,    department,    ui_case,    ui_env,    ui_method,    ui_step,    ui_task,    ui_step_group,    ui_vars,    interfaceTask,    interfaceResult,    interfaceApi,    interfaceCase,    interfaceRecord]