#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/7
# @Author : cyq
# @File : myLoguru
# @Software: PyCharm
# @Desc:
import os
import sys

from loguru import logger

_project_path = os.path.split(os.path.dirname(__file__))[0]
_Logs_path = os.path.join(_project_path, 'logs')


class BaseConfig:
    # 其他配置...
    
    # 日志配置
    LOG_MAX_SIZE = "500 MB"
    LOG_RETENTION = "7 days"
    LOG_DEBUG = False
    LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
    
class MyLoguru:
    """
    日志记录器
    
    特性：
    - 单例模式，全局唯一实例
    - 根据时间和文件大小自动切割日志
    - 分离不同级别的日志到不同文件
    - 支持自定义日志格式和保留策略
    - 线程和进程安全
    - 自动创建日志目录
    - 支持从配置文件读取配置
    
    使用示例：
    >>> from utils import log
    >>> log.info("This is an info message")
    >>> log.error("This is an error message")
    >>> # 绑定上下文
    >>> log_with_context = log.bind(user_id="123")
    >>> log_with_context.info("User login")
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, max_size=None, retention=None, debug=None):
        """
        初始化日志记录器
        
        :param max_size: 日志文件最大大小
        :param retention: 日志保留时间
        :param debug: 是否开启调试模式
        """
        # 防止重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        # 从配置文件或环境变量读取配置
        try:
            from config import Config
            self.log_dir = _Logs_path
            self.max_size = max_size or getattr(Config, 'LOG_MAX_SIZE', "500 MB")
            self.retention = retention or getattr(Config, 'LOG_RETENTION', '7 days')
            self.debug = debug if debug is not None else getattr(Config, 'LOG_DEBUG', False)
        except ImportError:
            # 配置文件不存在时使用默认值
            self.log_dir = _Logs_path
            self.max_size = max_size or "500 MB"
            self.retention = retention or '7 days'
            self.debug = debug or False
        
        self.logger = logger
        self._configure_logger()
        self._initialized = True
    
    def _configure_logger(self):
        """配置日志记录器"""
        self.logger.remove()

        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)

        # 基础日志格式
        base_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<blue>{process.name}</blue> | "
            "<blue>{thread.name}</blue> | "
            "<cyan>{file}</cyan>.<cyan>{module}</cyan>.<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        )
        # 错误日志格式（包含堆栈跟踪）
        error_format = base_format + "\n{exception}"
        
        # 普通日志文件配置
        self.logger.add(
            sink=f"{self.log_dir}/access-{{time:YYYY-MM-DD}}.log",
            rotation=self.max_size,
            retention=self.retention,
            level="INFO",
            format=base_format,
            enqueue=True,
            compression="zip",
            buffer=True
        )

        # 错误日志单独记录
        self.logger.add(
            sink=f"{self.log_dir}/error-{{time:YYYY-MM-DD}}.log",
            rotation=self.max_size,
            retention=self.retention,
            level="ERROR",
            format=error_format,
            enqueue=True,
            backtrace=True,
            diagnose=True,
            buffer=True
        )
        
        # 控制台输出配置
        self.logger.add(
            sink=sys.stdout,
            level="DEBUG",
            format=base_format,
            enqueue=True,
            colorize=True,
            backtrace=self.debug,
            diagnose=self.debug
        )
    
    def get_logger(self):
        """
        获取日志记录器实例
        
        :return: loguru logger实例
        """
        return self.logger
    
    def bind(self, **kwargs):
        """
        绑定上下文信息到日志
        
        :param kwargs: 上下文信息
        :return: 绑定了上下文的日志记录器
        """
        return self.logger.bind(**kwargs)
    
    def add_filter(self, filter_func):
        """
        添加日志过滤器
        
        :param filter_func: 过滤函数
        """
        self.logger.add_filter(filter_func)
    
    def remove_filter(self, filter_func):
        """
        移除日志过滤器
        
        :param filter_func: 过滤函数
        """
        self.logger.remove_filter(filter_func)
    """
    日志记录器

    特性：
    - 根据时间和文件大小自动切割日志
    - 分离不同级别的日志到不同文件
    - 支持自定义日志格式和保留策略
    - 线程和进程安全
    - 自动创建日志目录

    使用示例：
    >>> log = MyLoguru().get_logger()
    >>> log.info("This is an info message")
    >>> log.error("This is an error message")
    """

    def __init__(self, max_size="500 MB", retention='7 days', debug=False):
        self.log_dir = _Logs_path
        self.max_size = max_size
        self.retention = retention
        self.logger = logger
        self.debug = debug
        self._configure_logger()

    def _configure_logger(self):
        """配置日志记录器"""
        self.logger.remove()

        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)

        # 基础日志格式
        base_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<blue>{process.name}</blue> | "
            "<blue>{thread.name}</blue> | "
            "<cyan>{file}</cyan>.<cyan>{module}</cyan>.<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        )
        # 错误日志格式（包含堆栈跟踪）
        error_format = base_format + "\n{exception}"
        # 普通日志文件配置
        self.logger.add(
            sink=f"{self.log_dir}/access-{{time:YYYY-MM-DD}}.log",
            rotation=self.max_size,
            retention=self.retention,
            level="INFO",
            format=base_format,
            enqueue=True,
            compression="zip"  # 可选的日志压缩
        )

        # 错误日志单独记录
        self.logger.add(
            sink=f"{self.log_dir}/error-{{time:YYYY-MM-DD}}.log",
            rotation=self.max_size,
            retention=self.retention,
            level="ERROR",
            format=error_format,
            enqueue=True,
            backtrace=True,  # 错误日志总是记录堆栈
            diagnose=True  # 错误日志总是记录变量值
        )
        # 控制台输出配置
        self.logger.add(
            sink=sys.stdout,
            level="DEBUG",
            format=base_format,
            enqueue=True,  # 确保线程安全
            colorize=True,  # 启用颜色
            backtrace=self.debug,  # 调试模式下显示完整堆栈
            diagnose=self.debug  # 调试模式下显示变量值
        )

    def get_logger(self):
        return self.logger
