#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/11/26
# @Author : cyq
# @File : InterfaceEnum
# @Software: PyCharm
# @Desc:
import enum


class InterfaceResponseStatusCodeEnum:
    SUCCESS = 200


class InterfaceAPIStatusEnum:
    """接口结果实例状态"""
    RUNNING = "RUNNING"
    OVER = "OVER"


class InterfaceAPIResultEnum:
    """接口结果实例状态"""
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class InterfaceCaseErrorStep:
    STOP = 1
    CONTINUE = 0


class InterfaceRequestTBodyTypeEnum:
    """接口请求体类型"""
    AUTH = "auth"
    HEADERS = "headers"
    PARAMS = "params"
    JSON = "json"
    FORM_DATA = "data"
    FORM_FILES = "files"
    Content = "content"

    Null = 0
    Raw = 1
    Data = 2
    UrlEncoded = 3


class InterfaceRequestMethodEnum:
    """接口请求方法"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class ExtractTargetVariablesEnum:
    KEY = "key"
    VALUE = "value"
    Target = "target"
    ResponseJson = 1
    ResponseHeader = 2
    BeforeScript = 3
    BeforeParams = 4
    BeforeSQL = 10
    ContentSQL = 12
    AfterScript = 5
    LOOP = 13

    PLAY_VARIABLE = 14  # UI 方法提取
    StepScript = 11  # UI 脚本用例流程
    StepDB = 15  # DB提取
    ResponseJsonExtract = 6
    ResponseHeaderExtract = 7
    ResponseTextExtract = 8
    RequestCookieExtract = 9


class InterfaceResponseErrorMsgEnum:
    ResponseTimeout = "Response Timeout 响应超时！"
    ConnectTimeout = "Connect Timeout  请求超时！"
    ConnectFailed = "Connect Failed  请求链接失败！"
    HTTPStatusError = "HTTP Status Error  HTTP状态码错误！"
    UnsupportedProtocol = "Unsupported Protocol  请检查请求协议！"


class BeforeSqlDBTypeEnum:
    """前置SQL数据库类型"""
    MYSQL = 1
    ORACLE = 2
    REDIS = 3


class InterfaceUploadEnum:
    Swagger = "1"
    PostMan = "2"
    ApiPost = "3"
    YApi = "4"


class InterfaceAuthType(enum.IntEnum):
    """接口认证方式"""
    No_Auth = 1
    BASIC_Auth = 3
    BEARER_Auth = 4
    KV_Auth = 2
