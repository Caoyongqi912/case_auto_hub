#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/3/4
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: Celery 调度模块初始化

from app.scheduler.celer9.app import (
    celery_app,
    get_celery_app,
    update_beat_schedule,
    replace_beat_schedule,
    remove_beat_schedule,
    get_beat_schedule,
    get_schedule_count,
    CeleryScheduleBuilder,
)

from app.scheduler.celer9.trigger import (
    CeleryTrigger,
    TriggerModel,
    create_trigger,
    create_cron_trigger,
    create_interval_trigger,
    create_once_trigger,
)

from app.scheduler.celer9.tasks import (
    celery_submit_interface_task,
    celery_submit_play_task,
    celery_heartbeat,
    celery_print_jobs,
    celery_custom_task,
    auto_job_to_dict,
)

from app.scheduler.celer9.scheduler import (
    CeleryHubScheduler,
    celeryHubScheduler,
    run_sync,
)

from app.scheduler.celer9.service import (
    CeleryScheduleService,
    CeleryTriggerService,
    CeleryBeatService,
    CeleryTaskResultService,
    get_scheduler,
    init_celery_scheduler,
    shutdown_celery_scheduler,
)

__all__ = [
    "celery_app",
    "get_celery_app",
    "update_beat_schedule",
    "replace_beat_schedule",
    "remove_beat_schedule",
    "get_beat_schedule",
    "get_schedule_count",
    "CeleryScheduleBuilder",
    "CeleryTrigger",
    "TriggerModel",
    "create_trigger",
    "create_cron_trigger",
    "create_interval_trigger",
    "create_once_trigger",
    "celery_submit_interface_task",
    "celery_submit_play_task",
    "celery_heartbeat",
    "celery_print_jobs",
    "celery_custom_task",
    "auto_job_to_dict",
    "CeleryHubScheduler",
    "celeryHubScheduler",
    "run_sync",
    "CeleryScheduleService",
    "CeleryTriggerService",
    "CeleryBeatService",
    "CeleryTaskResultService",
    "get_scheduler",
    "init_celery_scheduler",
    "shutdown_celery_scheduler",
]
