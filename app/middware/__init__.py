#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/7
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: 中间件和异常处理器配置

from typing import Callable, Awaitable, Union

from fastapi import status, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response

from app.exception import AppException
from enums import HttpCodeEnum
from utils import MyLoguru

LOG = MyLoguru().get_logger()

RequestResponseEndpoint = Callable[[Request], Awaitable[Response]]

CORS_ALLOW_ORIGINS = {
    "allow_origins": ['*'],
    "allow_credentials": True,
    "allow_methods": ['*'],
    "allow_headers": ['*'],
}


async def req_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """请求中间件 - 记录请求日志"""
    LOG.info(f">> {request.method} : {request.url}")
    LOG.info(f">> {request.client.host}")
    return await call_next(request)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """应用异常处理器 - 处理所有AppException及其子类"""
    LOG.error(
        f"应用异常 [{exc.code}]: {exc.message}",
        extra={
            "status_code": exc.status_code,
            "data": exc.data,
            "path": request.url.path,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(exc.detail),
        headers=exc.headers,
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """SQLAlchemy异常处理器 - 处理数据库异常"""
    LOG.error(
        f"数据库异常: {exc}",
        exc_info=True,
        extra={"path": request.url.path}
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder({
            "code": HttpCodeEnum.DB_CONNECT_ERROR,
            "msg": "数据库操作失败",
            "data": None,
        })
    )


async def validation_exception_handler(
    request: Request,
    exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """处理请求验证异常"""
    LOG.warning(
        f"参数验证失败: {exc}",
        extra={"path": request.url.path}
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder({
            "code": HttpCodeEnum.PARAMS_VALIDA_ERROR,
            "data": None,
            "msg": validation_msg(exc),
        })
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器 - 处理未捕获的异常"""
    LOG.error(
        f"未处理的异常: {exc}",
        exc_info=True,
        extra={"path": request.url.path}
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder({
            "code": HttpCodeEnum.SERVICE_ERROR,
            "data": None,
            "msg": "服务器内部错误",
        })
    )


def validation_msg(exc: Union[RequestValidationError, ValidationError]) -> str:
    """处理验证错误信息"""
    exc_info = exc.errors()[0]
    error_type = exc_info.get("type")
    param = exc_info.get("loc")[-1]
    msg = exc_info.get("msg")

    if "missing" in error_type:
        return f"miss field: {param}"
    elif "type_error" in error_type or "value_error" in error_type:
        return f"{msg} : {param}"
    return "参数解析失败"
