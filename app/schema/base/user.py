#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/15
# @Author : cyq
# @File : user
# @Software: PyCharm
# @Desc: 用户相关的Schema定义
from typing import Union, Optional
from pydantic import BaseModel, field_validator, Field

from app.schema import PageSchema
from enums.UserEnum import GenderEnum
from app.exception import ParamsError
import re

__all__ = [
    "RegisterUser",
    "UserOptSchema",
    "RegisterAdmin",
    "UpdateUserSchema",
    "PasswordUserSchema",
    "LoginUser",
    "UserVars",
    "PageUserVars",
    "QueryUserVars",
    "AddOrUpdateUserVars",
    "PageUser"
]


class RegisterUser(BaseModel):
    """用户注册模型"""
    username: str = Field(..., title='用户名', description='用户名', max_length=20)
    gender: GenderEnum = Field(default=GenderEnum.MALE, title='性别', description='性别')
    phone: str = Field(..., title='手机号', description='手机号', max_length=11)
    tagName: Optional[str] = Field(None, title='标签名', description='标签名')
    depart_id: Optional[int] = Field(None, title='部门ID', description='部门ID')
    depart_name: Optional[str] = Field(None, title='部门', description='部门')
    isAdmin: Optional[bool] = Field(False, title='是否管理员', description='是否管理员')

    @field_validator('phone')
    @classmethod
    def check_phone(cls, v: str):
        """验证手机号格式"""
        par = "^((13[0-9])|(14)|(15[0-3,5-9])|(17[0,3,5-8])|(18[0-9])|166|198|199|(147))\\d{8}$"
        res = re.match(par, v.strip())
        if not res:
            raise ParamsError('手机号格式错误')
        return v


class UserOptSchema(BaseModel):
    """用户操作模型"""
    userId: int = Field(..., title='用户ID', description='用户ID')


class RegisterAdmin(BaseModel):
    """管理员注册模型"""
    username: str = Field(..., title='用户名', description='用户名')


class UpdateUserSchema(BaseModel):
    """更新用户模型"""
    id: int = Field(..., title='用户ID', description='用户ID')
    username: Optional[str] = Field(None, title='用户名', description='用户名')
    phone: Optional[str] = Field(None, title='手机号', description='手机号')
    gender: Optional[GenderEnum] = Field(None, title='性别', description='性别')
    depart_id: Optional[int] = Field(None, title='部门ID', description='部门ID')
    depart_name: Optional[str] = Field(None, title='部门', description='部门')
    tagName: Optional[str] = Field(None, title='标签名', description='标签名')


class PasswordUserSchema(BaseModel):
    """密码更新模型"""
    new_password: str = Field(..., title='新密码', description='新密码')
    old_password: str = Field(..., title='旧密码', description='旧密码')


class LoginUser(BaseModel):
    """用户登录模型"""
    username: str = Field(..., title='用户名', description='用户名')
    password: str = Field(..., title='密码', description='密码')


class UserVars(BaseModel):
    """用户变量模型"""
    key: str = Field(..., title='键', description='键')
    value: str = Field(..., title='值', description='值')
    description: Optional[str] = Field(None, title='描述', description='描述')


class AddOrUpdateUserVars(UserVars):
    """添加或更新用户变量模型"""
    id: Optional[int] = Field(None, title='ID', description='ID')


class PageUser(PageSchema):
    """用户分页"""
    ...


class PageUserVars(PageSchema):
    """用户变量分页查询模型"""
    key: Optional[str] = Field(None, title='键', description='键')


class QueryUserVars(BaseModel):
    """查询用户变量模型"""
    key: Optional[str] = Field(None, title='键', description='键')
