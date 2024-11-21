#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : __init__.py# @Software: PyCharm# @Desc:from apscheduler.schedulers.asyncio import AsyncIOSchedulerfrom apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStorefrom app.model.ui import UITaskModelfrom ._trigger import Triggerfrom config import Configfrom play import Playerfrom utils import logclass Scheduler:    scheduler: AsyncIOScheduler = None    @staticmethod    async def init(scheduler):        Scheduler.scheduler = scheduler    @staticmethod    def shutdown():        if Scheduler.scheduler:            Scheduler.scheduler.shutdown()    @staticmethod    def start():        job_store = {            'default': SQLAlchemyJobStore(url=Config.SQLALCHEMY_DATABASE_URI,                                          engine_options={"pool_recycle": 1500},                                          pickle_protocol=3)        }        Scheduler.scheduler.configure(jobstores=job_store)        Scheduler.scheduler.start()        log.info("Scheduler START")    @staticmethod    def addTaskJob(task: UITaskModel):        """        :param task:        :return:        """        log.info(f"add UI Task {task}")        return Scheduler.scheduler.add_job(            func=Player().run_task,            name=task.title,            id=task.uid,            trigger=Trigger(task.cron),            replace_existing=True,            args=(task.id,)        )    @staticmethod    def editTaskJob(task: UITaskModel):        """        更新JOB        :param task:        :return:        """        job = Scheduler.jobInfo(task.uid)        if job is None:  # 证明TASK 未创建JOB            return Scheduler.addTaskJob(task)        else:            Scheduler.scheduler.modify_job(job_id=task.uid,                                           name=task.title,                                           trigger=Trigger(task.cron))            Scheduler.scheduler.pause_job(task.uid)            Scheduler.scheduler.resume_job(task.uid)    @staticmethod    def pause(taskId: str):        """        暂停任务        :param taskId:        :return:        """        log.info(f"pause UI Task {taskId}")        Scheduler.scheduler.pause_job(taskId)    @staticmethod    def removeTaskJob(jobId: str):        job = Scheduler.jobInfo(jobId)        if job:            log.info(f"remove UI Task {jobId}")            Scheduler.scheduler.remove_job(job_id=jobId)        else:            log.info(f"remove UI Task {jobId} not found")    @staticmethod    def jobInfo(jobId: str):        job = Scheduler.scheduler.get_job(job_id=jobId)        log.info(f"jobInfo UI Task {job}")        return job    @staticmethod    def job_next_run_time(jobId: str):        job = Scheduler.scheduler.get_job(job_id=jobId)        if job is None:            return "请先配置定时任务"        log.debug(f"next_run_time {job.next_run_time}")        t = job.next_run_time        if t:            return job.next_run_time        else:            return "请先启动任务"    @staticmethod    def set_switch(jobId: str, switch: bool):        job = Scheduler.scheduler.get_job(job_id=jobId)        if job:            if switch:                job.resume()            else:                job.pause()        return