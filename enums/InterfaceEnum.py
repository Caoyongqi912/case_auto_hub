#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/26# @Author : cyq# @File : InterfaceEnum# @Software: PyCharm# @Desc:class InterfaceResponseStatusCodeEnum:    SUCCESS = 200class InterfaceAPIStatusEnum:    """接口结果实例状态"""    RUNNING = "RUNNING"    OVER = "OVER"class InterfaceAPIResultEnum:    """接口结果实例状态"""    SUCCESS = "SUCCESS"    ERROR = "ERROR"class InterfaceCaseErrorStep:    STOP = 1    CONTINUE = 0class InterfaceRequestTBodyTypeEnum:    """接口请求体类型"""    HEADERS = "headers"    PARAMS = "params"    JSON = "json"    FORM_DATA = "data"    Null = 0    Json = 1    Data = 2class InterfaceRequestMethodEnum:    """接口请求方法"""    GET = "GET"    POST = "POST"    PUT = "PUT"    DELETE = "DELETE"class InterfaceExtractTargetVariablesEnum:    KEY = "key"    VALUE = "value"    Target = "target"    ResponseJson = 1    ResponseHeader = 2    BeforeScript = 3    BeforeParams = 4    BeforeSQL = 10    AfterScript = 5    ResponseJsonExtract = 6    ResponseHeaderExtract = 7    ResponseTextExtract = 8    RequestCookieExtract = 9class InterfaceResponseErrorMsgEnum:    ResponseTimeout = "Response Timeout 响应超时！"    ConnectTimeout = "Connect Timeout  请求超时！"    HTTPStatusError = "HTTP Status Error  HTTP状态码错误！"class BeforeSqlDBTypeEnum:    """前置SQL数据库类型"""    MYSQL = 1    ORACLE = 2    REDIS = 3class InterfaceUploadEnum:    Swagger = "1"    PostMan = "2"    ApiPost = "3"    YApi = "4"