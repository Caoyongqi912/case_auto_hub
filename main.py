import asynciofrom apscheduler.schedulers.asyncio import AsyncIOSchedulerfrom app import hubfrom app.scheduler import Schedulerfrom utils import log@hub.on_event("startup")async def init_aps():    """    启动aps 任务    :return:    """    from config import Config    if Config.APS:        aps = AsyncIOScheduler()        try:            await Scheduler.init(aps)            # todo UI截图删除            Scheduler.start()            log.error(f"apscheduler 启动成成功")        except Exception as e:            log.error(f"apscheduler 启动失败: {e}")@hub.on_event("startup")async def init_redis():    from utils import rc    try:        await rc.init_pool()        log.info("redis 初始化链接完成...")    except Exception as e:        raise e@hub.on_event("startup")async def init_db():    """    初始化数据库    :return:    """    from app.model import create_table    # ...    try:        # asyncio.create_task(create_table())        log.info("数据库表创建链接完成...")    except Exception as e:        print(f"数据库表创建出现错误: {e}")        # 可以在这里添加更复杂的错误处理逻辑，比如尝试重新创建、记录错误日志、终止应用启动等@hub.on_event("startup")async def init_proxy():    from config import Config    if Config.Record_Proxy:        try:            asyncio.create_task(start_proxy())            log.info("record 代理启动完成...")        except Exception as e:            log.error(f"record 代理启动失败: {e}")@hub.on_event("shutdown")def shutdown_aps():    Scheduler.shutdown()async def start_proxy():    from mitmproxy.tools.dump import DumpMaster    from mitmproxy import options    from interface.recoder import InterfaceRecoder    dm = DumpMaster(        options=options.Options(            listen_host="0.0.0.0",            listen_port=7777,        ),        with_termlog=False,        with_dumper=False,    )    dm.addons.add(InterfaceRecoder())    await dm.run()