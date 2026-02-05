#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/6
# @Author : cyq
# @File : config
# @Software: PyCharm
# @Desc:
import os
import pickle

import pytz
from apscheduler.jobstores.redis import RedisJobStore
from dotenv import load_dotenv


class BaseConfig:
    ROOT = os.path.dirname(os.path.abspath(__file__))
    SECRET_KEY = "HARD TO GUESS"
    MYSQL_DATABASE = 'autoHub'
    MYSQL_PORT: int = 3306
    REDIS_PORT = 6379
    # sqlalchemy
    SQLALCHEMY_DATABASE_URI: str = ''
    # 异步URI
    ASYNC_SQLALCHEMY_URI: str = ''
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    Email_Sender_Username = "17611395912@163.com"
    Email_Sender_Password = "ZWdk2sGV*****V3UkQ9KU"
    Smtp_Server = "smtp.163.com"
    Smtp_port = 578

    WeChatBaseUrl = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"

    Banner = """
         ██████╗ █████╗ ███████╗███████╗    ██╗  ██╗██╗   ██╗████████╗ 
        ██╔════╝██╔══██╗██═════╝██═════╝    ██║  ██║██║   ██║██     ██╗
        ██║     ███████║███████╗███████╗    ███████║██║   ██║███████╔═╝
        ██║     ██╔══██║╚════██║██═════╝    ██╔══██║██║   ██║██     ██╗
        ╚██████╗██║  ██║███████║███████╗    ██║  ██║╚██████╔╝████████╔╝   
         ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝    ╚═╝  ╚═╝ ╚═════╝ ╚═══════╝   
         """


class LocalConfig(BaseConfig):
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = 5050
    DOMAIN = f"http://{SERVER_HOST}:{SERVER_PORT}"
    TASK_WORKER_POOL_SIZE = 10
    FILE_AVATAR_PATH = DOMAIN + "/file/avatar/uid="

    Record_Proxy = False
    # 硬编码MySQL配置
    MYSQL_SERVER = "127.0.0.1"
    MYSQL_PASSWORD = "sdkjfhsdkjhfsdkhfksd"
    # MYSQL_PASSWORD = "qq23qq"
    MYSQL_DATABASE = 'autoHub'
    MYSQL_PORT: int = 3306

    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://{}:{}@{}/{}'.format(
        'root', MYSQL_PASSWORD, MYSQL_SERVER, MYSQL_DATABASE)

    ASYNC_SQLALCHEMY_URI = f'mysql+aiomysql://root:{MYSQL_PASSWORD}' \
                           f'@{MYSQL_SERVER}:{BaseConfig.MYSQL_PORT}/{BaseConfig.MYSQL_DATABASE}'

    Inter_TASK_URL = f"{DOMAIN}interface/task/detail/taskId=&projectId="
    Inter_REPORT_URL = f"{DOMAIN}/interface/task/report/detail/resultId="

    REDIS_DB = 0
    REDIS_WORKER_POOL_BD = 10
    # 硬编码Redis配置
    REDIS_SERVER = "127.0.0.1"
    REDIS_PORT = 6379
    REDIS_URL: str = f"redis://{REDIS_SERVER}:{BaseConfig.REDIS_PORT}/{REDIS_DB}"
    REDIS_Broker: str = f"redis://{REDIS_SERVER}:{BaseConfig.REDIS_PORT}/1"
    REDIS_Backend: str = f"redis://{REDIS_SERVER}:{BaseConfig.REDIS_PORT}/2"

    CX_Oracle_Client_Dir = "/Users/cyq/Downloads/instantclient_23_3"

    # ======================= ui playwright ====================
    INIT_PLAY_BROWSER = False
    UI_Headless = True
    UI_Timeout = 3000
    UI_SLOW = 500
    UI_ERROR_PATH = DOMAIN + "/file/ui_case/uid="
    UI_TASK_URL = f"{DOMAIN}/ui/task/detail/taskId="
    UI_REPORT_URL = f"{DOMAIN}/ui/report/detail/resultId="

    # ======================= APScheduler ====================
    APS = False
    APS_TZ = pytz.timezone('Asia/Shanghai')
    APSJobStores = {
        'default':
        RedisJobStore(
            db=1,  # Redis 数据库编号
            jobs_key='apscheduler.jobs',  # 存储任务的键
            run_times_key='apscheduler.run_times',  # 存储任务运行时间的键
            host=REDIS_SERVER,  # Redis 服务器地址
            pickle_protocol=pickle.DEFAULT_PROTOCOL,
            port=BaseConfig.REDIS_PORT,  # Redis 服务器端口
            password=None  # Redis 密码（如果没有密码，设置为 None）
        ),
    }

    @staticmethod
    def task_url(target: str, task_id: int, project_id: int):
        if target == "API":
            return f"{Config.DOMAIN}interface/task/detail/taskId={task_id}&projectId={project_id}"
        return f"{Config.DOMAIN}/ui/task/detail/taskId={task_id}"

    @staticmethod
    def report_url(target: str, result_id: int):
        if target == "API":
            return f"{Config.DOMAIN}/interface/task/report/detail/resultId={result_id}"
        return f"{Config.DOMAIN}/ui/report/detail/resultId={result_id}"


