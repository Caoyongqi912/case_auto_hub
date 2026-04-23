#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/3/4
# @Author : cyq
# @File : scheduler
# @Software: PyCharm
# @Desc: Celery 调度器核心模块
import asyncio
from typing import TypeVar, Union, Callable, Optional, Dict, Any, List
from datetime import datetime

from app.model.base.job import AutoJob
from app.model.playUI.playTask import PlayTask
from app.model.interfaceAPIModel.interfaceTaskModel import InterfaceTask
from app.scheduler.celer9.trigger import CeleryTrigger, create_trigger
from app.scheduler.celer9.app import (
    celery_app,
    update_beat_schedule,
    replace_beat_schedule,
    remove_beat_schedule,
    get_beat_schedule,
    CeleryScheduleBuilder,
)
from app.scheduler.celer9.tasks import (
    celery_submit_interface_task,
    celery_submit_play_task,
    auto_job_to_dict,
)
from common import RedisClient
from config import Config
from enums import TriggerTypeEnum
from utils import MyLoguru

log = MyLoguru().get_logger()

TaskType = TypeVar("TaskType", bound=Union[PlayTask, InterfaceTask])


async def run_sync(func: Callable, *args, **kwargs) -> Any:
    """
    在异步环境中运行同步函数
    
    Args:
        func: 同步函数
        *args: 位置参数
        **kwargs: 关键字参数
    
    Returns:
        Any: 函数执行结果
    """
    return await asyncio.to_thread(func, *args, **kwargs)


