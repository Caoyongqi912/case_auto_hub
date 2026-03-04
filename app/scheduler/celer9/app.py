#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/3/4
# @Author : cyq
# @File : app
# @Software: PyCharm
# @Desc: Celery 应用配置模块
from typing import Dict, Any, Optional, List
from celery import Celery
from celery.schedules import crontab, schedule
from config import Config
from utils import MyLoguru

log = MyLoguru().get_logger()

celery_app = Celery(
    "hub_celery_scheduler",
    include=[
        "app.scheduler.celer9.tasks",
    ]
)

celery_app.conf.update(
    broker_url=Config.REDIS_Broker,
    result_backend=Config.REDIS_Backend,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    beat_schedule={},
    task_default_queue="default",
    task_queues={
        "default": {
            "exchange": "default",
            "routing_key": "default",
        },
        "interface_tasks": {
            "exchange": "interface_tasks",
            "routing_key": "interface_tasks",
        },
        "play_tasks": {
            "exchange": "play_tasks",
            "routing_key": "play_tasks",
        },
    },
)


class CeleryScheduleBuilder:
    """
    Celery 定时任务调度配置构建器
    
    提供与 APScheduler 一致的调度配置能力，支持：
    - CRON 表达式定时任务
    - 固定间隔定时任务
    - 单次执行任务
    """
    
    @staticmethod
    def build_cron_schedule(cron_expression: str) -> crontab:
        """
        构建 CRON 调度
        
        Args:
            cron_expression: CRON 表达式，格式为 "分 时 日 月 周"
                            例如: "0 12 * * *" 表示每天12点执行
        
        Returns:
            crontab: Celery crontab 对象
        
        Raises:
            ValueError: CRON 表达式格式错误时抛出
        """
        try:
            fields = cron_expression.strip().split()
            if len(fields) != 5:
                raise ValueError("CRON 表达式必须包含5个字段（分 时 日 月 周）")
            return crontab(
                minute=fields[0],
                hour=fields[1],
                day_of_month=fields[2],
                month_of_year=fields[3],
                day_of_week=fields[4],
            )
        except Exception as e:
            log.error(f"解析 CRON 表达式失败: {cron_expression}, 错误: {e}")
            raise ValueError(f"无效的 CRON 表达式: {cron_expression}") from e

    @staticmethod
    def build_interval_schedule(
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        days: Optional[int] = None,
    ) -> schedule:
        """
        构建固定间隔调度
        
        Args:
            seconds: 间隔秒数
            minutes: 间隔分钟数
            hours: 间隔小时数
            days: 间隔天数
        
        Returns:
            schedule: Celery schedule 对象
        """
        total_seconds = 0
        if seconds:
            total_seconds += seconds
        if minutes:
            total_seconds += minutes * 60
        if hours:
            total_seconds += hours * 3600
        if days:
            total_seconds += days * 86400
        
        if total_seconds <= 0:
            raise ValueError("间隔时间必须大于0")
        
        return schedule(run_every=total_seconds)

    @staticmethod
    def build_beat_schedule_entry(
        task_name: str,
        task_path: str,
        schedule_config: Any,
        args: Optional[tuple] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        queue: str = "default",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        构建 beat schedule 条目
        
        Args:
            task_name: 任务名称（唯一标识）
            task_path: 任务路径
            schedule_config: 调度配置（crontab 或 schedule 对象）
            args: 位置参数
            kwargs: 关键字参数
            queue: 任务队列
            options: 额外选项
        
        Returns:
            Dict[str, Any]: beat schedule 条目配置
        """
        entry = {
            "task": task_path,
            "schedule": schedule_config,
            "options": {"queue": queue},
        }
        
        if args:
            entry["args"] = args
        if kwargs:
            entry["kwargs"] = kwargs
        if options:
            entry["options"].update(options)
        
        return entry


def get_celery_app() -> Celery:
    """
    获取 Celery 应用实例
    
    Returns:
        Celery: Celery 应用实例
    """
    return celery_app


def update_beat_schedule(schedule_dict: Dict[str, Any]) -> None:
    """
    更新 beat schedule 配置
    
    Args:
        schedule_dict: 新的调度配置字典
    """
    celery_app.conf.beat_schedule.update(schedule_dict)
    log.info(f"[CeleryScheduler] 更新调度配置: {len(schedule_dict)} 个任务")


def replace_beat_schedule(schedule_dict: Dict[str, Any]) -> None:
    """
    替换 beat schedule 配置
    
    Args:
        schedule_dict: 新的调度配置字典
    """
    celery_app.conf.beat_schedule = schedule_dict
    log.info(f"[CeleryScheduler] 替换调度配置: {len(schedule_dict)} 个任务")


def remove_beat_schedule(task_name: str) -> bool:
    """
    移除指定的 beat schedule 任务
    
    Args:
        task_name: 任务名称
    
    Returns:
        bool: 是否成功移除
    """
    if task_name in celery_app.conf.beat_schedule:
        del celery_app.conf.beat_schedule[task_name]
        log.info(f"[CeleryScheduler] 移除任务: {task_name}")
        return True
    log.warning(f"[CeleryScheduler] 任务不存在: {task_name}")
    return False


def get_beat_schedule() -> Dict[str, Any]:
    """
    获取当前 beat schedule 配置
    
    Returns:
        Dict[str, Any]: 当前调度配置
    """
    return celery_app.conf.beat_schedule


def get_schedule_count() -> Dict[str, int]:
    """
    获取调度任务统计
    
    Returns:
        Dict[str, int]: 包含总数和分类统计
    """
    schedules = celery_app.conf.beat_schedule
    interface_tasks = len([k for k in schedules.keys() if "interface" in k.lower()])
    play_tasks = len([k for k in schedules.keys() if "play" in k.lower()])
    
    return {
        "total": len(schedules),
        "interface_tasks": interface_tasks,
        "play_tasks": play_tasks,
    }
