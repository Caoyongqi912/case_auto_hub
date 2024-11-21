#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/10/16# @Author : cyq# @File : uiCaseStepGroupMapper# @Software: PyCharm# @Desc:from typing import Typefrom sqlalchemy import insert, select, delete, and_from sqlalchemy.ext.asyncio import AsyncSessionfrom app.mapper import Mapper, Tfrom app.mapper.ui.uiCaseMapper import UICaseStepMapperfrom app.model import async_sessionfrom app.model.ui import UIStepGroupModel, group_step_Table, UICaseStepsModelfrom utils import logclass UICaseStepGroupMapper(Mapper):    __model__ = UIStepGroupModel    @classmethod    async def delete_by_id(cls, id: int):        """        通过uid删除        公共用例不删除        删除关联表        :param id:        """        try:            async with async_session() as session:                async with session.begin():                    # 查询steps                    step_query = await session.execute(                        select(UICaseStepsModel).join(                            group_step_Table,                            group_step_Table.c.ui_step_id == UICaseStepsModel.id                        ).where(                            and_(                                group_step_Table.c.ui_group_id == id,                                UICaseStepsModel.isCommonStep == 0                            )                        )                    )                    steps = step_query.scalars().all()                    # 删除关联表中的记录                    await session.execute(                        delete(group_step_Table).where(group_step_Table.c.ui_group_id == id)                    )                    target = await cls.get_by_id(id, session)                    for step in steps:                        await session.delete(step)                    await session.delete(target)        except Exception as e:            raise e    @classmethod    async def remove_group_step_by_id(cls, groupId: int, stepId: int):        """        remove_group_step_by_id        非公共用例删除        公共用例 删除关联        重新排序        :param groupId:        :param stepId:        :return:        """        try:            async with async_session() as session:                group: UIStepGroupModel = await cls.get_by_id(groupId, session, desc="步骤组")                step: UICaseStepsModel = await UICaseStepMapper.get_by_id(stepId, session, desc="步骤")                if step.isCommonStep:                    await cls.remove_group_step_by_id(groupId, stepId)                else:                    await cls.delete_commonStep_association_and_reorder(session, groupId, stepId)                    await session.delete(step)                group.stepNum -= 1                await session.commit()        except Exception as e:            raise e    @classmethod    async def addStepList(cls, group_id: int, stepList: [int]):        """        添加步骤关联        :param group_id:        :param stepList:        :return:        """        try:            async with async_session() as session:                group = await cls.get_by_id(group_id, session)                # 批量插入用例                new_group_step = [                    {                        'ui_group_id': group.id,                        'ui_step_id': stepId,                        'step_order': index                    }                    for index, stepId in enumerate(stepList, start=1)                ]                await session.execute(insert(group_step_Table).values(new_group_step))                await session.commit()        except Exception as e:            raise e    @classmethod    async def query_steps_by_groupId(cls, groupId: int):        """        :param groupId:        :return:        """        try:            async with async_session() as session:                data = select(UICaseStepsModel).join(                    group_step_Table,                    group_step_Table.c.ui_step_id == UICaseStepsModel.id                ).where(                    group_step_Table.c.ui_group_id == groupId                ).order_by(group_step_Table.c.step_order)                steps = await session.execute(data)                return steps.scalars().all()        except Exception as e:            raise e    @classmethod    async def order_steps_by_groupId(cls, groupId: int, stepList: [int]):        """        用例组重新排序        :param groupId:        :param stepList:        :return:        """        try:            async with async_session() as session:                await cls.order_step(session, groupId, stepList)                await session.commit()        except Exception as e:            raise e    @classmethod    async def addStep(cls, groupId: int, **kwargs):        """        添加用例        关联group表        :param groupId:        :param kwargs:        :return:        """        try:            async with async_session() as session:                group: UIStepGroupModel = await cls.get_by_id(groupId, session, desc="步骤组")                lastOrder = await cls.get_group_step_last_index(session, groupId)                stepId = kwargs.get("id", None)                if not stepId:                    step = UICaseStepsModel(**kwargs)                    session.add(step)                    await session.flush()                    session.expunge(step)                else:                    step = UICaseStepMapper.get_by_id(stepId, session, "步骤")                # 创建关联                await session.execute(                    insert(group_step_Table).values(                        {                            'ui_group_id': group.id,                            'ui_step_id': step.id,                            'step_order': lastOrder + 1                        }                    )                )                group.stepNum += 1                await session.commit()        except Exception as e:            raise e    @staticmethod    async def get_group_step_last_index(session: AsyncSession, groupId: int) -> int:        """        get group_step_Table last step order by groupId        :param session:        :param groupId:        :return:        """        try:            # Construct the query to get the last step order            sql = (                select(group_step_Table.c.step_order)                .where(group_step_Table.c.ui_group_id == groupId)                .order_by(group_step_Table.c.step_order.desc())  # Order by step_order descending                .limit(1)  # Limit to the last step only            )            # Execute the query            result = await session.execute(sql)            last_step_order = result.scalar()  # Fetch the first (and only) result            return last_step_order or 0        except Exception as e:            raise e    @staticmethod    async def delete_commonStep_association_and_reorder(session: AsyncSession, groupId: int, stepId: int):        """        :param session:        :param groupId:        :param stepId:        :return:        """        try:            await session.execute(                delete(group_step_Table).where(                    and_(                        group_step_Table.c.ui_group_id == groupId,                        group_step_Table.c.ui_step_id == stepId                    )                )            )            await UICaseStepGroupMapper.reorder_steps_by_groupId(session, groupId)        except Exception as e:            raise e    @staticmethod    async def reorder_steps_by_groupId(session: AsyncSession, groupId: int):        """        重新排序        :param session:        :param groupId:        :return:        """        try:            data = await session.execute(select(group_step_Table.c.ui_step_id).where(                group_step_Table.c.ui_group_id == groupId            ).order_by(group_step_Table.c.step_order))            steps = data.scalars()            await UICaseStepGroupMapper.order_step(session, groupId, steps)            log.debug(steps)        except Exception as e:            raise e    @staticmethod    async def order_step(session: AsyncSession, groupId: int, stepList: [int]):        """        排序        :param session:        :param groupId:        :param stepList:        :return:        """        for index, stepId in enumerate(stepList, start=1):            # 更新项目的顺序信息            association = group_step_Table.update().where(                (group_step_Table.c.ui_group_id == groupId) &                (group_step_Table.c.ui_step_id == stepId)            ).values(step_order=index)            await session.execute(association)