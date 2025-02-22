#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/14# @Author : cyq# @File : log_wrapper# @Software: PyCharm# @Desc:from redlock import RedLock, RedLockErrorimport asyncioimport functoolsfrom app.model import async_sessionfrom config import Configfrom utils import logimport osconnection_details = [{    "host": Config.REDIS_SERVER,    "port": Config.REDIS_PORT,    "db": Config.REDIS_DB,    # "password": Config.REDIS_PASSWORD}]def lock(key):    """    redis分布式锁，基于redlock    :param key: 唯一key，确保所有任务一致，但不与其他任务冲突    :return:    """    def decorator(func):        if asyncio.iscoroutinefunction(func):            @functools.wraps(func)            async def wrapper(*args, **kwargs):                log.debug(f"args[1] = {args[1]}")                try:                    with RedLock(f"distributed_lock:{func.__name__}:{key}{args[1]}",                                 connection_details=connection_details,                                 ttl=30000,  # 锁释放时间为30s                                 ):                        log.info(f"进程: {os.getpid()} 获取任务成功")                        return await func(*args, **kwargs)                except RedLockError:                    log.error(f"进程: {os.getpid()}获取任务失败, 其他任务执行中")        else:            @functools.wraps(func)            def wrapper(*args, **kwargs):                try:                    with RedLock(f"distributed_lock:{func.__name__}:{key}",                                 connection_details=connection_details,                                 ttl=30000,  # 锁释放时间为30s                                 ):                        return func(*args, **kwargs)                except RedLockError:                    log.error(f"进程: {os.getpid()}获取任务失败, 其他任务执行中")        return wrapper    return decoratordef session_transaction(func):    @functools.wraps(func)    async def wrapper(cls, *args, **kwargs):        session = kwargs.get('session', None)        # 如果没有传入 session，则创建一个新的 session        if not session:            async with async_session() as session:                async with session.begin():                    return await func(cls, *args, **kwargs, session=session)        else:            return await func(cls, *args, **kwargs, session=session)    return wrapperdef session_wrapper(func):    @functools.wraps(func)    async def wrapper(cls, *args, **kwargs):        session = kwargs.get('session', None)        # 如果没有传入 session，则创建一个新的 session        if not session:            async with async_session() as session:                return await func(cls, *args, **kwargs, session=session)        else:            return await func(cls, *args, **kwargs, session=session)    return wrapper