


from app.mapper import Mapper
from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
from app.model import async_session
from app.model.base.user import User
from app.model.interfaceAPIModel.interfaceGroupModel import InterfaceGroup
from app.model.interfaceAPIModel.associationModel import InterfaceGroupAPIAssociation
from app.model.interfaceAPIModel.interfaceModel import Interface
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, delete, insert, update, select

from utils import log


class InterfaceGroupMapper(Mapper[InterfaceGroup]):
    __model__ = InterfaceGroup
   

    @classmethod
    async def association_interface(cls,group_id:int,interface_id:int) -> None:
       """
       关联接口到分组
       """
       try:
            async with cls.transaction() as session:
                group = await cls.get_by_id(ident=group_id,session=session)
                if not group:
                    raise ValueError("分组不存在")
                group.interface_group_api_num +=1
                last_index = await cls.get_last_index(session=session,group_id=group_id)
                new_index = last_index + 1
                await cls.insert_association(session=session,group_id=group_id,interface_id=interface_id,step_order=new_index)
       except Exception as e:
            raise e


    
    @classmethod
    async def association_interfaces(cls,group_id:int,interface_ids:list[int]) -> None:
       """
       关联多个接口到分组
       """
       try:
            async with cls.transaction() as session:
                group = await cls.get_by_id(ident=group_id,session=session)
                if not group:
                    raise ValueError("分组不存在")
                group.interface_group_api_num += len(interface_ids)
                last_index = await cls.get_last_index(session=session,group_id=group_id)
                await cls.insert_associations(session=session,group_id=group_id,interface_ids=interface_ids,last_index=last_index)
       except Exception as e:
            raise e
    


    @classmethod
    async def copy_interface(cls,group_id:int,interface_id:int,user:User):
        """
        复制接口到分组
        """
        
        try:
            async with cls.transaction() as session:
                group = await cls.get_by_id(ident=group_id,session=session)
                if not group:
                    raise ValueError("分组不存在")

                interface = await InterfaceMapper.get_by_id(ident=interface_id,session=session)
                if not interface:
                    raise ValueError("接口不存在")
                last_index = await cls.get_last_index(session=session,group_id=group_id)

                if not interface.is_common:
                    interface = await InterfaceMapper.copy_one(
                        session=session,
                        target=interface,
                        user=user,
                        is_common=False )



                new_index = last_index + 1
                await cls.insert_association(session=session
                ,group_id=group_id,interface_id=interface.id,
                step_order=new_index)
        except Exception as e:
            log.error(e)
            raise



    @classmethod
    async def remove_association(cls,group_id:int,interface_id:int) -> None:
       """
       移除接口组-关联表
       """
       try:
            async with cls.transaction() as session:
                await session.execute(
                    delete(InterfaceGroupAPIAssociation).where(
                        and_(
                            InterfaceGroupAPIAssociation.group_id == group_id,
                            InterfaceGroupAPIAssociation.interface_id == interface_id
                        )
                    )
                )
       except Exception as e:
            raise e

    @classmethod
    async def reorder_interfaces(cls,group_id:int,interface_ids:list[int]) -> None:
       """
       子步骤重新排序
       :param group_id: 分组ID
       :param interface_ids: 接口ID列表
       """
       try:
            async with cls.transaction() as session:
                update_values = []
                for index, interface_id in enumerate(interface_ids, start=1):
                    update_values.append({
                        "step_order": index,
                        "interface_id": interface_id
                    })
                await session.execute(
                    update(InterfaceGroupAPIAssociation).where(
                        InterfaceGroupAPIAssociation.group_id == group_id
                    ).values(update_values)
                )
       except Exception as e:
            raise e


    @classmethod
    async def query_association_interfaces(cls,group_id:int) -> list[Interface]:
       """
       查询分组关联的接口
       """
       try:
            async with async_session() as session:
                result = await session.execute(
                    select(Interface).join(
                        InterfaceGroupAPIAssociation,
                        InterfaceGroupAPIAssociation.interface_id == Interface.id
                    ).where(
                        InterfaceGroupAPIAssociation.group_id == group_id
                    ).order_by(InterfaceGroupAPIAssociation.step_order)
                )
                return result.scalars().all()
       except Exception as e:
            raise e


    @classmethod
    async def remove_group(cls,group_id:int) -> bool:
       """
       移除接口组-关联表
       """
       try:
            async with cls.transaction() as session:
                await session.execute(
                   delete(Interface).where(
                        Interface.id.in_(
                            select(InterfaceGroupAPIAssociation.interface_id)
                            .where(InterfaceGroupAPIAssociation.group_id == group_id)
                        ),
                        Interface.is_common == 0  # 非公共
                    )
                )

                group = await cls.get_by_id(ident=group_id,session=session)
                if not group:
                    return False
                await session.delete(group)
                return True
       except Exception as e:
            raise e



    @classmethod
    async def get_last_index(cls,session:AsyncSession,group_id:int) -> int:
       """
       获取分组的最后一个接口索引
       """
       try:
            result = await session.execute((
            select(InterfaceGroupAPIAssociation.step_order).where(
                InterfaceGroupAPIAssociation.group_id == group_id
            ).order_by(InterfaceGroupAPIAssociation.step_order.desc()).limit(1)
            ))
            last_step_order = result.scalar()  # Fetch the first (and only) result
            return last_step_order or 0
       except Exception as e:
            raise e
    
    @classmethod
    async def insert_association(cls,session:AsyncSession,group_id:int,interface_id:int,step_order:int) -> None:
       """
       插入接口组-关联表
       """
       try:
           await session.execute(
                insert(InterfaceGroupAPIAssociation).prefix_with("IGNORE").values(
                    group_id=group_id,
                    interface_id=interface_id,
                    step_order=step_order
                )
           )
       except Exception as e:
            raise e
    
    @classmethod
    async def insert_associations(cls,session:AsyncSession,group_id:int,interface_ids:list[int],last_index:int) -> None:
       """
       插入接口组-关联表
       """
       try:
           values = [
                {
                    "group_id": group_id,
                    "interface_id": interface_id,
                    "step_order":  index
                }
                for  index, interface_id in enumerate(interface_ids,start=last_index+1)
            ]
           # 忽略重复插入
           await session.execute(
                insert(InterfaceGroupAPIAssociation).prefix_with("IGNORE").values(values)
           )
       except Exception as e:
            raise e