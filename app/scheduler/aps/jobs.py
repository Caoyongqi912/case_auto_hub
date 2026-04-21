#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/12/11
# @Author : cyq
# @File : aps_jobs
# @Software: PyCharm
# @Desc: APS 定时任务

from app.model.base.job import AutoJob
from utils import log
import time
from common.worker_pool import r_pool, register_interface_task_RoBot, register_play_task_robot
from common import rc


async def aps_submit_interface_task(job: AutoJob):
    """
    调度任务执行
    :param job: AutoJob 任务
    """
    if not r_pool.is_running:
        raise RuntimeError("任务池未启动")
    ## 添加到多个任务
    ##
    log.debug(f"aps_submit_interface_task {job}")
    for task_id in job.job_task_id_list:
        await r_pool.submit_to_redis(
            func=register_interface_task_RoBot,
            job_id=task_id,
            job_name=job.job_name,
            job_kwargs={
                "task_id": task_id,
                "env_id": job.job_env_id,
                "retry": job.job_max_retry_count,
                "retry_interval": job.job_retry_interval,
                "notify_id": job.notify_id,
                "variables": job.job_kwargs
            }
        )


async def aps_submit_play_task(job: AutoJob):
    """
    调度任务执行
    :param job: AutoJob 任务
    """
    if not r_pool.is_running:
        raise RuntimeError("任务池未启动")
    ## 添加到多个任务
    ##
    for task_id in job.job_task_id_list:
        unique_job_id = f"{task_id}_{int(time.time() * 1000000)}"  # 添加时间戳后缀

        await r_pool.submit_to_redis(
            func=register_play_task_robot,
            job_id=unique_job_id,
            job_name=job.job_name,
            job_kwargs={
                "task_id": task_id,
                "retry": job.job_max_retry_count,
                "retry_interval": job.job_retry_interval,
                "notify_id": job.notify_id,
                "variables": job.job_kwargs
            }
        )


async def aps_heartbeat():
    """
    可序列化的心跳任务函数
    """
    from common import rc
    Key = "scheduler:master_lock"
    await rc.init_pool()
    if await rc.r.get(Key):
        await rc.r.expire(Key, 60)
        log.info("[Scheduler] : ✅ Renewed lock")


async def print_jobs():
    """
    打印JOB
    """
    import pickle
    from config import Config

    try:
        jobs_key = Config.APSJobStores['default'].jobs_key
        await rc.init_pool()

        job_ids = await rc.r.hkeys(jobs_key)
        for job_id in job_ids:
            job_id_str = job_id.decode() if isinstance(job_id, bytes) else job_id
            job_data = await rc.r.hget(jobs_key, job_id_str)
            if job_data:
                try:
                    job_info = pickle.loads(job_data)
                    log.info(f"[Scheduler]: JOB {job_id_str} -> next run: {job_info.get('next_run_time', 'N/A')}")
                except Exception:
                    log.info(f"[Scheduler]: JOB {job_id_str}")

        log.info(f"[Scheduler]: 共有 {len(job_ids)} 个调度任务")
    except Exception as e:
        log.error(f"[Scheduler]: 打印任务失败: {e}")
