import asyncio
from contextlib import asynccontextmanager

import click
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.cors import CORSMiddleware
from app.middware import CORS_ALLOW_ORIGINS, req_middleware, error_middleware, validation_exception_handler
from app.controller import RegisterRouterList
from app.ws import asgi_app
from utils import log
from common import rc, RedisClient
from config import Config
import os


@asynccontextmanager
async def lifespanApp(app: FastAPI):
    """
    lifespan
    """
    click.echo(Config.Banner)

    await init_db()
    redis_client = await init_redis()
    pool = await init_worker_pool()
    aps = await init_aps(redis_client)
    await init_proxy()
    await init_ui_browser()
    await init_ui_methods()
    app.scheduler = aps

    yield
    await aps.shutdown()
    await pool.stop()
    await rc.close_pool()


def caseHub():
    """
    启动 caseHub
    :return:
    """
    _hub = FastAPI(title="CaseHub",
                   description="CaseAutoHub",
                   version="0.0.2",
                   lifespan=lifespanApp,
                   default_response_class=ORJSONResponse)

    # 加载路由
    for item in RegisterRouterList:
        _hub.include_router(item.router)

    # 参数校验捕获
    _hub.add_exception_handler(
        RequestValidationError,
        handler=validation_exception_handler,
    )

    # 跨域
    _hub.add_middleware(CORSMiddleware, **CORS_ALLOW_ORIGINS)

    # 请求日志
    _hub.add_middleware(
        BaseHTTPMiddleware,
        dispatch=req_middleware,
    )

    # 全局异常捕获
    _hub.add_middleware(
        ServerErrorMiddleware,
        handler=error_middleware,
    )

    # 静态文件服务 - 用于访问截图等静态文件
    _hub.mount("/static", StaticFiles(directory=Config.ROOT), name="static")
    # socket io 挂载
    _hub.mount("/", asgi_app)
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

async def init_worker_pool():
    from common.redis_worker_pool import r_pool
    
    await r_pool.start()
    return r_pool





async def init_ui_browser():
    """
    初始化UI 浏览器
    """
    from croe.play.browser import BrowserManager
    if Config.INIT_PLAY_BROWSER:
        await BrowserManager.get_browser()
        log.info("初始UI化浏览器完成...")


async def init_ui_methods():
    """
    初始化UI 方法API入库
    """
    from script.init_method import init_play_method,init_play_locator
    await init_play_method()
    await init_play_locator()



hub = caseHub()
