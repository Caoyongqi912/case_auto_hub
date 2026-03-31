#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/26
# @Author : cyq
# @File : requirementMapper
# @Software: PyCharm
# @Desc:

from typing import Any, List

from app.mapper import Mapper
from app.model import async_session
from app.model.caseHub.caseHUB import Requirement
from app.mapper.user import UserMapper


class RequirementMapper(Mapper[Requirement]):
    __model__ = Requirement

    @classmethod
    async def req_info(cls, **kwargs) -> dict[str, Any]:
        """
        获取需求详情信息
        :param kwargs: 查询条件（如 id）
        :return: 包含需求信息和关联用户信息的字典
        """
        async with async_session() as session:
            req = await cls.get_by_id(session=session, **kwargs)

            reqInfo = req.map
            reqInfo['developsInfo'] = []

            if req.maintainer:
                maintainer = await UserMapper.get_by_id(ident=req.maintainer, session=session)
                reqInfo['maintainerInfo'] = maintainer.userInfo

            if req.develops:
                dev_ids: List[int] = req.develops if isinstance(req.develops, list) else [req.develops]
                devs = await UserMapper.query_by_in_clause(target="id", list_=dev_ids, session=session)
                reqInfo['developsInfo'] = [dev.userInfo for dev in devs]

            return reqInfo
