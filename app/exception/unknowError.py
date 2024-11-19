#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/15# @Author : cyq# @File : params# @Software: PyCharm# @Desc:from fastapi.responses import JSONResponsefrom enums import HttpCodeEnumimport tracebackfrom utils import logfrom fastapi import status, Requestfrom .err_handle_func import DBError, SQLAlchemyErrorHandlerasync def execution_g_handler(request: Request, exc: Exception) -> JSONResponse:    """    异步处理全局异常的处理器    该函数旨在捕获应用程序中的异常，记录异常信息，并返回一个标准化的错误响应    :param request: 请求对象，用于记录异常时的请求上下文信息    :param exc: 异常对象，被捕获的异常实例，用于记录和响应具体的异常信息    :return: JSONResponse    """    log.debug("==========execution_g_handler=========")    return JSONResponse(        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,        content=dict(code=HttpCodeEnum.SERVICE_ERROR,                     data=None,                     msg="unknown error: " + str(exc)),    )async def errors_handling(request: Request, call_next) -> JSONResponse:    """    异步错误处理中间件。    该函数旨在捕获通过call_next传递的请求处理过程中可能抛出的任何异常，    并对这些异常进行统一的处理，返回一个包含错误信息的JSON响应。    :param request: Request对象，代表当前的HTTP请求。    :param call_next: 异步函数，负责处理当前的HTTP请求。    :return:        - 如果请求处理成功，则直接返回call_next的处理结果。        - 如果请求处理过程中发生异常，则返回一个包含错误信息的JSONResponse对象。    """    try:        log.info(f">> {request.method} : {request.url}")        log.info(f">> {request.client.host}")        return await call_next(request)    except Exception as exc:        log.exception(exc)        log.error("==========errors_handling=========")        # db操作查询不到等异常        if isinstance(exc, (DBError,                            SQLAlchemyErrorHandler)):            return exc.add_raise(str(exc))        # 内部异常 >> execution_g_handler        raise exc