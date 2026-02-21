#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/7
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc:
from typing import Callable, Awaitable, Union

from fastapi import status, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.responses import Response

from app.exception import AuthError, NotFind, SQLAlchemyErrorHandler, UIRuntimeError, ParamsError, CommonError
from enums import HttpCodeEnum
from utils import MyLoguru

LOG = MyLoguru().get_logger()

# ==================== 类型定义 ====================
RequestResponseEndpoint = Callable[[Request], Awaitable[Response]]

# ==================== CORS 配置 ====================
CORS_ALLOW_ORIGINS = {
    "allow_origins": ['*'],
    "allow_credentials": True,
    "allow_methods": ['*'],
    "allow_headers": ['*'],
}


# ==================== 中间件 ====================
async def req_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """
    请求中间件 - 记录请求日志
    """
    LOG.info(f">> {request.method} : {request.url}")
    LOG.info(f">> {request.client.host}")
    return await call_next(request)


async def error_middleware(_: Request, exc: Exception) -> Union[Response, None]:
    """
    异常中间件 - 统一异常处理
    """
    if isinstance(exc, (AuthError, NotFind, SQLAlchemyErrorHandler, CommonError)):
        return exc.add_raise()
    elif isinstance(exc, (ParamsError, UIRuntimeError)):
        raise exc
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=dict(code=HttpCodeEnum.SERVICE_ERROR, data=None, msg="service error"),
        )


async def validation_exception_handler(_: Request, exc: Union[RequestValidationError, ValidationError]) -> JSONResponse:
    """
    处理请求验证异常
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder({
            "code": HttpCodeEnum.PARAMS_VALIDA_ERROR,
            "data": None,
            "msg": validation_msg(exc),
        })
    )


# ==================== 辅助函数 ====================
def validation_msg(exc: Union[RequestValidationError, ValidationError]) -> str:
    """
    处理验证错误信息
    """
    LOG.info(exc)
    exc_info = exc.errors()[0]
    error_type = exc_info.get("type")
    param = exc_info.get("loc")[-1]
    msg = exc_info.get("msg")

    if "missing" in error_type:
        return f"miss field: {param}"
    elif "type_error" in error_type or "value_error" in error_type:
        return f"{msg} : {param}"
    return "参数解析失败"