#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/10
# @Author : cyq
# @File : interfaceResultMapper
# @Software: PyCharm
# @Desc:
from app.mapper import Mapper
from app.model.base.user import User
from app.model.interfaceAPIModel import InterfaceCaseResult
from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from app.model.base import EnvModel

class InterfaceCaseResultMapper(Mapper[InterfaceCaseResult]):
    __model__ = InterfaceCaseResult



    @classmethod
    async def init_case_result(cls,user:User, case:InterfaceCase,env:EnvModel):

        try:
            async with cls.transaction() as session:
                case_result = InterfaceCaseResult(
                    case_id=case.id,
                    env_id=env.id,
                    starter_id=user.id,
                    starter_name=user.username,
                    
                )


        except Exception:
            pass