import asyncio
from contextlib import asynccontextmanager
import click
import logging
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from app.middware import (
    CORS_ALLOW_ORIGINS,
    req_middleware,
    app_exception_handler,
    sqlalchemy_exception_handler,
    validation_exception_handler,
)
from app.exception import AppException
from sqlalchemy.exc import SQLAlchemyError
from app.controller import RegisterRouterList
from app.ws import asgi_app
from utils import log
from common import rc, RedisClient
from config import Config

logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)
logging.getLogger('apscheduler.executors').setLevel(logging.WARNING)
logging.getLogger('apscheduler.jobstores').setLevel(logging.WARNING)


async def init_essential():
    """
    初始化核心依赖（数据库和 Redis）

    这些组件是其他服务的基础，必须优先初始化。
    """
    await init_db()
    redis_client = await init_redis()
    return redis_client


async def init_services(redis_client: RedisClient):
    """
    初始化业务服务（Worker Pool 和 APScheduler）

    依赖 Redis 连接。
    """
    pool = await init_worker_pool(redis_client)
    aps = await init_aps(redis_client)
    return pool, aps


async def init_optional():
    """
    初始化可选服务（代理、浏览器、UI 方法）

    这些组件失败不应该阻止应用启动。
    """
    await init_proxy()
    await init_ui_methods()


@asynccontextmanager
async def lifespanApp(app: FastAPI):
    """
    FastAPI 应用生命周期管理

    启动顺序：
    1. 打印 Banner
    2. 初始化核心依赖（数据库、Redis）
    3. 初始化业务服务（Worker Pool、APScheduler）
    4. 初始化可选服务

    关闭顺序：
    1. 关闭 APScheduler
    2. 关闭 Worker Pool
    3. 关闭 Redis 连接
    """
    click.echo(Config.Banner)

    redis_client = await init_essential()
    pool, aps = await init_services(redis_client)

    try:
        await init_optional()
    except Exception as e:
        log.warning(f"可选服务初始化失败: {e}")

    app.scheduler = aps

    yield

    await aps.shutdown() if aps else None
    await pool.stop() if pool else None
    await rc.close_pool()


def caseHub():
    """
    启动 caseHub FastAPI 应用

    中间件和组件的加载顺序：
    1. 异常处理器（最先）
    2. CORS 中间件（处理跨域）
    3. 其他中间件
    4. 静态文件服务
    5. Socket.IO 挂载
    6. 路由注册
    """
    _hub = FastAPI(
        title="CaseHub",
        description="CaseAutoHub",
        version="2.0",
        lifespan=lifespanApp,
        default_response_class=ORJSONResponse
    )

    for item in RegisterRouterList:
        _hub.include_router(item.router)

    _hub.add_exception_handler(AppException, app_exception_handler)
    _hub.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    _hub.add_exception_handler(RequestValidationError, validation_exception_handler)

    _hub.add_middleware(
        CORSMiddleware,
        **CORS_ALLOW_ORIGINS
    )

    _hub.add_middleware(BaseHTTPMiddleware, dispatch=req_middleware)

    _hub.mount("/static", StaticFiles(directory=Config.ROOT), name="static")
    _hub.mount("/", asgi_app, name="socketio")
    return _hub


async def init_aps(redis_client: RedisClient):
    """
    启动aps 任务
    :return:
    """
    from config import Config

    if Config.APS:
        from app.scheduler.aps.scheduler import hubScheduler
        try:
            await hubScheduler.initialize(redis_client)
            return hubScheduler
        except Exception as e:
            log.exception(f"apScheduler 启动失败: {e}")
    return None


async def init_redis():
    """
    初始化redis
    :return:
    """
    try:
        await rc.init_pool()
        log.info("redis 初始化链接完成...")
        return rc
    except Exception as e:
        log.warning(f"redis 初始化链接失败: {e}")


async def init_db():
    """
    初始化数据库
    :return:
    """
    from app.model import create_table
    # ...
    try:
        #    asyncio.create_task(create_table())
        #  防止未创建完表执行其他
        await create_table()
        log.info("数据库表创建链接完成...")
    except Exception as e:
        log.error(f"数据库表创建出现错误: {e}")


async def init_proxy():
    """
    初始化代理 不好用
    """
    from config import Config
    if Config.Record_Proxy:
        try:
            asyncio.create_task(start_proxy())
            log.info("record 代理启动完成...")
        except Exception as e:
            log.error(f"record 代理启动失败: {e}")


async def start_proxy():
    """
    启动代理不好用
    """
    from mitmproxy.tools.dump import DumpMaster
    from mitmproxy import options
    from croe.interface.recoder import InterfaceRecoder
    dm = DumpMaster(
        options=options.Options(
            listen_host="0.0.0.0",
            listen_port=7777,
        ),
        with_termlog=False,
        with_dumper=False,
    )
    dm.addons.add(InterfaceRecoder())
    await dm.run()


async def init_worker_pool(rc):
    from common.worker_pool import r_pool

    await r_pool.set_redis_client(rc)
    await r_pool.start()
    return r_pool




async def init_ui_methods():
    """
    初始化UI 方法API入库
    """
    from script.init_method import init_play_method, init_play_locator
    await init_play_method()
    await init_play_locator()


hub = caseHub()
