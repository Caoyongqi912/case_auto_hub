#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/15# @Author : cyq# @File : user# @Software: PyCharm# @Desc:from typing import Unionfrom pydantic import BaseModel, validator, Fieldfrom enums.UserEnum import GenderEnumfrom app.exception import ParamsErrorimport reclass RegisterUser(BaseModel):    username: str    gender: GenderEnum = GenderEnum.MALE    phone: str    tagName: str | None = None    departmentID: Union[int, None] = None    isAdmin: Union[bool, None] = False    @validator('phone')    def check_phone(cls, v: str):        par = "^((13[0-9])|(14)|(15[0-3,5-9])|(17[0,3,5-8])|(18[0-9])|166|198|199|(147))\\d{8}$"        res = re.match(par, v.strip())        print(res)        if not res:            raise ParamsError('手机号格式错误')        return v