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
    """
    接口/用例结果标志 (命名常量, 非真 enum)。

    该类的成员值是 bool: SUCCESS = True, ERROR = False。
    它故意保留 .SUCCESS / .ERROR 形态, 让代码里
    case_result.result = InterfaceAPIResultEnum.ERROR
    读起来比 case_result.result = False 自描述得多, 写库 Boolean 列也直接 OK。

    重要: 不要给它赋字符串 (如 InterfaceAPIResultEnum.ERROR = "ERROR"),
    SQLAlchemy 不会报错, Python 会把非空字符串当成 True 静默写反。

    旧 InterfaceCaseResultEnum (SUCCESS="SUCCESS", ERROR="ERROR", 同名 str 值)
    已删除: 0 引用, 且同名不同值, 是两个看起来一样的命名常量陷阱。
    需用 str 状态请改用 InterfaceAPIStatusEnum.OVER / RUNNING。
    """
    SUCCESS = True
    ERROR = False

class InterfaceCaseErrorStep:
    STOP = 1
    CONTINUE = 0

class InterfaceDataValueType:
    TEXT = "text"
    FILE = "file"


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
    RemoteProtocolError = "RemoteProtocolError  请检查网络是否正常！"


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

class StepStatusEnum(enum.Enum):
    """步骤结果状态 (跟 InterfaceCaseContentResult.status 列对齐)。
    """
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    # 兼容旧 default='PENDING' / 历史 DB 数据 (interfaceResultModel 之前 default="PENDING")。
    PENDING = "PENDING"
