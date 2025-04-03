#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/2/27# @Author : cyq# @File : locustClient# @Software: PyCharmfrom dotenv import load_dotenvfrom locust.util.rounding import proper_roundimport anyiofrom utils.locustUser import DynamicApiUserfrom interface.starter import APIStarterfrom utils import log, GenerateToolsload_dotenv()from locust.runners import Runner, LocalRunnerimport geventfrom locust import eventsfrom locust.env import Environmentfrom locust.log import setup_loggingsetup_logging("DEBUG", None)class LocustClient:    def __init__(self):        self._runner = {}    def start_locust(self, taskId: str, domain: str, method: str, url: str, request_info: dict, users: int,                     spawn_rate: int,                     duration: float, io=None):        """        启动Locust性能测试。        参数说明：        - taskId (str): 任务唯一标识符。        - domain (str): 目标服务的域名或IP地址。        - method (str): HTTP请求方法（如GET、POST等）。        - url (str): 请求的URL路径。        - request_info (dict): 包含请求相关信息的字典，例如headers、params等。        - users (int): 模拟的并发用户数。        - spawn_rate (int): 每秒启动的用户数（即用户生成速率）。        - duration (float): 测试持续时间，单位为秒。        """        # 初始化DynamicApiUser类，并设置其属性值        DA = DynamicApiUser        DA.api_info = request_info  # 设置请求信息        DA.method = method  # 设置HTTP方法        DA.url = url  # 设置请求URL        # 创建Locust运行环境        env = Environment(user_classes=[DA], events=events, host=domain)        runner = env.create_local_runner()  # 创建本地运行器        self._runner[taskId] = runner  # 保存runner实例        # web_ui = env.create_web_ui("127.0.0.1", 8089)        # env.events.init.fire(environment=env, runner=runner, web_ui=web_ui)  # 触发初始化事件        env.events.init.fire(environment=env, runner=runner)  # 触发初始化事件        # 启动一个协程用于记录统计数据        gevent.spawn(_my_stats_history, env.runner, io)        # 开始性能测试        runner.start(users, spawn_rate=spawn_rate)        # 在指定的duration秒后停止测试        gevent.spawn_later(duration, runner.quit)        # 等待所有协程完成        runner.greenlet.join()        # 获取历史统计数据        history = runner.stats.history        log.debug(f"user:{runner.user_count}")        log.debug(f"请求数量：{runner.stats.num_requests}")        log.debug(f"失败数量：{runner.stats.num_failures}")        log.debug(f"请求total_response_time：{runner.stats.total.avg_response_time}")        log.debug(f"请求max_response_time：{runner.stats.total.max_response_time}")        log.debug(f"请求min_response_time：{runner.stats.total.min_response_time}")        log.debug(f"请求avg_response_time：{runner.stats.total.avg_response_time}")        log.debug(f"请求total_rps：{runner.stats.total.total_rps}")        data = anyio.run(push_data, runner, io)    def stop(self, taskId: str, io: APIStarter):        runner: LocalRunner = self._runner.get(taskId)        if runner:            anyio.run(push_data, runner, io)            runner.quit()    @property    def users(self):        return self._runnerdef _my_stats_history(runner: Runner, io: APIStarter) -> None:    """Save current stats info to history for charts of report."""    while True:        if not runner.stats.total.use_response_times_cache:            break        if runner.state != "ready" and runner.state != "stopped":            _my_update_stats_history(runner, io)        gevent.sleep(3)def _my_update_stats_history(runner: Runner, io: APIStarter) -> None:    stats = runner.stats    timestamp = GenerateTools.getTime(4)    current_response_time_percentiles = {        f"response_time_percentile_{str(percentile).replace('.', '')}": [            timestamp,            stats.total.get_current_response_time_percentile(percentile) or 0,        ]        for percentile in [0.5, 0.95]    }    data = anyio.run(push_data, runner, io, current_response_time_percentiles)    stats.history.append(data)async def push_data(runner: Runner, io: APIStarter, current_response_time_percentiles: dict = None):    stats = runner.stats    timestamp = GenerateTools.getTime(4)    data = {        "status": str(runner.state).upper(),        "max_response": proper_round(stats.total.max_response_time, digits=2),        "request_num": stats.num_requests,        "request_fail_num": stats.num_failures,        "total_rps": proper_round(stats.total.total_rps, digits=2),        "user_count": runner.target_user_count,        "current_rps": [timestamp, proper_round(stats.total.current_rps, digits=2) or 0],        "current_fail_per_sec": [timestamp, stats.total.current_fail_per_sec or 0],        "total_avg_response_time": [timestamp, proper_round(stats.total.avg_response_time, digits=2)],        "cpu": runner.current_cpu_usage,    }    if current_response_time_percentiles:        data.update(current_response_time_percentiles)    log.error(data)    await io.push(data)    return datalocust_client = LocustClient()