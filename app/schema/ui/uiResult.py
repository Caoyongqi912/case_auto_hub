#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/2/5# @Author : cyq# @File : uiResult# @Software: PyCharm# @Desc:from app.schema import PageSchemaclass PageUIResultSchema(PageSchema):    ui_case_Id: int | None    ui_case_name: str | None    starter_id: int | None    starter_name: str | None    status:str|None