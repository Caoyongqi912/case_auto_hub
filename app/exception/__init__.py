#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/15
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: FastAPI异常处理模块

from typing import Any, Optional
from fastapi import HTTPException, status
from enums import HttpCodeEnum


class AppException(HTTPException):
    """应用异常基类 - 所有业务异常的父类"""
    
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: int = HttpCodeEnum.SERVICE_ERROR,
        message: str = "请求错误",
        data: Any = None,
        headers: Optional[dict] = None,
        cause: Optional[Exception] = None,
    ):
        self.code = code
        self.data = data
        self.message = message
        
        if cause:
            self.__cause__ = cause
        
        super().__init__(
            status_code=status_code,
            detail={"code": code, "msg": message, "data": data},
            headers=headers,
        )


class AuthError(AppException):
    """认证/权限异常"""
    
    def __init__(
        self,
        message: str = "认证失败",
        data: Any = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=HttpCodeEnum.AUTH_ERROR,
            message=message,
            data=data,
            cause=cause,
        )


class NotFoundError(AppException):
    """资源未找到异常"""
    
    def __init__(
        self,
        message: str = "资源不存在",
        data: Any = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code=HttpCodeEnum.DB_NOT_FIND,
            message=message,
            data=data,
            cause=cause,
        )


class DatabaseError(AppException):
    """数据库异常"""
    
    def __init__(
        self,
        message: str = "数据库操作失败",
        data: Any = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=HttpCodeEnum.DB_CONNECT_ERROR,
            message=message,
            data=data,
            cause=cause,
        )


class ParamsError(AppException):
    """参数错误"""
    
    def __init__(
        self,
        message: str = "参数错误",
        data: Any = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=HttpCodeEnum.PARAMS_VALIDA_ERROR,
            message=message,
            data=data,
            cause=cause,
        )


class CommonError(AppException):
    """通用业务异常"""
    
    def __init__(
        self,
        message: str = "业务处理失败",
        data: Any = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=HttpCodeEnum.SERVICE_ERROR,
            message=message,
            data=data,
            cause=cause,
        )


class UIRuntimeError(AppException):
    """UI自动化运行时异常"""
    
    def __init__(
        self,
        message: str = "UI自动化执行失败",
        data: Any = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=HttpCodeEnum.SERVICE_ERROR,
            message=message,
            data=data,
            cause=cause,
        )


NotFind = NotFoundError
