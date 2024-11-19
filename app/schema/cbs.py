#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/19# @Author : cyq# @File : cbs# @Software: PyCharm# @Desc:from pydantic import BaseModel, validatorfrom app.exception.err_handle_func import ParamsErrorclass CBSCookie(BaseModel):    username: str    env: str | None = "uat"    password: str | None = "App!User5i5j@"    city: str = "beijing"    @validator("username", "city")    def check_username(cls, v):        if not v:            raise ParamsError("username is required")        return v    @validator("env")    def check_env(cls, v):        if v not in ["uat", "sso", "sit"]:            raise ParamsError("env only support [sit,uat,sso]")        return v