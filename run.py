#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/5# @Author : cyq# @File : _main# @Software: PyCharm# @Desc:import uvicornfrom config import ConfigAPP = "main:hub"if __name__ == "__main__":    uvicorn.run(APP,                host=Config.SERVER_HOST,                port=Config.SERVER_PORT,                reload=True,                forwarded_allow_ips="*",                workers=1)