#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
任务函数注册模块

定义并注册所有可执行的任务函数。
"""
from app.model.base import User
from common.worker_pool.pool import RedisWorkerPool
from config import Config
from croe.interface.starter import APIStarter
from croe.interface.task import TaskRunner, TaskParams
from croe.play.starter import UIStarter
from croe.play.task_runner import PlayTaskRunner, PlayTaskExecuteParams
from enums import StarterEnum
from utils import MyLoguru

log = MyLoguru().get_logger()

r_pool = RedisWorkerPool.get_instance()


@r_pool.register_function
async def register_interface_task_RoBot(**kwargs):
    """
    接口任务注册执行（定时执行）
    
    由 APScheduler 定时触发，执行接口自动化测试任务。
    
    Args:
        **kwargs: 任务参数，包含测试配置等信息
    """
    try:
        runner = TaskRunner(APIStarter(StarterEnum.RoBot))
        await runner.execute_task(params=TaskParams(**kwargs))
    except Exception as e:
        log.error(f"register_interface_task_RoBot 执行失败: {e}")


@r_pool.register_function
async def register_interface_task_Handle(user: User, **kwargs):
    """
    接口任务注册执行（手动触发）
    
    由用户通过接口手动触发，执行接口自动化测试任务。
    
    Args:
        user: 当前用户对象
        **kwargs: 任务参数
    """
    try:
        runner = TaskRunner(APIStarter(user))
        await runner.execute_task(params=TaskParams(**kwargs))
    except Exception as e:
        log.error(f"register_interface_task_Handle 执行失败: {e}")


@r_pool.register_function
async def register_play_task_handle(user: User, **kwargs):
    """
    UI 自动化任务注册执行（手动触发）
    
    由用户通过接口手动触发，执行 UI 自动化测试任务。
    
    Args:
        user: 当前用户对象
        **kwargs: 任务参数
    """
    try:
        runner = PlayTaskRunner(UIStarter(user))
        await runner.execute_task(params=PlayTaskExecuteParams(**kwargs))
    except Exception as e:
        log.error(f"register_play_task_handle 执行失败: {e}")


@r_pool.register_function
async def register_play_task_robot(**kwargs):
    """
    UI 自动化任务注册执行（定时执行）
    
    由 APScheduler 定时触发，执行 UI 自动化测试任务。
    
    Args:
        **kwargs: 任务参数
    """
    try:
        runner = PlayTaskRunner(UIStarter(StarterEnum.RoBot))
        await runner.execute_task(params=PlayTaskExecuteParams(**kwargs))
    except Exception as e:
        log.error(f"register_play_task_robot 执行失败: {e}")


__all__ = [
    "r_pool",
    "register_interface_task_RoBot",
    "register_interface_task_Handle",
    "register_play_task_robot",
    "register_play_task_handle",
]
