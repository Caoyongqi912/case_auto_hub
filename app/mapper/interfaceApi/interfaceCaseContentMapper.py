#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/3
# @Author : cyq
# @File : interfaceCaseContentMapper
# @Software: PyCharm
# @Desc:
from typing import Dict,Type

from sqlalchemy.ext.asyncio import AsyncSession
from app.mapper import Mapper
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
    async def copy_content(cls,content_id:int,session:AsyncSession,user:User, **kwargs):
        pass