#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/3
# @Author : cyq
# @File : interfaceCaseContentMapper
# @Software: PyCharm
# @Desc: 用例步骤内容 Mapper
from typing import Dict, Type

from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.mapper.interfaceApi.interfaceGroupMapper import InterfaceGroupMapper
from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
from app.mapper.interfaceApi.interfaceLoopMapper import InterfaceLoopMapper
from app.mapper.interfaceApi.interfaceConditionMapper import InterfaceConditionMapper
from app.model.base import User
from app.model.interfaceAPIModel.contents import (
    InterfaceCaseContents,
    APIStepContent,
    GroupStepContent,
    ConditionStepContent,
    ScriptStepContent,
    DBStepContent,
    WaitStepContent,
    WhileStepContent,
    AssertStepContent,
    LoopStepContent,
)
from enums.CaseEnum import CaseStepContentType
from utils import log


class InterfaceCaseContentMapper(Mapper):
    
    CONTENT_TYPE_MAP: Dict[CaseStepContentType, Type[InterfaceCaseContents]] = {
        CaseStepContentType.STEP_API: APIStepContent,
        CaseStepContentType.STEP_API_GROUP: GroupStepContent,
        CaseStepContentType.STEP_API_CONDITION: ConditionStepContent,
        CaseStepContentType.STEP_API_SCRIPT: ScriptStepContent,
        CaseStepContentType.STEP_API_DB: DBStepContent,
        CaseStepContentType.STEP_API_WAIT: WaitStepContent,
        CaseStepContentType.STEP_API_WHILE: WhileStepContent,
        CaseStepContentType.STEP_API_ASSERT: AssertStepContent,
        CaseStepContentType.STEP_LOOP: LoopStepContent,
    }

    @classmethod
    async def insert_content(cls,user:User, session:AsyncSession,content_type:CaseStepContentType, target_id:int,    **kwargs) -> InterfaceCaseContents:

        """
        插入步骤内容

        根据 content_type 自动创建对应的子类实例，
        SQLAlchemy 会自动处理基类和子类记录的插入

        Args:
            user:创建人
            session: 数据库会话
            content_type: 步骤类型
            target_id: 关联目标 ID
            **kwargs: 其他可选字段（如 wait_time, script_text 等）

        Returns:
            InterfaceCaseContents: 创建的步骤内容实例
        """
        cls_model = cls.CONTENT_TYPE_MAP.get(content_type)
        if not cls_model:
            raise ValueError(f"不支持的 content_type: {content_type}")

        try:
            content = cls_model(
                target_id=target_id,
                creator=user.id,
                creator_name=user.creatorName,
                **kwargs
            )
            return await cls.add_flush_expunge(session=session, model=content)
        except Exception as e:
            log.error(f"insert_content {content_type} error: {e}")
            raise

    @classmethod
    async def copy_content(cls, content: InterfaceCaseContents, session: AsyncSession, user: User):
        """
        复制步骤内容

        Args:
            content: 步骤内容实例
            session: 数据库会话
            user: 复制人

        复制content实例
        - 接口：
            公共interface 复制引用
            私有interface 复制新实例
        - Group：
            复制引用
        - Condition：
            创建新Condition
            关联interface
                公共interface 复制引用
                私有interface 复制新实例
        - Loop：
            复制新实例
            关联interface
                公共interface 复制引用
                私有interface 复制新实例
        - 其他：
            直接复制

        Returns:
            InterfaceCaseContents: 复制后的步骤内容实例
        """
        cls_model = cls.CONTENT_TYPE_MAP.get(CaseStepContentType(content.content_type))
        if not cls_model:
            log.error(f"不支持的 content_type: {content.content_type}")
            return False

        new_content = cls_model(
            target_id=content.target_id,
            creator=user.id,
            creator_name=user.creatorName,
        )

        new_target_id = content.target_id
        match content.content_type:
            case CaseStepContentType.STEP_API:
                interface = await InterfaceMapper.get_by_id(ident=content.target_id, session=session)
                if not interface:
                    return False

                if not interface.is_common:
                    new_interface = await InterfaceMapper.copy_one(
                        target=interface,
                        user=user,
                        session=session,
                        is_common=False,
                    )
                    new_target_id = new_interface.id

            case CaseStepContentType.STEP_API_GROUP:
                group = await InterfaceGroupMapper.get_by_id(ident=content.target_id, session=session)
                if not group:
                    return False
                new_target_id = group.id

            case CaseStepContentType.STEP_API_CONDITION:
                new_condition = await InterfaceConditionMapper.copy_condition(
                    condition_id=content.target_id,
                    user=user,
                    session=session,
                )
                if not new_condition:
                    return False
                new_target_id = new_condition.id

            case CaseStepContentType.STEP_LOOP:
                new_loop = await InterfaceLoopMapper.copy_loop(
                    loop_id=content.target_id,
                    user=user,
                    session=session,
                )
                if not new_loop:
                    return False
                new_target_id = new_loop.id

            case _:
                new_target_id = content.target_id

        new_content.target_id = new_target_id
        return await cls.add_flush_expunge(session=session, model=new_content)