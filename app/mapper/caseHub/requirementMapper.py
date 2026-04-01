#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/26
# @Author : cyq
# @File : requirementMapper
# @Software: PyCharm
# @Desc:

from typing import Any, List, Optional

from sqlalchemy import insert, update, and_, select

from app.exception import NotFind
from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.caseHub.association import RequirementCaseAssociation
from app.model.caseHub.caseHUB import Requirement, TestCase
from app.mapper.user import UserMapper
from utils import log


class RequirementMapper(Mapper[Requirement]):
    __model__ = Requirement

    @classmethod
    async def update_requirement_case(cls, requirement_id: int, case_id: int,
                                      user: User,
                                      case_type: Optional[int] = None,
                                      case_level: Optional[str] = None,
                                      is_review: Optional[bool] = None,
                                      case_status: Optional[int] = None):
        """
        更新需求关联用例的属性

        :param requirement_id: 需求ID
        :param case_id: 用例ID
        :param user: 操作用户
        :param case_type: 用例类型
        :param case_level: 用例等级
        :param is_review: 是否审核
        :param case_status: 用例状态
        """
        from app.mapper.caseHub import CaseDynamicMapper

        updates = {
            "case_level": case_level.upper() if case_level else None,
            "case_type": case_type,
            "is_review": is_review,
            "case_status": case_status,
        }

        try:
            async with cls.transaction() as session:
                stmt = select(RequirementCaseAssociation).where(
                    and_(
                        RequirementCaseAssociation.requirement_id == requirement_id,
                        RequirementCaseAssociation.case_id == case_id
                    )
                )
                ass_instance = (await session.execute(stmt)).scalar_one_or_none()
                if not ass_instance:
                    raise NotFind("未找到信息")

                old_case = {}
                new_case = {}
                for field, new_value in updates.items():
                    if new_value is not None:
                        old_case[field] = getattr(ass_instance, field)
                        setattr(ass_instance, field, new_value)
                        new_case[field] = new_value

                if new_case:
                    await CaseDynamicMapper.update_dynamic(
                        case_id=case_id,
                        old_case=old_case,
                        new_case=new_case,
                        session=session,
                        cr=user
                    )
                    await cls.add_flush_expunge(session=session, model=ass_instance)
        except Exception as e:
            log.error(e)
            raise

    @classmethod
    async def insert_requirement(cls, user: User, case_ids: Optional[List[int]] = None, **kwargs) -> Requirement:
        """
        插入需求
        :param user
        :param case_ids
        :param kwargs
        """

        try:
            async with cls.transaction() as session:
                requirement = await cls.save(
                    creator_user=user,
                    session=session,
                    **kwargs
                )
                if case_ids:
                    from .testcaseMapper import get_last_index
                    last_order = await get_last_index(session=session, requirement_id=requirement.id)
                    requirement.case_number += len(case_ids)
                    await session.execute(
                        insert(RequirementCaseAssociation).values(
                            [{
                                "requirement_id": requirement.id,
                                "case_id": case_id,
                                "order": last_order + 1
                            } for case_id in case_ids],
                        )
                    )
                    await cls.add_flush_expunge(session=session, model=requirement)
                return requirement
        except Exception as e:
            log.error(e)
            raise

    @classmethod
    async def get_requirement_info(cls, **kwargs) -> dict[str, Any]:
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


