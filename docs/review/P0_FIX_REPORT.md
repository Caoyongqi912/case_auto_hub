# P0 修复完成报告

日期:2026-06-19
审查文档:`docs/review/run_interface_case_deep_review.md` (V2)
执行计划:`docs/superpowers/plans/2026-06-18-interface-case-runner-p0-hardening.md`

## 已修复 BUG 清单

### 模型层 (3)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **M1** target_id ClassVar | 严重 | 删除 `InterfaceCaseContents.target_id: ClassVar`,`to_dict` 的 mapper 循环改用 `mapper is base_mapper: continue`,子类列不再丢失 |
| **M2** case_title 长度 | 严重 | `interface_case_name` 20→64,`interface_case_desc` 50→255 |
| **M3** BaseModel JTI | 严重 | `BaseModel.to_dict/map/copy_map` 改用 `sqlalchemy.inspect(cls).mapper.columns`;`InterfaceCaseContentResult.to_dict` 同步修 mapper 循环 |
| **M11** uid 长度 | 低 | `interface_uid` / `interface_case_uid` / `task_uid` 全部 20/10 → 50 |

### 流程层 (3)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **F1** interfaceLog 字段名 | 严重 | 删除 `runner.py:225` 错误的 camelCase 赋值,日志走 `finalize_case_result(logs=...)` |
| **F2** 早返 None | 严重 | `runner.py` 两处早返路径显式 `return False, None`,task 模式 `success, _ = await ...` 不再 TypeError |
| **F3** init_global_headers | 中 | 删死代码 / 日志用实际数量 / `or []` 改 `list()` / 返回类型从 `Optional[List]` 改 `List` |

### 资源管理 (2)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **D1** result_writer 单例 | 严重 | `ResultWriter.clear_cache()`;`InterfaceRunner` 自建实例注入 `__slots__`;`finally` 清缓存;所有模块单例引用改 `self.result_writer` |
| **E1** HttpxClient 资源 | 严重 | `__call__` 不再 `self.client.timeout = ...` 改用 kwargs 传 `timeout=`;`InterfaceExecutor.aclose()` + `run_interface_case` finally 调用 |

### 安全 (3)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **S1** getattr 沙箱逃逸 | 严重 | `DISALLOWED_ATTRS` 加 `getattr/setattr/delattr/vars/dir`;Attribute 任意 `__*` 拒绝;Call 当 func 是 Attribute 时也按 attr 名拦 |
| **S2** import 沙箱 | 中 | `ALLOWED_NODE_TYPES` 移除 `ast.Import/ImportFrom/alias` |
| **S3** SCRIPT_TIMEOUT 强制 | 严重 | `multiprocessing.spawn` 子进程跑脚本,主进程 `proc.join(timeout)`,超时 `terminate → kill`,抛 `ScriptSecurityError` |

### 变量 (1)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **V1** name mangling | 中 | `__find_g_vars` → `_find_g_vars`,`VariableTrans` 子类可正常 override |

## 测试统计

- **新增测试文件**: 13
- **新增测试用例**: 29
- **测试结果**: 29 passed in ~6s
- **覆盖 BUG**: 12/12 (M1/M2/M3/M11/F1/F2/F3/D1/E1/S1/S2/S3/V1)

## 计划外发现

在执行计划过程中,Plan 描述有几处偏差,实际修复范围略大于 Plan:

1. **M1**:Plan 假设"to_dict 永远拿到 None",但实际子类 Column 会接管,mapping 循环会把子类列补回去。真正的问题:
   - ClassVar 本身是 code smell(introspection 工具会误判)
   - 映射循环的过滤条件 `mapper.local_table.name != self.__tablename__` 在子类实例上等于过滤自己,导致子类列丢失
   - 修法:删 ClassVar + 改条件为 `mapper is base_mapper: continue`

2. **M3**:Plan 只说改 `BaseModel.to_dict`,但测试用例走的是 `InterfaceCaseContentResult.to_dict`(同一类孪生 bug),需要同步修。

3. **F3**:Plan 说"`self.interface_executor.g_headers` 从未被赋值",实际赋值是对的,bug 只是日志里 `len(self.global_headers)` 恒为 0(实例字段没更新)。

4. **S1**:Plan 的修复代码漏了把 `getattr/setattr` 加进 `DISALLOWED_ATTRS`,导致 `getattr("", "__class__")` 仍然能逃逸。补充完整。

## 兼容性 / 注意事项

- **所有 SQL 长度变更需要 alembic 或手 ALTER**:项目无 alembic,生产需手动:
  - `ALTER TABLE interface_case_result MODIFY interface_case_name VARCHAR(64), MODIFY interface_case_desc VARCHAR(255);`
  - `ALTER TABLE interface_result MODIFY interface_uid VARCHAR(50);`
  - `ALTER TABLE interface_case_result MODIFY interface_case_uid VARCHAR(50);`
  - `ALTER TABLE interface_task_result MODIFY task_uid VARCHAR(50);`

- **multiprocessing 子进程**:Windows / macOS / Linux 都用 `spawn` 上下文,行为一致。子进程入口 `_exec_in_subprocess` 必须在模块顶层(可 pickle),不能是 lambda/闭包。

- **基础配置 `config.py` 始终未动**,用户的 MySQL 密码修改保留在工作区。

- **CR 换行顺手清掉**:`app/model/basic.py` 和 `common/httpxClient.py` 和 `utils/variableTrans.py` 原本用 CR 换行,统一改为 LF。
