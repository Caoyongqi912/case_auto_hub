#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/11
# @Author : cyq
# @File : gunicorn_conf.py
# @Software: PyCharm
# @Desc:
# gunicorn_conf.py 建议配置
bind = '0.0.0.0:5050'            
workers = 4                      
worker_class = "uvicorn.workers.UvicornWorker"
accesslog = "gunicorn_access.log"
errorlog = "gunicorn_error.log"
preload_app = True
daemon = False                     
loglevel = "info"
timeout = 30                     
graceful_timeout = 10            