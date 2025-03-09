#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/12/4# @Author : cyq# @File : _script# @Software: PyCharm# @Desc:import asynciofrom app.model import async_sessionfrom app.model.interface import InterfaceScriptDescfrom app.model.interface.interfaceGlobal import InterfaceGlobalFuncscs = [    dict(        title="timestamp(day:str = None)-> str 获取时间戳",        subTitle="Func",        args=str(["+1s", "-1s", "+1m", "-1m", "+1h", "-1h"]),        desc='获取不同时间的时间戳',        example="ts=timestamp();",        returnContent=':return 1705114614000'    ),    {        "title": "date(day:str = None) -> str 获取日期",        "subTitle": "Func",        "args": "['+1d', '-1d', '+1m', '-1m', '+1y', '-1y']",        "desc": "获取 YYYY-MM-DD 格式时间",        "example": "currentDay = date()",        "returnContent": ':return 2024-01-13'    },    {        "title": "log(message:str) -> NoReturn: 打印日志",        "subTitle": "Func",        "args": "",        "desc": "日志输出",        "example": "execute_sql(db='db_name',sql='insert ...');",        "returnContent": ':no return'    },    {        "title": 'response 响应体',        "subTitle": 'Http Response Object',        "example": 'text = response.text , jsonBody = response.json()',        "desc": '当前步骤返回响应体对象 用于后置操作',        "returnContent": ':return Any',    },    {        "title": 'faker 生成伪数据',        "subTitle": 'Faker Object',        "example": 'name = faker.name()',        "desc": '当前步骤返回响应体对象 用于后置操作',        "returnContent": ':return Any',    },]funcs = [    {        "label": "$f_name",        "value": "{{$f_name}}",        "description": "随机生成姓名",        "demo": "大娃"    },    {        "label": "$f_address",        "value": "{{$f_address}}",        "description": "随机生成地址",        "demo": "北京市朝阳区建国路12号"    },    {        "label": "$f_phone_number",        "value": "{{$f_phone_number}}",        "description": "随机生成电话号码",        "demo": "13812345678"    },    {        "label": "$f_email",        "value": "{{$f_email}}",        "description": "随机生成电子邮件地址",        "demo": "example@example.com"    },    {        "label": "$f_text",        "value": "{{$f_tex}}",        "description": "随机生成一段文本",        "demo": "这是一段随机生成的文本，用于填充数据。"    },    {        "label": "$f_city",        "value": "{{$f_city}}",        "description": "随机生成城市名称",        "demo": "上海"    },    {        "label": "$f_country",        "value": "{{$f_country}}",        "description": "随机生成国家名称",        "demo": "中国"    },    {        "label": "$f_date_of_birth",        "value": "{{$f_date_of_birth}}",        "description": "随机生成出生日期",        "demo": "1990-05-23"    },    {        "label": "$f_url",        "value": "{{$f_url}}",        "description": "随机生成 URL 地址",        "demo": "https://www.example.com"    },    {        "label": "$f_uuid",        "value": "{{$f_uuid}}",        "description": "随机生成 UUID",        "demo": "123e4567-e89b-12d3-a456-426614174000"    },    {        "label": "$timestamp",        "value": "{{$timestamp}}",        "description": "生成当前时间戳",        "demo": "1739974246313"    },    {        "label": "$today",        "value": "{{$today}}",        "description": "生成当前日期",        "demo": "2025-02-19"    }, {        "label": "$now",        "value": "{{$now}}",        "description": "生成当前日期",        "demo": "2025-02-19 22:22:50"    }, {        "label": "$monthFirst",        "value": "{{$monthFirst}}",        "description": "生成当月一号",        "demo": "2025-02-01"    },    {        "label": "$yesterday",        "value": "{{$yesterday}",        "description": "生成昨天日期",        "demo": "2025-02-02"    }]# async def insertScript():#     for sc in scs:#         await insert(**sc)async def inertFuncs():    try:        async with async_session() as session:            async with session.begin():                for func in funcs:                    model = InterfaceGlobalFunc(**func)                    session.add(model)    except Exception as e:        raise e# async def insert(**kwargs):#     async with async_session() as session:#         async with session.begin():#             for sc in scs:#                 model = InterfaceScriptDesc(**sc)#                 session.add(model)import hashlib# 创建MD5对象md5_hash = hashlib.md5()# 更新MD5对象，必须是字节类型md5_hash.update("your_string_here".encode('utf-8'))# 获取MD5的十六进制结果password = md5_hash.hexdigest()if __name__ == '__main__':    print(password)