#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : config# @Software: PyCharm# @Desc:import osfrom apscheduler.jobstores.redis import RedisJobStorefrom dotenv import load_dotenvclass BaseConfig:    ROOT = os.path.dirname(os.path.abspath(__file__))    SECRET_KEY = "HARD TO GUESS"    MYSQL_DATABASE = 'autoHub'    MYSQL_PORT: int = 3306    REDIS_PORT = 6379    # sqlalchemy    SQLALCHEMY_DATABASE_URI: str = ''    # 异步URI    ASYNC_SQLALCHEMY_URI: str = ''    SQLALCHEMY_TRACK_MODIFICATIONS = False    WeChatUrl = ""class LocalConfig(BaseConfig):    SERVER_HOST: str = "127.0.0.1"    SERVER_PORT: int = 5050    DOMAIN = f"http://{SERVER_HOST}:{SERVER_PORT}"    UI_Headless = True    UI_Timeout = 5000    UI_SLOW = 500    UI_ERROR_PATH = DOMAIN + "/file/ui_case/uid="    FILE_AVATAR_PATH = DOMAIN + "/file/avatar/uid="    APS = False    Record_Proxy = False    MYSQL_SERVER = "127.0.0.1"    # MYSQL_PASSWORD = "sdkjfhsdkjhfsdkhfksd"    MYSQL_PASSWORD = "qq23qq"    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://{}:{}@{}:{}/{}'.format(        'root', MYSQL_PASSWORD, MYSQL_SERVER, BaseConfig.MYSQL_PORT, BaseConfig.MYSQL_DATABASE)    ASYNC_SQLALCHEMY_URI = f'mysql+aiomysql://root:{MYSQL_PASSWORD}' \                           f'@{MYSQL_SERVER}:{BaseConfig.MYSQL_PORT}/{BaseConfig.MYSQL_DATABASE}'    # UI_TASK_URL = f"{DOMAIN}:{BaseConfig.STRUCTURE_WEB_SERVER_PORT}/ui/task/detail/taskId="    # UI_REPORT_URL = f"{DOMAIN}:{BaseConfig.STRUCTURE_WEB_SERVER_PORT}/report/history/uiTask/detail/uid="    REDIS_DB = 0    REDIS_SERVER = "127.0.0.1"    REDIS_URL: str = f"redis://{REDIS_SERVER}:{BaseConfig.REDIS_PORT}/{REDIS_DB}"    APSJobStores = {        'default': RedisJobStore(            db=2,  # Redis 数据库编号            jobs_key='apscheduler.jobs',  # 存储任务的键            run_times_key='apscheduler.run_times',  # 存储任务运行时间的键            host=REDIS_SERVER,  # Redis 服务器地址            port=BaseConfig.REDIS_PORT,  # Redis 服务器端口            password=None  # Redis 密码（如果没有密码，设置为 None）        ),    }class ProConfig(BaseConfig):    ...load_dotenv()Config = LocalConfig if os.getenv("ENV", "pro") == "dev" else ProConfig