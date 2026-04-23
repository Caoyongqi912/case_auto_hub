#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Redis Worker Pool 包

提供基于 Redis 的分布式任务队列功能。

Modules:
    models: 任务数据模型（Job, JobStatus）
    connection: Redis 连接管理
    queue: 任务队列操作
    executor: 任务执行器
    monitor: 监控统计
    pool: 工作池主类
    tasks: 任务函数注册

Usage:
    from common.worker_pool import r_pool, RedisWorkerPool
    from common.worker_pool.models import Job, JobStatus
    
    # 获取单例实例
    pool = RedisWorkerPool.get_instance()
    
    # 启动工作池
    await pool.start()
    
    # 提交任务
    await pool.submit_to_redis(func, job_id, "task_name")
"""

from common.worker_pool.models import Job, JobStatus, JOB
from common.worker_pool.pool import RedisWorkerPool
from common.worker_pool.tasks import (
    r_pool,
    register_interface_task_RoBot,
    register_interface_task_Handle,
    register_play_task_robot,
    register_play_task_handle,
)

__all__ = [
    "r_pool",
    "RedisWorkerPool",
    "Job",
    "JobStatus",
    "JOB",
    "register_interface_task_RoBot",
    "register_interface_task_Handle",
    "register_play_task_robot",
    "register_play_task_handle",
]
