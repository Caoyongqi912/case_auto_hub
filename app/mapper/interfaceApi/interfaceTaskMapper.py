from typing import List

from app.model import async_session
from app.model.interfaceAPIModel.interfaceTaskModel import InterfaceTask
from app.model.interfaceAPIModel.interfaceModel import Interface
from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from app.model.interfaceAPIModel.associationModel import InterfaceCaseTaskAssociation,InterfaceAPITaskAssociation
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_,delete,insert,update
from sqlalchemy import select
from app.mapper import Mapper


__all__ = [
    "InterfaceTaskMapper"
]
class InterfaceTaskMapper(Mapper[InterfaceTask]):
    __model__ = InterfaceTask


    @classmethod
    async def query_association_interfaces(cls,task_id:int) -> list[Interface]:
        """
        查询接口关联
        """
        try:
            async with async_session() as session:
                result = await session.scalars(
                    select(Interface).join(
                        InterfaceAPITaskAssociation,
                        InterfaceAPITaskAssociation.interface_api_id == Interface.id
                    ).where(
                        InterfaceAPITaskAssociation.interface_task_id == task_id
                    ).order_by(
                        InterfaceAPITaskAssociation.step_order
                    )
                )
                return result.all()
        except Exception as e:
            raise e 



    @classmethod
    async def query_association_interface_cases(cls,task_id:int) -> list[InterfaceCase]:
        """
        查询接口业务关联
        """
        try:
            async with async_session() as session:
                result = await session.scalars(
                    select(InterfaceCase).join(
                        InterfaceCaseTaskAssociation,
                        InterfaceCaseTaskAssociation.interface_case_id == InterfaceCase.id
                    ).where(
                        InterfaceCaseTaskAssociation.interface_task_id == task_id
                    ).order_by(
                        InterfaceCaseTaskAssociation.step_order
                    )
                )
                return result.all()
        except Exception as e:
            raise e 



    @classmethod
    async def association_interfaces(cls,task_id:int,interface_ids:list[int]) -> bool:
        """
        关联接口到任务
        """
        try:
            async with cls.transaction() as session:
                if not interface_ids:
                    return False
                task = await cls.get_by_id(ident=task_id,session=session)
                if not task:
                    return False

                last_step_order = await cls.get_api_last_index(task_id=task_id,session=session)
                await cls.insert_interfaces_task_association(session=session,
                            task_id=task_id,
                            interface_ids=interface_ids,
                            step_order=last_step_order)
                task.interface_task_total_apis_num += len(interface_ids)
                return True
        except Exception as e:
            raise e

    

    @classmethod
    async def association_interface_cases(cls,task_id:int,case_ids:list[int]) -> bool:
        """
        关联接口业务到任务  
        """
        try:
            async with cls.transaction() as session:
                if not case_ids:

                    return False
                task = await cls.get_by_id(ident=task_id,session=session)
                if not task:
                    return False

                last_step_order = await cls.get_case_last_index(task_id=task_id,session=session)
                await cls.insert_cases_task_association(session=session,
                            task_id=task_id,
                            case_ids=case_ids,
                            step_order=last_step_order)
                task.interface_task_total_cases_num += len(case_ids)
                return True
        except Exception as e:
            raise e


    

    @classmethod
    async def remove_association_interface(cls,task_id:int,interface_id:int) -> bool:
        """
        解除关联
        :param task_id: 任务ID
        :param interface_id: 接口ID
        """
        try:
            async with cls.transaction() as session:
                task = await cls.get_by_id(ident=task_id,session=session)
                await session.execute(
                    delete(InterfaceAPITaskAssociation).where(
                        and_(
                            InterfaceAPITaskAssociation.interface_task_id == task_id,
                            InterfaceAPITaskAssociation.interface_api_id == interface_id
                        )
                    )
                )
                task.interface_task_total_apis_num -= 1
                return True
        except Exception as e:
            raise e






    @classmethod
    async def remove_association_interface_case(cls,task_id:int,case_id:int) -> bool:
        """
        解除关联
        :param task_id: 任务ID
        :param case_id: 接口业务ID
        """
        try:
            async with cls.transaction() as session:
                task = await cls.get_by_id(ident=task_id,session=session)
                await session.execute(
                    delete(InterfaceCaseTaskAssociation).where(
                        and_(
                            InterfaceCaseTaskAssociation.interface_task_id == task_id,
                            InterfaceCaseTaskAssociation.interface_case_id == case_id
                        )
                    )
                )
                task.interface_task_total_cases_num -= 1
                return True
        except Exception as e:
            raise e

    @classmethod
    async def reorder_interface(cls,task_id:int,interface_ids:list[int]) -> bool:
        """
        子步骤重新排序
        :param task_id: 任务ID
        :param interface_ids: 接口ID列表
        """
        try:
            async with cls.transaction() as session:
                update_values = []
                for index, interface_id in enumerate(interface_ids, start=1):
                    update_values.append({
                        "interface_task_id": task_id,
                        "interface_api_id": interface_id,
                        "step_order": index
                    })
                await session.execute(
                    update(InterfaceAPITaskAssociation).values(
                        update_values
                    )
                )
                return True
        except Exception as e:
            raise e


    @classmethod
    async def reorder_interface_case(cls,task_id:int,case_ids:list[int]) -> bool:
        """
        子步骤重新排序
        :param task_id: 任务ID
        :param case_ids: 接口业务ID列表
        """
        try:
            async with cls.transaction() as session:
                update_values = []
                for index, case_id in enumerate(case_ids, start=1):
                    update_values.append({
                        "interface_task_id": task_id,
                        "interface_case_id": case_id,
                        "step_order": index
                    })
                await session.execute(
                    update(InterfaceCaseTaskAssociation).values(
                        update_values
                    )
                )
        except Exception as e:
            raise e



    @staticmethod
    async def get_case_last_index(task_id:int,session:AsyncSession) -> int:
        """
        获取接口业务索引
        """
        try:
            result = await session.execute(
                select(InterfaceCaseTaskAssociation.step_order).where(
                    InterfaceCaseTaskAssociation.interface_task_id == task_id
                ).order_by(
                    InterfaceCaseTaskAssociation.step_order.desc()
                ).limit(1)
            )
            last_step_order = result.scalar()  # 获取第一个结果
            # 如果查询结果为 None，则返回 0；否则返回查询到的值
            return last_step_order if last_step_order is not None else 0
        except Exception as e:
            raise e

    @staticmethod
    async def get_api_last_index(task_id:int,session:AsyncSession) -> int:

        """
        获取接口索引
        """
        try:
            result = await session.execute(
                select(InterfaceAPITaskAssociation.step_order).where(
                    InterfaceAPITaskAssociation.interface_task_id == task_id
                ).order_by(
                    InterfaceAPITaskAssociation.step_order.desc()
                ).limit(1)
            )
            last_step_order = result.scalar()  # 获取第一个结果
            # 如果查询结果为 None，则返回 0；否则返回查询到的值
            return last_step_order if last_step_order is not None else 0
        except Exception as e:
            raise e
    

    @staticmethod
    async def insert_cases_task_association(session:AsyncSession,task_id:int,case_ids:List[int],step_order:int):
        try:
            values = [
            {
                "interface_task_id": task_id,
                "interface_case_id": case_id,
                "step_order": index
            } for index, case_id in enumerate(case_ids, start=step_order + 1)
            ]
            if values:
                await session.execute(
                        insert(InterfaceCaseTaskAssociation).prefix_with("IGNORE")
                        .values(values)
                    )
        except Exception as e:
            raise e


    @staticmethod
    async def insert_interfaces_task_association(session:AsyncSession,task_id:int,interface_ids:list[int],step_order:int):
        """
        插入接口任务关联
        """
        try:
            values = [
            {
                "interface_task_id": task_id,
                "interface_api_id": interface_api_id,
                "step_order": index
            } for index, interface_api_id in enumerate(interface_ids, start=step_order + 1)
            ]
            if values:
                await session.execute(
                        insert(InterfaceAPITaskAssociation).prefix_with("IGNORE")
                        .values(values)
                    )
        except Exception as e:
            raise e