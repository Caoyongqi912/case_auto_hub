#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/7
# @Author : cyq
# @File : HTTP_CODE_ENUM
# @Software: PyCharm
# @Desc: HTTP响应码枚举类


class HttpCodeEnum:
    """HTTP业务响应码枚举"""
    
    OK = 0
    PARAMS_VALIDA_ERROR = 2000
    DB_NOT_FIND = 2001
    DB_CONNECT_ERROR = 2002
    SERVICE_ERROR = 1000
    AUTH_ERROR = 4000