class ProConfig(BaseConfig):
    ...


class DockerConfig(BaseConfig):
    """Docker环境配置"""
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 5050
    DOMAIN = f"http://{SERVER_HOST}:{SERVER_PORT}"
    TASK_WORKER_POOL_SIZE = 10
    FILE_AVATAR_PATH = DOMAIN + "/file/avatar/uid="

    Record_Proxy = False
    # 从环境变量读取MySQL配置
    MYSQL_SERVER = os.getenv("MYSQL_HOST", "mysql")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "sdkjfhsdkjhfsdkhfksd")
    MYSQL_DATABASE = os.getenv("MYSQL_DB", "autoHub")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))

    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://{}:{}@{}/{}'.format(
        'root', MYSQL_PASSWORD, MYSQL_SERVER, MYSQL_DATABASE)

    ASYNC_SQLALCHEMY_URI = f'mysql+aiomysql://root:{MYSQL_PASSWORD}' \
                           f'@{MYSQL_SERVER}:{MYSQL_PORT}/{MYSQL_DATABASE}'

    Inter_TASK_URL = f"{DOMAIN}interface/task/detail/taskId=&projectId="
    Inter_REPORT_URL = f"{DOMAIN}/interface/task/report/detail/resultId="

    REDIS_DB = 0
    REDIS_WORKER_POOL_BD = 10
    # 从环境变量读取Redis配置
    REDIS_SERVER = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_URL: str = f"redis://{REDIS_SERVER}:{REDIS_PORT}/{REDIS_DB}"
    REDIS_Broker: str = f"redis://{REDIS_SERVER}:{REDIS_PORT}/1"
    REDIS_Backend: str = f"redis://{REDIS_SERVER}:{REDIS_PORT}/2"

    # ======================= ui playwright ====================
    INIT_PLAY_BROWSER = False
    UI_Headless = True
    UI_Timeout = 10000
    UI_SLOW = 500
    UI_ERROR_PATH = DOMAIN + "/file/ui_case/uid="
    UI_TASK_URL = f"{DOMAIN}/ui/task/detail/taskId="
    UI_REPORT_URL = f"{DOMAIN}/ui/report/detail/resultId="

    # ======================= APScheduler ====================
    APS = False
    APS_TZ = pytz.timezone('Asia/Shanghai')
    APSJobStores = {
        'default':
        RedisJobStore(
            db=1,  # Redis 数据库编号
            jobs_key='apscheduler.jobs',  # 存储任务的键
            run_times_key='apscheduler.run_times',  # 存储任务运行时间的键
            host=REDIS_SERVER,  # Redis 服务器地址
            pickle_protocol=pickle.DEFAULT_PROTOCOL,
            port=REDIS_PORT,  # Redis 服务器端口
            password=None  # Redis 密码（如果没有密码，设置为 None）
        ),
    }

    @staticmethod
    def task_url(target: str, task_id: int, project_id: int):
        if target == "API":
            return f"{Config.DOMAIN}interface/task/detail/taskId={task_id}&projectId={project_id}"
        return f"{Config.DOMAIN}/ui/task/detail/taskId={task_id}"

    @staticmethod
    def report_url(target: str, result_id: int):
        if target == "API":
            return f"{Config.DOMAIN}/interface/task/report/detail/resultId={result_id}"
        return f"{Config.DOMAIN}/ui/report/detail/resultId={result_id}"


load_dotenv()

# 配置加载逻辑
env = os.getenv("ENV", "pro")
if env == "docker":
    Config = DockerConfig
elif env == "dev":
    Config = LocalConfig
else:
    Config = ProConfig
