#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/3/4
# @Author : cyq
# @File : tasks
# @Software: PyCharm
# @Desc: Celery 任务定义模块
import asyncio
import time
from typing import Dict, Any, Optional

from celery import shared_task
from celery.app.task import Task

from app.model.base.job import AutoJob
from app.scheduler.celer9.app import celery_app
from utils import MyLoguru

log = MyLoguru().get_logger()


@celery_app.task(name="celery_submit_interface_task", bind=True, max_retries=3)
def celery_submit_interface_task(self: Task, job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    提交接口测试任务
    
    与 APScheduler 的 aps_submit_interface_task 功能一致，
    将任务提交到 Redis 任务池执行。
    
    Args:
        self: Celery Task 实例
        job_data: 任务数据字典，包含：
            - uid: 任务唯一标识
            - job_name: 任务名称
            - job_task_id_list: 任务ID列表
            - job_env_id: 环境ID
            - job_max_retry_count: 最大重试次数
            - job_retry_interval: 重试间隔
            - notify_id: 通知ID
            - job_kwargs: 额外参数
    
    Returns:
        Dict[str, Any]: 执行结果
    """
    async def _execute():
        from common.worker_pool import r_pool, register_interface_task_RoBot
        
        if not r_pool.is_running:
            raise RuntimeError("任务池未启动")
        
        task_id_list = job_data.get("job_task_id_list", [])
        job_name = job_data.get("job_name", "未命名任务")
        
        log.info(f"[CeleryTask] 开始执行接口任务: {job_name}, 任务数: {len(task_id_list)}")
        
        results = []
        for task_id in task_id_list:
            try:
                await r_pool.submit_to_redis(
                    func=register_interface_task_RoBot,
                    job_id=str(task_id),
                    job_name=job_name,
                    job_kwargs={
                        "task_id": task_id,
                        "env_id": job_data.get("job_env_id"),
                        "retry": job_data.get("job_max_retry_count", 0),
                        "retry_interval": job_data.get("job_retry_interval", 0),
                        "notify_id": job_data.get("notify_id"),
                        "variables": job_data.get("job_kwargs", {}),
                    }
                )
                results.append({"task_id": task_id, "status": "submitted"})
            except Exception as e:
                log.error(f"[CeleryTask] 提交接口任务失败: {task_id}, 错误: {e}")
                results.append({"task_id": task_id, "status": "failed", "error": str(e)})
        
        return {"job_name": job_name, "results": results}
    
    try:
        self.update_state(state="PROGRESS", meta={"status": "任务开始", "job_name": job_data.get("job_name")})
        result = asyncio.run(_execute())
        self.update_state(state="SUCCESS", meta={"status": "任务完成", "result": result})
        log.info(f"[CeleryTask] 接口任务执行完成: {job_data.get('job_name')}")
        return result
    except Exception as e:
        log.error(f"[CeleryTask] 接口任务执行失败: {job_data.get('job_name')}, 错误: {e}")
        self.update_state(
            state="FAILURE",
            meta={"error": str(e), "job_name": job_data.get("job_name")}
        )
        raise


@celery_app.task(name="celery_submit_play_task", bind=True, max_retries=3)
def celery_submit_play_task(self: Task, job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    提交 UI 自动化测试任务
    
    与 APScheduler 的 aps_submit_play_task 功能一致，
    将任务提交到 Redis 任务池执行。
    
    Args:
        self: Celery Task 实例
        job_data: 任务数据字典，包含：
            - uid: 任务唯一标识
            - job_name: 任务名称
            - job_task_id_list: 任务ID列表
            - job_max_retry_count: 最大重试次数
            - job_retry_interval: 重试间隔
            - notify_id: 通知ID
            - job_kwargs: 额外参数
    
    Returns:
        Dict[str, Any]: 执行结果
    """
    async def _execute():
        from common.worker_pool import r_pool, register_play_task_robot
        
        if not r_pool.is_running:
            raise RuntimeError("任务池未启动")
        
        task_id_list = job_data.get("job_task_id_list", [])
        job_name = job_data.get("job_name", "未命名任务")
        
        log.info(f"[CeleryTask] 开始执行UI任务: {job_name}, 任务数: {len(task_id_list)}")
        
        results = []
        for task_id in task_id_list:
            try:
                unique_job_id = f"{task_id}_{int(time.time() * 1000000)}"
                await r_pool.submit_to_redis(
                    func=register_play_task_robot,
                    job_id=unique_job_id,
                    job_name=job_name,
                    job_kwargs={
                        "task_id": task_id,
                        "retry": job_data.get("job_max_retry_count", 0),
                        "retry_interval": job_data.get("job_retry_interval", 0),
                        "notify_id": job_data.get("notify_id"),
                        "variables": job_data.get("job_kwargs", {}),
                    }
                )
                results.append({"task_id": task_id, "status": "submitted"})
            except Exception as e:
                log.error(f"[CeleryTask] 提交UI任务失败: {task_id}, 错误: {e}")
                results.append({"task_id": task_id, "status": "failed", "error": str(e)})
        
        return {"job_name": job_name, "results": results}
    
    try:
        self.update_state(state="PROGRESS", meta={"status": "任务开始", "job_name": job_data.get("job_name")})
        result = asyncio.run(_execute())
        self.update_state(state="SUCCESS", meta={"status": "任务完成", "result": result})
        log.info(f"[CeleryTask] UI任务执行完成: {job_data.get('job_name')}")
        return result
    except Exception as e:
        log.error(f"[CeleryTask] UI任务执行失败: {job_data.get('job_name')}, 错误: {e}")
        self.update_state(
            state="FAILURE",
            meta={"error": str(e), "job_name": job_data.get("job_name")}
        )
        raise


@celery_app.task(name="celery_heartbeat", bind=True)
def celery_heartbeat(self: Task) -> Dict[str, Any]:
    """
    Celery 心跳任务
    
    与 APScheduler 的 aps_heartbeat 功能一致，
    用于续期分布式锁，确保调度器主节点状态。
    
    Args:
        self: Celery Task 实例
    
    Returns:
        Dict[str, Any]: 心跳结果
    """
    async def _execute():
        from common import rc
        key = "scheduler:master_lock"
        await rc.init_pool()
        if await rc.r.get(key):
            await rc.r.expire(key, 60)
            log.info("[CeleryScheduler] ✅ 续期锁成功")
            return {"status": "renewed", "key": key}
        log.warning("[CeleryScheduler] ⚠️ 锁不存在")
        return {"status": "not_found", "key": key}
    
    try:
        return asyncio.run(_execute())
    except Exception as e:
        log.error(f"[CeleryScheduler] 心跳任务失败: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="celery_print_jobs", bind=True)
def celery_print_jobs(self: Task) -> Dict[str, Any]:
    """
    打印当前所有调度任务
    
    与 APScheduler 的 print_jobs 功能一致，
    用于调试和监控调度任务状态。
    
    Args:
        self: Celery Task 实例
    
    Returns:
        Dict[str, Any]: 任务列表信息
    """
    from app.scheduler.celer9.app import get_beat_schedule
    
    schedules = get_beat_schedule()
    job_list = []
    
    for name, config in schedules.items():
        job_info = {
            "name": name,
            "task": config.get("task"),
            "schedule": str(config.get("schedule")),
        }
        job_list.append(job_info)
        log.info(f"[CeleryScheduler] JOB: {name} -> {config.get('task')}")
    
    log.info(f"[CeleryScheduler] 当前共有 {len(job_list)} 个调度任务")
    return {"total": len(job_list), "jobs": job_list}


@shared_task(name="celery_custom_task", bind=True, max_retries=3)
def celery_custom_task(
    self: Task,
    task_path: str,
    args: Optional[tuple] = None,
    kwargs: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    通用自定义任务执行器
    
    用于执行动态注册的自定义任务函数。
    
    Args:
        self: Celery Task 实例
        task_path: 任务函数路径，格式为 "module.function"
        args: 位置参数
        kwargs: 关键字参数
    
    Returns:
        Any: 任务执行结果
    """
    async def _execute():
        import importlib
        
        module_path, func_name = task_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        
        if asyncio.iscoroutinefunction(func):
            return await func(*(args or ()), **(kwargs or {}))
        else:
            return func(*(args or ()), **(kwargs or {}))
    
    try:
        self.update_state(state="PROGRESS", meta={"status": "执行中", "task": task_path})
        result = asyncio.run(_execute())
        self.update_state(state="SUCCESS", meta={"status": "完成"})
        return result
    except Exception as e:
        log.error(f"[CeleryTask] 自定义任务执行失败: {task_path}, 错误: {e}")
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


def auto_job_to_dict(job: AutoJob) -> Dict[str, Any]:
    """
    将 AutoJob 模型转换为字典
    
    Args:
        job: AutoJob 模型实例
    
    Returns:
        Dict[str, Any]: 任务数据字典
    """
    return {
        "uid": job.uid,
        "job_name": job.job_name,
        "job_type": job.job_type,
        "job_task_id_list": job.job_task_id_list or [],
        "job_enabled": job.job_enabled,
        "job_trigger_type": job.job_trigger_type,
        "job_env_id": job.job_env_id,
        "job_env_name": job.job_env_name,
        "job_execute_strategy": job.job_execute_strategy,
        "job_execute_time": job.job_execute_time,
        "job_execute_cron": job.job_execute_cron,
        "job_execute_interval": job.job_execute_interval,
        "job_execute_interval_unit": job.job_execute_interval_unit,
        "job_max_retry_count": job.job_max_retry_count,
        "job_retry_interval": job.job_retry_interval,
        "job_kwargs": job.job_kwargs or {},
        "job_notify_type": job.job_notify_type,
        "job_notify_on": job.job_notify_on,
        "notify_id": job.notify_id,
    }
