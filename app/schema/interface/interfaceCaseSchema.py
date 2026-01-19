import json
from typing import List, Union
from pydantic.v1 import root_validator
from app.schema import PageSchema
from pydantic import BaseModel
from app.schema.interface.interfaceApiSchema import IBeforeSqlExtracts
from enums import ModuleEnum
from enums.CaseEnum import LoopTypeEnum


class InterfaceCaseSchema(BaseModel):
    id: int | None = None
    uid: str | None = None
    title: str | None = None
    desc: str | None = None
    level: str | None = None
    status: str | None = None
    module_id: int | None = None
    project_id: int | None = None


class InsertInterfaceCaseBaseInfoSchema(InterfaceCaseSchema):
    title: str
    desc: str
    level: str
    status: str
    module_id: int
    project_id: int


class OptionInterfaceCaseSchema(InterfaceCaseSchema):
    id: int


class ExecuteInterfaceCaseSchema(BaseModel):
    case_id: int
    env_id: int
    error_stop: bool


class PageInterfaceCaseSchema(InterfaceCaseSchema, PageSchema):
    module_type: int = ModuleEnum.API_CASE


class AssociationApisSchema(BaseModel):
    interface_case_id: int
    interface_id_list: List[int]


class AssociationApiSchema(BaseModel):
    case_id: int
    module_id: int
    project_id: int


class UpdateCaseContentAssert(BaseModel):
    assert_key: str
    assert_value: str
    assert_type: int


class AddInterfaceCaseCommonGROUPSchema(BaseModel):
    interface_case_id: int
    api_group_id_list: List[int]


class AddInterfaceApi2Case(BaseModel):
    caseId: int
    apiId: int


class RemoveCaseContentSchema(BaseModel):
    case_id: int
    content_step_id: int


class ReorderContentStepSchema(BaseModel):
    case_id: int
    content_step_order: List[int]


class AssociationConditionSchema(BaseModel):
    interface_case_id: int


class AssociationConditionAPISchema(BaseModel):
    condition_id: int
    interface_id_list: List[int]


class AssociationLoopAPISchema(BaseModel):
    loop_id: int
    interface_id_list: List[int]


class AssociationLoopAPISchema(BaseModel):
    loop_id: int
    interface_id_list: List[int]


class RemoveAssociationConditionAPISchema(BaseModel):
    condition_id: int
    interface_id: int


class RemoveAssociationLoopAPISchema(BaseModel):
    loop_id: int
    interface_id: int


class ConditionAddGroups(BaseModel):
    condition_api_id: int
    group_id_list: List[int]


class ConditionAddCommons(BaseModel):
    condition_api_id: int
    common_api_list: List[int]


class CopyContentStepSchema(BaseModel):
    case_id: int
    content_id: int


class UpdateConditionSchema(BaseModel):
    id: int
    condition_key: str
    condition_value: str | None = None
    condition_operator: int


class UpdateDBSchema(BaseModel):
    id: int
    sql_text: str | None = None
    sql_extracts: List[IBeforeSqlExtracts] | None = None
    db_id: int | None = None


class LoopCondition(BaseModel):
    key: str
    value: str
    operate: int


class AssociationLoopSchema(BaseModel):
    case_id: int
    loop_type: int
    loop_interval: Union[int] = None
    loop_times: Union[int] = None
    loop_items: Union[str] = None
    loop_item_key: Union[str] = None

    loop_condition: Union[LoopCondition] = None
    max_loop: Union[int] = None

    @root_validator(pre=True)
    def validate_loop_type(cls, values):
        lt = values.get("loop_type")

        match lt:
            case LoopTypeEnum.LoopItems:
                loop_items = values.get("loop_items")
                loop_item_key = values.get("loop_item_key")
                if loop_items is None or (isinstance(loop_items, str) and not loop_items.strip()):
                    raise ValueError("loop_items 不能为空")
                if loop_item_key is None:
                    raise ValueError("loop_item_key 不能为空")
                # 尝试解析为JSON或逗号分隔的列表
                try:
                    # 先尝试解析为JSON
                    items = json.loads(loop_items)
                    if not items:  # 空列表或空对象
                        raise ValueError("loop_items 不能为空列表")
                except json.JSONDecodeError:
                    # 如果不是JSON，检查是否是逗号分隔的列表
                    items = [item.strip() for item in loop_items.split(',') if item.strip()]
                    if not items:
                        raise ValueError("loop_items 必须包含至少一个有效的项")
            case LoopTypeEnum.LoopTimes:
                loop_times = values.get("loop_times")
                if loop_times is None or isinstance(loop_times, int):
                    raise ValueError("loop_times 不能为空")
            case LoopTypeEnum.LoopCondition:
                # 当 loop_type 为 WhileCondition 时，验证 loop_condition
                loop_condition = values.get("loop_condition")
                max_loop = values.get("max_loop")

                if loop_condition is None:
                    raise ValueError("loop_condition 不能为空")

                if max_loop is None:
                    raise ValueError("max_loop 不能为空")
                # 如果提供的是字典，验证它
                if isinstance(loop_condition, dict):
                    try:
                        # 尝试创建 LoopCondition 实例来验证
                        LoopCondition(**loop_condition)
                    except Exception as e:
                        raise ValueError(f"无效的 loop_condition: {e}")

        return values


class UpdateLoopSchema(AssociationLoopSchema):
    case_id: Union[ int] = None
    id: int
    loop_type: int
    loop_interval: Union[int] = None
    loop_times: Union[int] = None
    loop_items: Union[str] = None
    loop_item_key: Union[str] = None


class UpdateCaseContentStepSchema(BaseModel):
    id: int
    content_name: str | None = None
    enable: bool = None
    api_wait_time: int = None
    api_script_text: str = None
    api_assert_list: List[UpdateCaseContentAssert] = None


class AddCaseContentStepSchema(BaseModel):
    case_id: int
    content_type: int
    enable: bool = None
    api_wait_time: int = None
    api_script_text: str = None
    api_assert_list: List[UpdateCaseContentAssert] = None