class CeleryHubScheduler:
    """
    Celery 调度器核心类
    
    提供与 APScheduler HubScheduler 一致的接口和功能：
    - 分布式锁机制确保主从节点
    - 任务注册、移除、暂停、恢复
    - 支持 CRON、固定间隔、单次执行三种触发方式
    - 心跳机制保持主节点状态
    
    Attributes:
        redis: Redis 客户端实例
        lock_key: 分布式锁键名
        lock_value: 锁值
        lock_ex: 锁过期时间（秒）
        is_master: 是否为主节点
    """
    
    redis: Optional[RedisClient] = None
    is_master: bool = False

    def __init__(self):
        self._lock_key = "celery_scheduler:master_lock"
        self._lock_value = "1"
        self._lock_ex = 60
        self._initialized = False
        self._job_registry: Dict[str, Dict[str, Any]] = {}

    async def initialize(self, redis: RedisClient) -> bool:
        """
        初始化调度器
        
        尝试获取分布式锁，成功则成为主节点，
        负责管理定时任务的调度。
        
        Args:
            redis: Redis 客户端实例
        
        Returns:
            bool: 是否成功成为主节点
        """
        self.redis = redis
        
        restart_key = f"{self._lock_key}_restart"
        restart_flag = await self.redis.r.get(restart_key)
        
        if not restart_flag:
            await self.redis.r.delete(self._lock_key)
            await self.redis.r.set(restart_key, "1", ex=60)
        
        acquired = await self.redis.r.set(
            self._lock_key,
            self._lock_value,
            nx=True,
            ex=self._lock_ex
        )
        
        if acquired:
            self.is_master = True
            self._initialized = True
            log.info("[CeleryScheduler] 初始化为主节点")
            
            await self._setup_heartbeat()
            await self._setup_job_printer()
            
            return True
        
        self.is_master = False
        self._initialized = True
        log.info("[CeleryScheduler] 初始化为从节点")
        return False

    async def add_job(
        self,
        task_func: Callable,
        trigger: CeleryTrigger,
        job_id: str,
        name: Optional[str] = None,
        args: Optional[tuple] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        queue: str = "default",
    ) -> bool:
        """
        注册定时任务
        
        Args:
            task_func: 任务函数
            trigger: 触发器实例
            job_id: 任务唯一标识
            name: 任务名称
            args: 位置参数
            kwargs: 关键字参数
            queue: 任务队列
        
        Returns:
            bool: 是否注册成功
        """
        if not trigger.is_valid:
            log.warning(f"[CeleryScheduler] 无效的触发器，跳过注册: {job_id}")
            return False
        
        task_path = self._get_task_path(task_func)
        
        schedule_entry = CeleryScheduleBuilder.build_beat_schedule_entry(
            task_name=job_id,
            task_path=task_path,
            schedule_config=trigger.schedule,
            args=args,
            kwargs=kwargs,
            queue=queue,
        )
        
        self._job_registry[job_id] = {
            "name": name or job_id,
            "task_path": task_path,
            "trigger": trigger,
            "args": args,
            "kwargs": kwargs,
            "queue": queue,
            "enabled": True,
            "created_at": datetime.now().isoformat(),
        }
        
        update_beat_schedule({job_id: schedule_entry})
        log.info(f"[CeleryScheduler] 注册任务成功: {job_id} -> {task_path}")
        return True

    async def remove_job(self, job_id: str) -> bool:
        """
        移除定时任务
        
        Args:
            job_id: 任务唯一标识
        
        Returns:
            bool: 是否移除成功
        """
        if job_id in self._job_registry:
            del self._job_registry[job_id]
        
        result = remove_beat_schedule(job_id)
        if result:
            log.info(f"[CeleryScheduler] 移除任务成功: {job_id}")
        else:
            log.warning(f"[CeleryScheduler] 任务不存在: {job_id}")
        return result

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            job_id: 任务唯一标识
        
        Returns:
            Optional[Dict[str, Any]]: 任务信息，不存在则返回 None
        """
        schedules = get_beat_schedule()
        if job_id in schedules:
            job_info = self._job_registry.get(job_id, {})
            return {
                "id": job_id,
                "schedule": schedules[job_id],
                "registry_info": job_info,
            }
        return None

    async def get_jobs(self) -> List[Dict[str, Any]]:
        """
        获取所有任务信息
        
        Returns:
            List[Dict[str, Any]]: 任务列表
        """
        schedules = get_beat_schedule()
        jobs = []
        for job_id, schedule in schedules.items():
            job_info = self._job_registry.get(job_id, {})
            jobs.append({
                "id": job_id,
                "schedule": schedule,
                "registry_info": job_info,
            })
        return jobs

    async def switch_job(self, job_id: str, enable: bool) -> bool:
        """
        启用或禁用任务
        
        Args:
            job_id: 任务唯一标识
            enable: True 启用，False 禁用
        
        Returns:
            bool: 是否操作成功
        """
        job_info = self._job_registry.get(job_id)
        if not job_info:
            log.warning(f"[CeleryScheduler] 任务不存在: {job_id}")
            return False
        
        if enable:
            if job_id in get_beat_schedule():
                log.info(f"[CeleryScheduler] 任务已启用: {job_id}")
                return True
            
            trigger = job_info.get("trigger")
            if trigger and trigger.is_valid:
                task_path = job_info.get("task_path")
                schedule_entry = CeleryScheduleBuilder.build_beat_schedule_entry(
                    task_name=job_id,
                    task_path=task_path,
                    schedule_config=trigger.schedule,
                    args=job_info.get("args"),
                    kwargs=job_info.get("kwargs"),
                    queue=job_info.get("queue", "default"),
                )
                update_beat_schedule({job_id: schedule_entry})
                job_info["enabled"] = True
                log.info(f"[CeleryScheduler] 启用任务成功: {job_id}")
        else:
            remove_beat_schedule(job_id)
            job_info["enabled"] = False
            log.info(f"[CeleryScheduler] 禁用任务成功: {job_id}")
        
        return True

    async def modify(self, job: AutoJob) -> bool:
        """
        修改任务配置
        
        Args:
            job: AutoJob 模型实例
        
        Returns:
            bool: 是否修改成功
        """
        existing_job = await self.get_job(job.uid)
        
        if existing_job:
            await self.remove_job(job.uid)
        
        result = await self.add_auto_job(job)
        if result:
            await self.switch_job(job.uid, job.job_enabled)
            log.info(f"[CeleryScheduler] 修改任务成功: {job.uid}")
        return result

    async def add_auto_job(self, job: AutoJob) -> bool:
        """
        添加自动化任务
        
        根据 job_type 自动选择任务类型：
        - job_type == 1: 接口测试任务
        - job_type == 2: UI 自动化任务
        
        Args:
            job: AutoJob 模型实例
        
        Returns:
            bool: 是否添加成功
        
        Raises:
            ValueError: 无效的任务类型
        """
        if job.job_type == 1:
            return await self._add_interface_job(job)
        elif job.job_type == 2:
            return await self._add_play_job(job)
        else:
            raise ValueError(f"无效的任务类型: {job.job_type}")

    async def _add_interface_job(self, job: AutoJob) -> bool:
        """
        添加接口测试定时任务
        
        Args:
            job: AutoJob 模型实例
        
        Returns:
            bool: 是否添加成功
        """
        trigger = create_trigger(
            trigger_type=job.job_trigger_type,
            kw=job.trigger_value
        )
        
        job_data = auto_job_to_dict(job)
        
        return await self.add_job(
            task_func=celery_submit_interface_task,
            trigger=trigger,
            job_id=job.uid,
            name=job.job_name,
            kwargs={"job_data": job_data},
            queue="interface_tasks",
        )

    async def _add_play_job(self, job: AutoJob) -> bool:
        """
        添加 UI 自动化定时任务
        
        Args:
            job: AutoJob 模型实例
        
        Returns:
            bool: 是否添加成功
        """
        trigger = create_trigger(
            trigger_type=job.job_trigger_type,
            kw=job.trigger_value
        )
        
        job_data = auto_job_to_dict(job)
        
        return await self.add_job(
            task_func=celery_submit_play_task,
            trigger=trigger,
            job_id=job.uid,
            name=job.job_name,
            kwargs={"job_data": job_data},
            queue="play_tasks",
        )

    async def _setup_heartbeat(self) -> None:
        """
        设置心跳任务
        
        每 30 秒执行一次，用于续期分布式锁
        """
        try:
            from app.scheduler.celer9.trigger import create_interval_trigger
            
            trigger = create_interval_trigger(seconds=30)
            
            await self.add_job(
                task_func=celery_submit_interface_task.__class__.__module__ + ".celery_heartbeat",
                trigger=trigger,
                job_id="celery_heartbeat",
                name="Celery Scheduler Heartbeat",
                queue="default",
            )
            
            trigger2 = create_interval_trigger(seconds=30)
            schedule_entry = CeleryScheduleBuilder.build_beat_schedule_entry(
                task_name="celery_heartbeat",
                task_path="app.scheduler.celer9.tasks.celery_heartbeat",
                schedule_config=trigger2.schedule,
                queue="default",
            )
            update_beat_schedule({"celery_heartbeat": schedule_entry})
            
            log.info("[CeleryScheduler] 心跳任务设置完成")
        except Exception as e:
            log.error(f"[CeleryScheduler] 设置心跳任务失败: {e}")

    async def _setup_job_printer(self) -> None:
        """
        设置任务打印任务
        
        每小时打印一次当前所有调度任务
        """
        try:
            from app.scheduler.celer9.trigger import create_interval_trigger
            
            trigger = create_interval_trigger(hours=1)
            schedule_entry = CeleryScheduleBuilder.build_beat_schedule_entry(
                task_name="celery_print_jobs",
                task_path="app.scheduler.celer9.tasks.celery_print_jobs",
                schedule_config=trigger.schedule,
                queue="default",
            )
            update_beat_schedule({"celery_print_jobs": schedule_entry})
            
            log.info("[CeleryScheduler] 任务打印器设置完成")
        except Exception as e:
            log.error(f"[CeleryScheduler] 设置任务打印器失败: {e}")

    async def shutdown(self) -> None:
        """
        关闭调度器
        
        释放分布式锁，清理资源
        """
        if self.redis and self.is_master:
            await self.redis.r.delete(self._lock_key)
            log.info("[CeleryScheduler] 释放分布式锁")
        
        self._initialized = False
        self.is_master = False
        log.info("[CeleryScheduler] 调度器已关闭")

    def _get_task_path(self, task_func: Callable) -> str:
        """
        获取任务函数的路径
        
        Args:
            task_func: 任务函数
        
        Returns:
            str: 任务路径
        """
        if hasattr(task_func, "name"):
            return task_func.name
        
        module = getattr(task_func, "__module__", "")
        name = getattr(task_func, "__name__", "")
        
        if module and name:
            return f"{module}.{name}"
        
        return str(task_func)

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    @property
    def job_count(self) -> int:
        """当前任务数量"""
        return len(get_beat_schedule())


celeryHubScheduler = CeleryHubScheduler()
