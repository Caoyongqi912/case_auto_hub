#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/20# @Author : cyq# @File : projectPart# @Software: PyCharm# @Desc:from sys import orig_argvfrom typing import Listfrom sqlalchemy import select, and_, deletefrom sqlalchemy.ext.asyncio import AsyncSessionfrom app.mapper import Mapperfrom app.model import async_sessionfrom app.model.base import CasePart, Userfrom utils import MyLogurulog = MyLoguru().get_logger()async def list2Tree(data: List):    """    列表转树    :param data:    :return:    """    mapping: dict = dict(zip([i['id'] for i in data], data))    c = []    for d in data:        parent: dict = mapping.get(d['parentID'])        if parent is None:            c.append(d)        else:            children: list = parent.get("children")            if not children:                children = []            children.append(d)            parent.update({"children": children})    return cclass ProjectPartMapper(Mapper):    __model__ = CasePart    @classmethod    async def remove_part(cls, partId: int):        try:            async with async_session() as session:                async with session.begin():                    part = await cls.get_by_id(partId, session)                    if part.isRoot:                        subPartId = await ProjectPartMapper.get_subtree_ids(session, partId)                        for i in subPartId:                            await session.execute(delete(CasePart).where(CasePart.id == i))                    await session.delete(part)        except Exception as e:            raise e    @classmethod    async def drop(cls, id: int, targetId: int | None):        try:            async with async_session() as session:                part: CasePart = await cls.get_by_id(id, session)                if targetId:                    target_part: CasePart = await cls.get_by_id(targetId, session)                    part.parentID = target_part.id                    part.isRoot = False                    if target_part.isRoot:                        part.rootID = target_part.id                else:                    part.isRoot = True                    part.parentID = None                    part.rootID = None                session.add(part)                await session.commit()        except Exception as e:            raise e    @staticmethod    async def query_parent_part_by_projectId(project_id: int) -> List[CasePart]:        """        通过projectID 查询父级目录        :param project_id:        :return:        """        try:            async with async_session() as session:                sql = select(CasePart).where(                    and_(                        CasePart.isRoot == 1,                        CasePart.projectID == project_id                    ))                exe = await session.execute(sql)                return exe.scalars().all()        except Exception as e:            raise e    @classmethod    async def query_by(cls, **kwargs) -> List[dict]:        queryParts: List[CasePart] = await super().query_by(**kwargs)        parts = [part.map for part in queryParts]        return await list2Tree(parts)    @classmethod    async def get_subtree_ids(cls, session: AsyncSession, part_id: int):        """        递归查询某个 CasePart 节点及其所有子节点的 ID。        :param session: 异步数据库会话        :param part_id: 起始节点的 ID        :return: 所有子节点的 ID 列表        """        try:            # 基础查询：选择起始节点            base_query = select(CasePart.id).where(CasePart.id == part_id)            # 递归 CTE：查询所有子节点            cte = base_query.cte(name='ChildRecords', recursive=True)            cte = cte.union_all(                select(CasePart.id)                .where(CasePart.parentID == cte.c.id)            )            # 最终查询：选择所有子节点的 ID            recursive_query = select(cte.c.id)            return (await session.execute(recursive_query)).scalars().all()        except Exception as e:            log.error(f"递归查询失败: {e}")            raise e