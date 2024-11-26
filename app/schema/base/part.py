#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/26# @Author : cyq# @File : part# @Software: PyCharm# @Desc:from pydantic import BaseModel, Fieldfrom app.schema import PageSchemaclass PartSchemaField(BaseModel):    id: int | None = None    uid: str | None = None    title: str | None = None    projectID: int | None = None    parentID: int | None = None    rootID: int | None = None    isRoot: bool | None = Noneclass InsertPartSchema(BaseModel):    title: str    projectID: int    parentID: int | None = None    rootID: int | None = None    isRoot: bool