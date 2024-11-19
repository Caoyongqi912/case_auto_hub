#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/7# @Author : cyq# @File : myLoguru# @Software: PyCharm# @Desc:import osimport sysfrom loguru import logger_project_path = os.path.split(os.path.dirname(__file__))[0]_Logs_path = os.path.join(_project_path, 'logs')class MyLoguru:    """    根据时间、文件大小切割日志    """    def __init__(self, max_size=30, retention='7 days'):        self.log_dir = _Logs_path        self.max_size = max_size        self.retention = retention        self.logger = logger        self.logger.remove()        self.configure_logger()    def configure_logger(self):        """        Returns:        """        # 创建日志目录        os.makedirs(self.log_dir, exist_ok=True)        # 添加按照日期和大小切割的文件 handler        self.logger.add(            sink=f"{self.log_dir}/access-{{time:YYYY-MM-DD}}.log",            rotation=f"{self.max_size} MB",            retention=self.retention,            level="INFO",            format='{time:YYYYMMDD HH:mm:ss} - '  # 时间                   "{process.name} | "  # 进程名                   "{thread.name} | "  # 进程名                   '{module}.{function}:{line} - {level} -{message}',  # 模块名.方法名:行号        )        # 配置按照等级划分的文件 handler 和控制台输出        self.logger.add(sys.stdout,                        format="<green>{time:YYYYMMDD HH:mm:ss}</green> | "  # 颜色>时间                               "<blue>{process.name}</blue> | "  # 进程名                               "<blue>{thread.name}</blue> | "  # 进程名                               "<cyan>{module}</cyan>.<cyan>{function}</cyan>"  # 模块名.方法名                               ":<cyan>{line}</cyan> | "  # 行号                               "<level>{level}</level>: "  # 等级                               "<level>{message}</level>",  # 日志内容                        )        self.logger.add(sink=f"{self.log_dir}/error-{{time:YYYY-MM-DD}}.log",                        rotation=f"{self.max_size} MB",                        retention=self.retention,                        backtrace=True,                        diagnose=True,                        format="<green>{time:YYYYMMDD HH:mm:ss}</green> | "  # 颜色>时间                               "<blue>{process.name}</blue> | "  # 进程名                               "<blue>{thread.name}</blue> | "  # 进程名                               "<cyan>{module}</cyan>.<cyan>{module}</cyan>.<cyan>{function}</cyan>"  # 模块名.方法名                               ":<cyan>{line}</cyan> | "  # 行号                               "<level>{level}</level>: "  # 等级                               "<level>{message}</level>",  # 日志内容                        level="ERROR")    def get_logger(self):        return self.logger