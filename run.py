#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/5
# @Author : cyq
# @File : _main
# @Software: PyCharm
# @Desc:
import uvicorn
from config import Config
APP = "main:hub"

if __name__ == "__main__":
    uvicorn.run(APP,
                host=Config.SERVER_HOST,
                port=Config.SERVER_PORT,
                reload=True,
                forwarded_allow_ips="*",
                workers=1)


# todo
# 1、 用例管理完善
# 2、 接口添加修改日志能力
# 3、 任务执行完善
