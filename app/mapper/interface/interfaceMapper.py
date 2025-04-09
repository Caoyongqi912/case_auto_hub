#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceMapper# @Software: PyCharm# @Desc:import asynciofrom typing import List, Sequence, Dict, Anyfrom sqlalchemy import select, insert, and_, delete, updatefrom sqlalchemy.ext.asyncio import AsyncSessionfrom app.mapper import Mapperfrom app.mapper.interface.interfaceGroupMapper import InterfaceGroupMapperfrom app.mapper.project.moduleMapper import ModuleMapperfrom app.model import async_sessionfrom app.model.base import Userfrom app.model.base.module import Modulefrom app.model.interface import InterfaceModel, InterFaceCaseModel, InterCaseAssociation, InterfaceGroupModelfrom app.model.interface.interfaceScriptDescModel import InterfaceScriptDescfrom enums import ModuleEnumfrom interface.recoder import Recordfrom utils import MyLogurulog = MyLoguru().get_logger()class InterfaceMapper(Mapper):    __model__ = InterfaceModel    @classmethod    async def set_interfaces_modules(cls, module_id: int, interfaces: List[int]):        """        设置接口 所属模块        """        try:            async with async_session() as session:                async with session.begin():                    stmts = [                        update(InterfaceModel).where(                            InterfaceModel.id == interface                        ).values(                            module_id=module_id                        )                        for interface in interfaces]                    await asyncio.gather(*[session.execute(stmt) for stmt in stmts])        except Exception as e:            raise e    @classmethod    async def upload(cls, apis: List[Dict[str, Any]], project_id: str, module_id: str, env_id: str, creator: User):        """        批量上传 API 数据并插入到数据库。        :param apis: API 数据列表        :param project_id: 项目 ID        :param module_id: 父级 Module ID        :param env_id: 环境 ID        :param creator: 创建者用户对象        :return: None        """        try:            async with async_session() as session:                async with session.begin():                    # 提取并插入 Module                    module_names = [api.pop("module") for api in apis]                    modules = []                    for name in set(module_names):                        modules.append(await cls.insert_module(name, session, int(module_id), int(project_id), creator))                    # 插入 API 数据                    api_tasks = [                        cls.insert_inter_with_semaphore(session,                                                        int(project_id),                                                        int(env_id),                                                        modules[index], creator, api["data"])                        for index, api in enumerate(apis)                    ]                    await asyncio.gather(*api_tasks, return_exceptions=True)        except Exception as e:            log.error(f"Error in upload method: {e}")            raise    @staticmethod    async def insert_inter_with_semaphore(            session: AsyncSession, project_id: int, env_id: int, module_id: int, creator: User,            data: List[Dict[str, Any]]    ):        """        插入 API 数据到数据库，使用 Semaphore 控制并发度。        :param session: 数据库会话        :param project_id: 项目 ID        :param env_id: 环境 ID        :param module_id: module_id        :param creator: 创建者用户对象        :param data: API 数据列表        """        semaphore = asyncio.Semaphore(5)  # 同时最多允许5个并发任务        async with semaphore:            try:                for api_data in data:                    api_data.update({                        "project_id": project_id,                        "env_id": env_id,                        "module_id": module_id,                        "creator": creator.id,                        "creatorName": creator.username,                        "status": "DEBUG",                        "level": "P1",                    })                    api = InterfaceModel(**api_data)                    session.add(api)            except Exception as e:                log.error(f"Error in insert_inter_with_semaphore: {e}")                raise    @staticmethod    async def insert_module(            module_name: str, session: AsyncSession, parent_id: int, project_id: int, creator: User    ) -> int:        """        :param module_name: 部门 名称        :param session: 数据库会话        :param parent_id: 父级 部门 ID        :param project_id: 项目 ID        :param creator: 创建者用户对象        :return: 插入的 部门 ID        """        try:            # 获取父级 Module 和子 module 是否存在            parent_module = await ModuleMapper.get_by_id(parent_id, session)            _exist = await  session.execute(                select(Module).where(                    and_(                        Module.project_id == parent_id,                        Module.title == module_name,                        Module.module_type == ModuleEnum.API                    )                )            )            existing_module: Module = _exist.scalar_one_or_none()            if existing_module and module_name == existing_module.title:                log.debug(f"子部门 '{module_name}' 已存在")                return existing_module.id            # 创建新的部门            child_module = Module(                title=module_name,                project_id=project_id,                parent_id=parent_module.id,                creator=creator.id,                creatorName=creator.username            )            session.add(child_module)            await session.flush()            return child_module.id        except Exception as e:            log.error(f"Error in child_module : {e}")            raise    @classmethod    async def remove(cls, interId: int):        """            删除api接口            关联删除处理            api task association            api group association            api case association        """        try:            async with async_session() as session:                async with session.begin():                    api = await cls.get_by_id(interId, session)                    from .interfaceTaskMapper import InterfaceTaskMapper                    await InterfaceTaskMapper.set_task_when_api_remove(session, interId)                    await InterfaceGroupMapper.set_group_when_api_remove(session, interId)                    await InterfaceCaseMapper.set_case_when_api_remove(session, interId)                    await session.delete(api)                    await session.flush()        except Exception as e:            raise e    @staticmethod    async def copy_record_2_api(recordId: str, creator: User):        """        录制转API        """        try:            recordInfos = await Record.query_record(creator.uid)            if not recordInfos:                raise Exception("未查询到录制信息")            for record in recordInfos:                if record.get("uid") == recordId:                    kwargs = {                        "env_id": -1,                        "url": record['url'],                        "desc": record['url'],                        "method": record['method'],                        "headers": record['headers'],                        "params": record['params'],                        "data": record['data'],                        "body": record['body'],                        "body_type": record['body_type']                    }                    return kwargs        except Exception as e:            raise e    @classmethod    async def save_record(cls, creatorUser: User, recordId: str, **kwargs):        """        录制转API        """        try:            record = await cls.copy_record_2_api(recordId, creatorUser)            kwargs.update(record)            return await cls.save(creatorUser=creatorUser, **kwargs)        except Exception:            raise    @classmethod    async def copy_api(cls, apiId: int, creator: User, session: AsyncSession = None,                       is_copy_name: bool = False, is_common: bool = False) -> "InterfaceModel":        """        复制API        :param apiId: 待复制API        :param creator: 创建人        :param session: session        :param is_copy_name: 复制api name        :param is_common: 复制api  common        """        try:            # 封装为一个内部函数，减少重复代码            async def copy_api_logic(logic_session: AsyncSession):                target_api = await cls.get_by_id(ident=apiId, session=logic_session)                target_api_map = target_api.map                if not is_copy_name:                    target_api_map['name'] = target_api_map['name'] + "(副本)"                new_api = cls.__model__(                    **target_api_map,                    creator=creator.id,                    creatorName=creator.username                )                new_api.is_common = is_common                await cls.add_flush_expunge(logic_session, new_api)                return new_api            # 使用一个session上下文管理器，如果没有传入session则创建一个            if session is None:                async with async_session() as session:                    async with session.begin():                        return await copy_api_logic(session)            else:                # 如果传入了session，直接使用它                return await copy_api_logic(session)        except Exception as e:            raise e    @classmethod    async def query_added(cls, beginTime: str, endTime: str):        """查询新增"""        try:            async with async_session() as session:                sql = select(InterfaceModel).join(Module,                                                  InterfaceModel.module_id == Module.id                                                  ).where(                    and_(                        InterfaceModel.create_time >= beginTime,                        InterfaceModel.create_time <= endTime                    )                )                sca = await session.scalars(sql)                data = sca.all()                return data        except Exception as e:            raise e    @staticmethod    async def new_api_2_group(session: AsyncSession, group: InterfaceGroupModel) -> InterfaceModel:        try:            api = InterfaceModel(                name=group.name,                description=group.description,                project_id=group.project_id,                module_id=group.module_id,                is_common=False,                is_group=True,                group_id=group.id,                method="GROUP",                status="DEBUG",                level="P2",                url="-",                body_type=0            )            await InterfaceMapper.add_flush_expunge(session, api)            return api        except Exception as e:            raise eclass InterfaceCaseMapper(Mapper):    __model__ = InterFaceCaseModel    @classmethod    async def append_record(cls, creatorUser: User, recordId: str, caseId: int):        """        录制 append 用例        """        try:            case: InterFaceCaseModel = await cls.get_by_id(ident=caseId)            if not case:                raise Exception("用例不存在")            recordApi = await InterfaceMapper.copy_record_2_api(recordId, creatorUser)            recordApi['name'] = recordApi['url'][:5] + '...'            recordApi['desc'] = f"{recordApi['method']} : {recordApi['url']} "            recordApi['is_common'] = 0            recordApi['status'] = "DEBUG"            recordApi['level'] = "P2"            recordApi['project_id'] = case.project_id            recordApi['module_id'] = case.module_id            api = await InterfaceMapper.save(creatorUser=creatorUser, **recordApi)            return await cls.add_api(                caseId=case.id,                apiId=api.id            )        except Exception as e:            raise e    @classmethod    async def remove_api(cls, caseId: int, apiId: int):        """        删除关联的api        if common 解除关联        """        try:            async with async_session() as session:                async with session.begin():                    caseApi: InterFaceCaseModel = await cls.get_by_id(ident=caseId, session=session)                    api: InterfaceModel = await InterfaceMapper.get_by_id(ident=apiId, session=session)                    # 删除关联表数据                    await session.execute(delete(InterCaseAssociation).where(                        InterCaseAssociation.inter_case_id == caseId,                        InterCaseAssociation.interface_id == apiId                    ))                    # 非公共用例直接删除                    if not api.is_common:                        await session.delete(api)                    # 中间表重新排序                    apis = await session.execute(                        select(InterfaceModel).join(                            InterCaseAssociation,                            InterCaseAssociation.interface_id == InterfaceModel.id                        ).where(                            InterCaseAssociation.inter_case_id == caseId                        ).order_by(                            InterCaseAssociation.step_order                        )                    )                    apis = apis.scalars().all()                    caseApi.apiNum = len(apis)                    for index, api in enumerate(apis, start=1):                        sql = update(InterCaseAssociation).where(                            and_(                                InterCaseAssociation.inter_case_id == caseId,                                InterCaseAssociation.interface_id == api.id                            )                        ).values(step_order=index)                        await session.execute(sql)        except Exception as e:            raise e    @classmethod    async def reorder_apis(cls, caseId: int, apiIds: List[int]):        """        关联api 重新排序        """        try:            async with async_session() as session:                async with session.begin():                    for index, api in enumerate(apiIds, start=1):                        sql = update(InterCaseAssociation).where(                            and_(                                InterCaseAssociation.inter_case_id == caseId,                                InterCaseAssociation.interface_id == api                            )                        ).values(step_order=index)                        await session.execute(sql)        except Exception as e:            raise e    @classmethod    async def query_interface_by_caseId(cls, caseId: int) -> List[InterfaceModel]:        """        根据接口id查询        """        try:            async with async_session() as session:                apis = await session.scalars(                    select(InterfaceModel).join(                        InterCaseAssociation,                        InterCaseAssociation.interface_id == InterfaceModel.id                    ).where(                        InterCaseAssociation.inter_case_id == caseId                    ).order_by(                        InterCaseAssociation.step_order                    )                )                return apis.all()        except Exception as e:            log.exception(e)            raise e    @classmethod    async def add_api(cls, caseId: int, apiId: int):        """        case 添加单个 api        """        try:            async with async_session() as session:                async with session.begin():                    api_case = await cls.get_by_id(ident=caseId, session=session)                    api_case.apiNum += 1                    last_step_index = await cls.get_last_index(session, caseId)                    await session.execute((insert(InterCaseAssociation).values(                        dict(                            interface_id=apiId,                            inter_case_id=caseId,                            step_order=last_step_index + 1                        )                    )))        except Exception as e:            log.error(e)            raise e    @classmethod    async def add_common_apis(cls, caseId: int, commonApis: List[int]):        """        case 关联 common api        """        try:            async with async_session() as session:                async with session.begin():                    api_case = await cls.get_by_id(ident=caseId, session=session)                    api_case.apiNum += len(commonApis)                    last_step_index = await cls.get_last_index(session, caseId)                    await session.execute(                        insert(InterCaseAssociation),                        [                            {                                'interface_id': apiId,                                'inter_case_id': caseId,                                'step_order': index                            }                            for index, apiId in enumerate(commonApis, start=last_step_index + 1)                        ]                    )        except Exception as e:            raise e    @classmethod    async def copy_common_apis(cls, caseId: int, commonApis: List[int], cr: User):        """        case 复制添加common api        """        try:            async with async_session() as session:                async with session.begin():                    if not commonApis:                        return                    new_apis = []                    api_case = await cls.get_by_id(ident=caseId, session=session)                    for api in commonApis:                        new_api = await InterfaceMapper.copy_api(apiId=api, creator=cr,                                                               is_copy_name=True,                                                               is_common=False,                                                               session=session)                        new_apis.append(new_api)                    last_step_index = await cls.get_last_index(session, caseId)                    api_case.apiNum += len(new_apis)                    await session.execute(                        insert(InterCaseAssociation),                        [                            {                                'interface_id': new_api.id,                                'inter_case_id': caseId,                                'step_order': index                            }                            for index, new_api in enumerate(new_apis, start=last_step_index + 1)                        ]                    )        except Exception as e:            raise e    @classmethod    async def copy_case(cls, caseId: int, creator: User):        """        复制用例        """        try:            async with async_session() as session:                async with session.begin():                    targe_case: InterFaceCaseModel = await cls.get_by_id(ident=caseId, session=session)                    target_api_map = targe_case.map                    target_api_map['title'] = target_api_map['title'] + "(副本)"                    new_case = InterFaceCaseModel(                        **target_api_map,                        creator=creator.id,                        creatorName=creator.username                    )                    await cls.add_flush_expunge(session, new_case)                    apiIds = await session.scalars(select(InterCaseAssociation).where(                        InterCaseAssociation.inter_case_id == caseId                    ).order_by(InterCaseAssociation.step_order.desc()))                    apiIds = apiIds.all()                    if apiIds:                        new_apis = []                        for ident in apiIds:                            new_api: InterfaceModel = await InterfaceMapper.copy_api(ident,                                                                                   session=session,                                                                                   is_copy_name=True,                                                                                   creator=creator)                            new_apis.append(new_api)                        for index, api in enumerate(new_apis, start=1):                            await session.execute(insert(InterCaseAssociation).values(                                dict(                                    interface_id=api.id,                                    inter_case_id=new_case.id,                                    step_order=index                                )))                        await session.flush()        except Exception as e:            log.error(e)            raise e    @classmethod    async def copy_case_api(cls, caseId: int, apiId: int, copyer: User):        """        复制用例中api 关联添加到底部        """        try:            async with async_session() as session:                async with session.begin():                    case = await cls.get_by_id(ident=caseId, session=session)                    case.apiNum += 1                    new_api = await InterfaceMapper.copy_api(apiId=apiId, creator=copyer,                                                           session=session)                    last_step_index = await cls.get_last_index(session, caseId)                    await session.execute((insert(InterCaseAssociation).values(                        dict(                            interface_id=new_api.id,                            inter_case_id=caseId,                            step_order=last_step_index + 1                        )                    )))        except Exception as e:            raise e    @staticmethod    async def get_last_index(session: AsyncSession, caseId: int) -> int:        try:            sql = (                select(InterCaseAssociation.step_order).where(                    InterCaseAssociation.inter_case_id == caseId                ).order_by(InterCaseAssociation.step_order.desc()).limit(1)            )            result = await session.execute(sql)            last_step_order = result.scalar()  # Fetch the first (and only) result            return last_step_order or 0        except Exception as e:            raise e    @classmethod    async def add_group_step(cls, caseId: int, groupIds: List[int]):        """        添加分组        """        try:            async with async_session() as session:                async with session.begin():                    case: InterFaceCaseModel = await cls.get_by_id(ident=caseId, session=session)                    case.apiNum += len(groupIds)                    last_step_index = await cls.get_last_index(session, caseId)                    for index, groupId in enumerate(groupIds, start=last_step_index + 1):                        group = await InterfaceGroupMapper.get_by_id(session=session, ident=groupId)                        # 需要创建一个 api 关联 group                        api = await InterfaceMapper.new_api_2_group(session, group=group)                        await session.execute((insert(InterCaseAssociation).values(                            dict(                                interface_id=api.id,                                inter_case_id=caseId,                                step_order=index                            )                        )))        except Exception as e:            raise e    @classmethod    async def remove_case(cls, caseId: int):        """        逻辑删除        删除关联 非公共api        删除关联 group        删除关联 task        :param caseId:        :return:        """        log.info(f"删除用例 {caseId}")        try:            async with async_session() as session:                async with session.begin():                    case = await cls.get_by_id(ident=caseId, session=session)                    log.info(f"删除用例 {case}")                    # 查询关联API                    stmt = await session.execute(                        select(InterfaceModel).join(                            InterCaseAssociation,                            InterCaseAssociation.interface_id == InterfaceModel.id                        ).where(                            InterCaseAssociation.inter_case_id == caseId                        )                    )                    apis = stmt.scalars().all()                    log.debug(apis)                    # 删除API 所有关联                    await session.execute(                        delete(InterCaseAssociation).where(                            InterCaseAssociation.inter_case_id == caseId                        )                    )                    # 删除任务关联                    from app.mapper.interface import InterfaceTaskMapper                    await  InterfaceTaskMapper.set_task_when_case_remove(session, caseId)                    # 删除所有非公共 API                    private_api_ids = [api.id for api in apis if not api.is_common]                    if private_api_ids:                        await session.execute(                            delete(InterfaceModel).where(InterfaceModel.id.in_(private_api_ids))                        )                        log.info(f"Deleted non-common APIs for case {caseId}: {private_api_ids}")                    await session.delete(case)        except Exception as e:            raise e    @staticmethod    async def set_case_when_api_remove(session: AsyncSession, apiId: int):        try:            stmt = await session.scalars(select(InterFaceCaseModel.id).join(                InterCaseAssociation,                InterCaseAssociation.inter_case_id == InterFaceCaseModel.id            ).where(                InterCaseAssociation.interface_id == apiId            ))            cases_ids: Sequence[InterFaceCaseModel.id] = stmt.all()            await session.execute(                update(InterFaceCaseModel).where(                    InterFaceCaseModel.id.in_(cases_ids)                ).values(                    apiNum=InterFaceCaseModel.apiNum - 1                )            )            await session.execute(                delete(InterCaseAssociation).where(                    InterCaseAssociation.interface_id == apiId                )            )        except Exception as e:            raise eclass InterfaceScriptMapper(Mapper):    __model__ = InterfaceScriptDescclass InterfaceFuncMapper(Mapper):    __model__ = InterfaceScriptDesc__all__ = ['InterfaceMapper', 'InterfaceCaseMapper', 'InterfaceScriptMapper',"InterfaceFuncMapper"]