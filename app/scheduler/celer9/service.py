#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/3/4
# @Author : cyq
# @File : service
# @Software: PyCharm
# @Desc: Celery 调度服务层封装
import asyncio
from typing import Dict, Any, List, Optional

from app.model.base.job import AutoJob
from app.scheduler.celer9.app import (
    get_celery_app,
    get_beat_schedule,
    get_schedule_count,
    update_beat_schedule,
    replace_beat_schedule,
    remove_beat_schedule,
    CeleryScheduleBuilder,
)
from app.scheduler.celer9.trigger import (
    CeleryTrigger,
    create_trigger,
    create_cron_trigger,
    create_interval_trigger,
    create_once_trigger,
)
from app.scheduler.celer9.scheduler import celeryHubScheduler, CeleryHubScheduler
from utils import MyLoguru

log = MyLoguru().get_logger()


class CeleryScheduleService:
    """
    Celery 定时任务管理服务
    
    提供统一的任务管理接口，封装底层调度器操作。
    支持同步和异步两种调用方式。
    """
    
    @staticmethod
    async def initialize(redis_client) -> bool:
        """
        初始化调度服务
        
        Args:
            redis_client: Redis 客户端实例
        
        Returns:
            bool: 是否成功成为主节点
        """
        return await celeryHubScheduler.initialize(redis_client)
    
    @staticmethod
    async def shutdown() -> None:
        """关闭调度服务"""
        await celeryHubScheduler.shutdown()
    
    @staticmethod
    def is_master() -> bool:
        """
        检查当前节点是否为主节点
        
        Returns:
            bool: 是否为主节点
        """
        return celeryHubScheduler.is_master
    
    @staticmethod
    def is_initialized() -> bool:
        """
        检查调度器是否已初始化
        
        Returns:
            bool: 是否已初始化
        """
        return celeryHubScheduler.is_initialized

    @staticmethod
    async def add_auto_job(job: AutoJob) -> bool:
        """
        添加自动化任务
        
        Args:
            job: AutoJob 模型实例
        
        Returns:
            bool: 是否添加成功
        """
        return await celeryHubScheduler.add_auto_job(job)

    @staticmethod
    async def remove_job(job_id: str) -> bool:
        """
        移除任务
        
        Args:
            job_id: 任务唯一标识
        
        Returns:
            bool: 是否移除成功
        """
        return await celeryHubScheduler.remove_job(job_id)

    @staticmethod
    async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            job_id: 任务唯一标识
        
        Returns:
            Optional[Dict[str, Any]]: 任务信息
        """
        return await celeryHubScheduler.get_job(job_id)

    @staticmethod
    async def get_all_jobs() -> List[Dict[str, Any]]:
        """
        获取所有任务
        
        Returns:
            List[Dict[str, Any]]: 任务列表
        """
        return await celeryHubScheduler.get_jobs()

    @staticmethod
    async def enable_job(job_id: str) -> bool:
        """
        启用任务
        
        Args:
            job_id: 任务唯一标识
        
        Returns:
            bool: 是否操作成功
        """
        return await celeryHubScheduler.switch_job(job_id, True)

    @staticmethod
    async def disable_job(job_id: str) -> bool:
        """
        禁用任务
        
        Args:
            job_id: 任务唯一标识
        
        Returns:
            bool: 是否操作成功
        """
        return await celeryHubScheduler.switch_job(job_id, False)

    @staticmethod
    async def modify_job(job: AutoJob) -> bool:
        """
        修改任务配置
        
        Args:
            job: AutoJob 模型实例
        
        Returns:
            bool: 是否修改成功
        """
        return await celeryHubScheduler.modify(job)

    @staticmethod
    def get_current_schedules() -> Dict[str, Any]:
        """
        获取当前调度配置
        
        Returns:
            Dict[str, Any]: 调度配置字典
        """
        return get_beat_schedule()

    @staticmethod
    def get_schedule_statistics() -> Dict[str, int]:
        """
        获取调度统计信息
        
        Returns:
            Dict[str, int]: 统计信息
        """
        return get_schedule_count()

    @staticmethod
    def get_job_count() -> int:
        """
        获取任务数量
        
        Returns:
            int: 任务数量
        """
        return celeryHubScheduler.job_count


class CeleryTriggerService:
    """
    触发器服务
    
    提供触发器创建和管理的便捷方法
    """
    
    @staticmethod
    def create_cron(cron_expression: str) -> CeleryTrigger:
        """
        创建 CRON 触发器
        
        Args:
            cron_expression: CRON 表达式
        
        Returns:
            CeleryTrigger: 触发器实例
        """
        return create_cron_trigger(cron_expression)
    
    @staticmethod
    def create_interval(
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        days: Optional[int] = None,
        weeks: Optional[int] = None,
    ) -> CeleryTrigger:
        """
        创建固定间隔触发器
        
        Args:
            seconds: 秒
            minutes: 分钟
            hours: 小时
            days: 天
            weeks: 周
        
        Returns:
            CeleryTrigger: 触发器实例
        """
        return create_interval_trigger(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            days=days,
            weeks=weeks,
        )
    
    @staticmethod
    def create_once(run_date) -> CeleryTrigger:
        """
        创建单次执行触发器
        
        Args:
            run_date: 执行时间
        
        Returns:
            CeleryTrigger: 触发器实例
        """
        return create_once_trigger(run_date)


class CeleryBeatService:
    """
    Celery Beat 调度配置服务
    
    直接操作 Celery Beat 调度配置
    """
    
    @staticmethod
    def update_schedule(schedule_dict: Dict[str, Any]) -> None:
        """
        更新调度配置（增量）
        
        Args:
            schedule_dict: 调度配置字典
        """
        update_beat_schedule(schedule_dict)
    
    @staticmethod
    def replace_schedule(schedule_dict: Dict[str, Any]) -> None:
        """
        替换调度配置（全量）
        
        Args:
            schedule_dict: 调度配置字典
        """
        replace_beat_schedule(schedule_dict)
    
    @staticmethod
    def remove_schedule_entry(task_name: str) -> bool:
        """
        移除调度条目
        
        Args:
            task_name: 任务名称
        
        Returns:
            bool: 是否移除成功
        """
        return remove_beat_schedule(task_name)
    
    @staticmethod
    def build_cron_schedule(cron_expression: str):
        """
        构建 CRON 调度
        
        Args:
            cron_expression: CRON 表达式
        
        Returns:
            crontab: CRON 调度对象
        """
        return CeleryScheduleBuilder.build_cron_schedule(cron_expression)
    
    @staticmethod
    def build_interval_schedule(
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        days: Optional[int] = None,
    ):
        """
        构建间隔调度
        
        Args:
            seconds: 秒
            minutes: 分钟
            hours: 小时
            days: 天
        
        Returns:
            schedule: 间隔调度对象
        """
        return CeleryScheduleBuilder.build_interval_schedule(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            days=days,
        )


class CeleryTaskResultService:
    """
    Celery 任务结果查询服务
    """
    
    @staticmethod
    def get_task_result(task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务执行结果
        
        Args:
            task_id: Celery 任务 ID
        
        Returns:
            Optional[Dict[str, Any]]: 任务结果
        """
        app = get_celery_app()
        result = app.AsyncResult(task_id)
        
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None,
        }
    
    @staticmethod
    def get_task_status(task_id: str) -> str:
        """
        获取任务状态
        
        Args:
            task_id: Celery 任务 ID
        
        Returns:
            str: 任务状态
        """
        app = get_celery_app()
        result = app.AsyncResult(task_id)
        return result.status
    
    @staticmethod
    def revoke_task(task_id: str, terminate: bool = False) -> bool:
        """
        撤销任务
        
        Args:
            task_id: Celery 任务 ID
            terminate: 是否终止正在执行的任务
        
        Returns:
            bool: 是否撤销成功
        """
        app = get_celery_app()
        app.control.revoke(task_id, terminate=terminate)
        log.info(f"[CeleryService] 撤销任务: {task_id}, terminate={terminate}")
        return True


def get_scheduler() -> CeleryHubScheduler:
    """
    获取调度器实例
    
    Returns:
        CeleryHubScheduler: 调度器实例
    """
    return celeryHubScheduler


async def init_celery_scheduler(redis_client) -> bool:
    """
    初始化 Celery 调度器的便捷函数
    
    Args:
        redis_client: Redis 客户端实例
    
    Returns:
        bool: 是否成功成为主节点
    """
    return await CeleryScheduleService.initialize(redis_client)


async def shutdown_celery_scheduler() -> None:
    """关闭 Celery 调度器的便捷函数"""
    await CeleryScheduleService.shutdown()
