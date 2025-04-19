import asynciofrom contextlib import asynccontextmanagerimport clickfrom fastapi import FastAPIfrom fastapi.exceptions import RequestValidationErrorfrom starlette.middleware.base import BaseHTTPMiddlewarefrom starlette.middleware.errors import ServerErrorMiddlewarefrom starlette.middleware.cors import CORSMiddlewarefrom app.middware import CORS_ALLOW_ORIGINS, req_middleware, error_middleware, validation_exception_handlerfrom app.controller import RegisterRouterListfrom app.ws import async_io, asgi_appfrom utils import logfrom common import rc, RedisClientfrom config import Config@asynccontextmanagerasync def lifespanApp(app: FastAPI):    click.echo(Config.Banner)    await init_db()    redis_client = await init_redis()    aps = await init_aps(redis_client)    await init_proxy()    app.scheduler = aps    yield    await aps.shutdown()    await rc.close_pool()def caseHub():    _hub = FastAPI(        title="CaseHub",        description="CaseAutoHub",        version="0.0.1",        lifespan=lifespanApp,    )    # 加载路由    for item in RegisterRouterList:        _hub.include_router(item.router)    # 参数校验捕获    _hub.add_exception_handler(        RequestValidationError,        handler=validation_exception_handler,    )    # 跨域    _hub.add_middleware(        CORSMiddleware,        **CORS_ALLOW_ORIGINS    )    # 请求日志    _hub.add_middleware(        BaseHTTPMiddleware,        dispatch=req_middleware,    )    # 全局异常捕获    _hub.add_middleware(        ServerErrorMiddleware,        handler=error_middleware,    )    _hub.mount("/ws", asgi_app)    _hub.sio = async_io    return _hubasync def init_aps(redis_client: RedisClient):    """    启动aps 任务    :return:    """    from config import Config    if Config.APS:        from app.scheduler.aps.scheduler import TaskScheduler        scheduler = TaskScheduler(redis_client)        try:            if await scheduler.try_become_master():                log.info("Scheduler started as master")            else:                log.info("Scheduler started as slave")            return scheduler        except Exception as e:            log.exception(f"apscheduler 启动失败: {e}")async def init_redis():    try:        await rc.init_pool()        log.info("redis 初始化链接完成...")        return rc    except Exception as e:        log.warning(f"redis 初始化链接失败: {e}")async def init_db():    """    初始化数据库    :return:    """    from app.model import create_table    # ...    try:        asyncio.create_task(create_table())        log.info("数据库表创建链接完成...")    except Exception as e:        print(f"数据库表创建出现错误: {e}")async def init_proxy():    from config import Config    if Config.Record_Proxy:        try:            asyncio.create_task(start_proxy())            log.info("record 代理启动完成...")        except Exception as e:            log.error(f"record 代理启动失败: {e}")async def start_proxy():    from mitmproxy.tools.dump import DumpMaster    from mitmproxy import options    from interface.recoder import InterfaceRecoder    dm = DumpMaster(        options=options.Options(            listen_host="0.0.0.0",            listen_port=7777,        ),        with_termlog=False,        with_dumper=False,    )    dm.addons.add(InterfaceRecoder())    await dm.run()hub = caseHub()