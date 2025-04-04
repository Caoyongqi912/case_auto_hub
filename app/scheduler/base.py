#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/4/3# @Author : cyq# @File : schedulerManager# @Software: PyCharm# @Desc:from typing import Optional, Any, Listfrom apscheduler.job import Jobfrom apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStorefrom apscheduler.schedulers.asyncio import AsyncIOSchedulerfrom apscheduler.triggers.base import BaseTriggerfrom app.model import async_enginefrom app.scheduler.tasks import run_heartbeatfrom common.redisClient import get_redis, RedisClientfrom utils import MyLogurufrom config import Configlog = MyLoguru().get_logger()_Redis = get_redis()APSJobStores = {    "default": SQLAlchemyJobStore(        engine=async_engine.sync_engine,        engine_options={            'connect_args': {'connect_timeout': 5}        },    )}def master_required(func):    async def wrapper(self, *args, **kwargs):        if not await self.is_master():            raise PermissionError("Master node required")        return await func(self, *args, **kwargs)    return wrapperclass BaseScheduler:    """调度器基类（生产级实现）"""    def __init__(self, redis_client: 'RedisClient'):        self.redis = redis_client        self.scheduler = AsyncIOScheduler()        self.lock_key = "scheduler:master_lock"    async def try_become_master(self) -> bool:        """        尝试成为主节点。        该方法通过 Redis 的分布式锁机制，尝试获取主节点的控制权。如果成功获取锁，则启动调度器并配置相关任务。        返回值:            bool: 如果成功获取锁并成为主节点，返回 True；否则返回 False。        """        # 启动时强制清除当前实例持有的旧锁（如果存在）        if self.redis.r:            await self.redis.r.delete(self.lock_key)        # 尝试在 Redis 中设置一个分布式锁，锁的键为 self.lock_key，值为 "1"，锁的有效期为 60 秒        acquired = await self.redis.r.set(            self.lock_key,            "1",            nx=True,            ex=60  # 锁60秒过期        )        # 如果成功获取锁，则配置调度器并启动它，同时设置相关任务        if acquired:            self.scheduler.configure(jobstores=Config.APSJobStores)            self.scheduler.start()            self._setup_jobs()        # 返回是否成功获取锁的结果        return bool(acquired)    def _setup_jobs(self):        """        主节点才设置的任务        该方法用于在主节点上设置定时任务，主要包括心跳任务。心跳任务用于定期续期锁，确保主节点的持续运行。        """        # 心跳任务（每30秒续期锁）        try:            # 添加心跳任务到调度器，每30秒执行一次run_heartbeat函数            self.scheduler.add_job(                run_heartbeat,                "interval",                seconds=30,                id="heartbeat",                replace_existing=True,                executor="default",  # 明确指定执行器                misfire_grace_time=60  # 允许60秒内的延迟            )            log.debug("set heartbeat job success")        except Exception as e:            # 如果添加心跳任务失败，记录错误日志            log.debug("set heartbeat job failed")            log.exception(e)    @master_required    async def add_job(            self,            func: callable,            job_id: str,            trigger: BaseTrigger,            *args: Any,            **kwargs: Any    ) -> Optional[Job]:        """添加定时任务（需在主节点执行）"""        return self.scheduler.add_job(            func=func,            id=job_id,            trigger=trigger,            misfire_grace_time=3600,  # 允许1小时内的延迟            max_instances=1,  # 确保不会并发执行            *args,            **kwargs        )    async def remove_job(self, job_id: str) -> None:        """移除定时任务"""        if self.scheduler.get_job(job_id):            self.scheduler.remove_job(job_id)            log.info(f"Removed job: {job_id}")    async def get_job(self, job_id: str) -> Optional[Job]:        """获取任务详情"""        return self.scheduler.get_job(job_id) if self.scheduler else None    async def get_all_jobs(self, prefix: str = None) -> List[Job]:        """获取所有任务（可选前缀过滤）"""        if not self.scheduler:            return []        jobs = self.scheduler.get_jobs()        return [job for job in jobs if not prefix or job.id.startswith(prefix)]from fastapi import Request, HTTPExceptionasync def get_scheduler(request: Request) -> BaseScheduler:    """依赖注入获取调度器实例"""    scheduler = request.app.state.scheduler    if not scheduler:        raise HTTPException(status_code=503, detail="Scheduler not available")    return scheduler