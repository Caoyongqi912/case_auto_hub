#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planModuleMapper
# @Software: PyCharm
# @Desc: 计划分组数据访问层
from typing import List, Optional

from sqlalchemy import select, delete, and_

from app.mapper import Mapper
from app.model.base import User
from app.model.caseHub.plan_module import PlanModule


class PlanModuleMapper(Mapper[PlanModule]):
    __model__ = PlanModule

    @classmethod
    async def add_module(
        cls,
        plan_id: int,
        title: str,
        user: User,
        parent_id: Optional[int] = None,
        order: int = 0
    ) -> PlanModule:
        """
        添加计划分组
        :param plan_id: 计划ID
        :param title: 分组名称
        :param user: 创建人
        :param parent_id: 父级分组ID
        :param order: 排序顺序
        :return: 创建的分组
        """
        return await cls.save(
            creator_user=user,
            plan_id=plan_id,
            title=title,
            parent_id=parent_id,
            order=order
        )

    @classmethod
    async def update_module(
        cls,
        module_id: int,
        user: User,
        title: Optional[str] = None,
        parent_id: Optional[int] = None,
        order: Optional[int] = None
    ) -> PlanModule:
        """
        更新计划分组
        :param module_id: 分组ID
        :param user: 更新人
        :param title: 分组名称
        :param parent_id: 父级分组ID
        :param order: 排序顺序
        :return: 更新后的分组
        """
        kwargs = {"id": module_id}
        if title is not None:
            kwargs["title"] = title
        if parent_id is not None:
            kwargs["parent_id"] = parent_id
        if order is not None:
            kwargs["order"] = order
        
        return await cls.update_by_id(update_user=user, **kwargs)

    @classmethod
    async def remove_module(cls, module_id: int) -> int:
        """
        删除计划分组（会级联删除子分组）
        :param module_id: 分组ID
        :return: 删除数量
        """
        try:
            async with cls.transaction() as session:
                deleted_count = 0
                
                async def delete_tree(parent_id: int):
                    nonlocal deleted_count
                    stmt = select(PlanModule).where(PlanModule.parent_id == parent_id)
                    result = await session.execute(stmt)
                    children = result.scalars().all()
                    
                    for child in children:
                        await delete_tree(child.id)
                    
                    del_stmt = delete(PlanModule).where(PlanModule.id == parent_id)
                    result = await session.execute(del_stmt)
                    deleted_count += result.rowcount
                
                await delete_tree(module_id)
                return deleted_count
        except Exception as e:
            raise

    @classmethod
    async def move_module(
        cls,
        module_id: int,
        new_parent_id: Optional[int] = None,
        order: Optional[int] = None
    ) -> PlanModule:
        """
        移动计划分组到新的父级分组下
        :param module_id: 分组ID
        :param new_parent_id: 新的父级分组ID，None表示移到根级
        :param order: 排序顺序
        :return: 移动后的分组
        """
        try:
            async with cls.transaction() as session:
                module = await cls.get_by_id(ident=module_id, session=session)
                if not module:
                    raise ValueError("分组不存在")
                
                if new_parent_id is not None:
                    parent = await cls.get_by_id(ident=new_parent_id, session=session)
                    if not parent:
                        raise ValueError("父级分组不存在")
                    if parent.plan_id != module.plan_id:
                        raise ValueError("不能移动到其他计划的分组下")
                
                if new_parent_id is not None:
                    module.parent_id = new_parent_id
                if order is not None:
                    module.order = order
                
                await session.flush()
                return module
        except Exception as e:
            raise

    @classmethod
    async def get_module_tree(cls, plan_id: int) -> List[dict]:
        """
        获取计划下所有分组（树形结构）
        :param plan_id: 计划ID
        :return: 树形结构列表
        """
        try:
            async with cls.transaction() as session:
                stmt = select(PlanModule).where(
                    PlanModule.plan_id == plan_id
                ).order_by(PlanModule.order, PlanModule.create_time)
                result = await session.execute(stmt)
                modules = result.scalars().all()
                return [m.map for m in modules]
        except Exception as e:
            raise

    @classmethod
    async def build_tree(cls, plan_id: int) -> List[dict]:
        """
        构建计划分组的完整树形结构
        :param plan_id: 计划ID
        :return: 树形结构
        """
        try:
            async with cls.transaction() as session:
                stmt = select(PlanModule).where(
                    PlanModule.plan_id == plan_id
                ).order_by(PlanModule.order, PlanModule.create_time)
                result = await session.execute(stmt)
                modules = result.scalars().all()
                
                module_list = [m.map for m in modules]
                module_dict = {m["key"]: m for m in module_list}
                
                for module in module_list:
                    module["children"] = []
                
                root_modules = []
                for module in module_list:
                    parent_id = module.get("parent_id")
                    if parent_id is None:
                        root_modules.append(module)
                    elif parent_id in module_dict:
                        module_dict[parent_id]["children"].append(module)
                
                return root_modules
        except Exception as e:
            raise