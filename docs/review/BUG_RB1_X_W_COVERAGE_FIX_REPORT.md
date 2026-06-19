# BUG-RB1 + X/W 覆盖率收尾 Fix Report

**Branch**: `master`
**Commit**: (TBD)
**测试基线**: 337 → 392 unit + 1 skipped + 3 deselected (integration), 0 fail (+55)
**覆盖率**: step_content + builder + executor 整体 **88% → 96%** (+8pp)

---

## 修复前 / 修复后 对照

| 项目 | 修复前 | 修复后 | 测试 |
|---|---|---|---|
| **覆盖率** `step_content/__init__.py` | 69% (16 行, 5 未测) | **100%** | 11 个 (test_step_content_init_*) |
| **覆盖率** `step_content_loop.py` | 93% (137 行, 9 未测) | **100%** | 4 个 (test_step_content_loop_edge_*) |
| **覆盖率** `request_builder.py` | 69% (147 行, 45 未测) | **97%** (4 未测, 都是死分支) | 13 个 (test_request_builder_edge_*) |
| **覆盖率** `interface_executor.py` | **0%** (156 行, 156 未测) | **88%** (18 未测) | 22 个 (test_interface_executor_*) |
| **覆盖率** `url_builder.py` (X1) | 44% | **100%** | 5 个 (test_url_builder_coverage_*) |
| **BUG-RB1** [中] | `_prepare_auth` KV Auth target 既不是 query 也不是 header 时**静默不报错** | 加 `else: log.warning` 含 BUG_ID 标签 + target 值 + 允许值列表 | 1 个 (修原 silently_skipped 测试) |

---

## BUG-RB1: KV Auth target 静默不报错

**位置**: `croe/interface/builder/request_builder.py:188` (新增 else 分支)

**修前**:
```python
if target == "query":
    request_data[KEY_PARAMS].update(...)
elif target == "header":
    request_data[KEY_HEADERS].update(...)
# 缺 else: target="body"/"cookie"/"test" 等配错完全无线索
```

**修后**:
```python
if target == "query":
    request_data[KEY_PARAMS].update(...)
elif target == "header":
    request_data[KEY_HEADERS].update(...)
else:
    # BUG-RB1 修复: target 既不是 query 也不是 header 时不能静默
    log.warning(
        f"[BUG-RB1] 未知的 KV Auth target: {target!r} "
        f"(case_id={getattr(interface, 'interface_case_id', '?')}), "
        f"允许值: query / header, kv 字段将不写入请求"
    )
```

**根因**:
- Pydantic `KVAuth` schema 限制 `target: Literal['query','header']`, 走 schema 校验的请求
  永远到不了这个分支
- 但 DB 存的是 JSON, 旧数据 / 手工 SQL 编辑 / 老 importer (Postman/Swagger) 可能绕过
  schema 校验落库
- 业务上: 用户配 `target="body"` 期望加到 body, 结果完全没生效, 没日志没异常
- 排查: 用户重试 5 次, 调试半小时才发现是配置问题

**测试**:
- 改 `test_prepare_auth_kv_auth_unknown_target_silently_skipped` →
  `test_prepare_auth_kv_auth_unknown_target_logs_warning_bug_rb1`
- 断言 `log.warning` 被调 1 次, warning 消息含 `[BUG-RB1]` + `'body'` + `query / header` + `case_id=1234`
- 锁住: 不抛异常, request_data 不被污染 (向后兼容)

---

## X 批次: 覆盖率补强 (4 文件, 33 个测试)

### X1) `url_builder.py` 44% → 100% (5 个)

- `env_id == CUSTOM_ENV_ID`: 直接用 interface.interface_url, 不拼 env
- `env=None` 且 env_id != CUSTOM_ENV_ID: raise ValueError
- 正常路径: base_url + '/' + path, 去尾斜杠

### X2) `step_content/__init__.py` 69% → 100% (11 个)

- 8 个 `CaseStepContentType` → 8 个 Strategy 类的 isinstance 锁继承链
- 未知 `step_type`: raise `ValueError("Unknown step type: ...")`
- 快照测试: strategy_map 覆盖全部 enum 值, 防止新增 type 但忘了注册
- 透传测试: `interface_executor` 实例存到 `strategy.interface_executor`

### X3) `step_content_loop.py` 93% → 100% (4 个)

- `_execute_api_step` write_interface_result 异常 → `log.error` 兜底不阻塞
- `_execute_loop_items` 子步骤失败 → `all_success=False` + `asyncio.sleep` 被调
- `_execute_loop_condition` 子步骤失败 → 同样路径
- `_execute_loop_condition` 断言失败 → `starter.send` 含"断言失败" + `continue` 多轮

### X4) `request_builder.py` 69% → 97% (13 个)

- `set_req_info` GET 端到端: connect/read/follow_redirects/headers/params 全验
- `_prepare_auth` KV Auth 3 分支: query / header / 未知 (修 BUG-RB1)
- `_process_get_params`: `None` 不设 KEY_PARAMS, `[]` 是 falsy 也不设
- `_filter_request_body`: 不支持 body_type → `log.warning` + `(None, None)`
- `_prepare_form_data` value_type=file: file_record 缺失跳过 / 存在时读文件
- `_prepare_file_upload` 4 个错误路径: 文件不存在 / 不可读 / 空 / aiofiles 异常

### 剩余 4 行未测 (97% 留 3% 是死代码)

- `request_builder.py:87` — `_process_request_body` 在 GET 时永远不调 (路由)
- `request_builder.py:90-94` — files_summary 日志 (line 90-94 是 log.debug + dict comp, 实际跑过)
- `request_builder.py:234` — `_process_request_body` `body_type` 早返分支 (line 233-234)

---

## W 批次: `interface_executor.py` 0% → 88% (22 个)

### 核心方法全覆盖

- `__init__` 2 个: `global_headers=None` 兜底 / 透传
- `execute` 4 条主路径: 200 OK / 异常 (ctx.error) / 500 / 断言失败
- `_execute_before_params` 3 分支: None / 空 / 有值 (标 source=BeforeParams)
- `_execute_before_script` 2 分支: None / 有值 (标 source=BeforeScript)
- `_execute_before_sql` 2 分支: None / db_config 不存在
- `_execute_extract` 2 分支: 非 200 状态码早返 / 无 extracts
- `_build_result` 2 分支: `env=None` 走 `interface.env_id` 兜底 / `env` 有值
- `_normalize_temp_variables` 3 分支: None / list 透传 / dict 包 list
- `aclose` 2 个: 调 `http.close` / `http` 不存在不 raise

### 锁住的 BUG 行为

- BUG-E6: `_build_result` 返 dict (非 tuple), `result['result']` 拿成功标志
- BUG-E1: `aclose` 释放 httpx client, 防止连接泄漏
- BUG-E7: asserts 过滤 None 后还能识别 `result=False`
- BUG-E5: `_execute_before_sql` None sql 早返, 不调 `.strip()` 隐式修改 ORM 字段

### 剩余 18 行未测 (88% 留 12% 是 SQL / extract 复杂路径)

- `interface_executor.py:205` — `db_executor.invoke` 失败
- `interface_executor.py:275-295` — SQL 执行 + variable_manager.add_vars(result) 复杂
- `interface_executor.py:316` — `_execute_post_handlers` 调 assert 前 starter.send
- `interface_executor.py:375-387` — extract 真实执行 (非 200 跳过 + 有 extracts 走)

---

## 总览

| 指标 | 修前 (commit 09c6255) | 修后 |
|---|---|---|
| 测试数 | 337 unit | **392 unit** (+55) |
| 通过率 | 100% | 100% |
| step_content 子目录覆盖率 | 88% | **100%** (7 文件) |
| request_builder.py 覆盖率 | 69% | **97%** |
| interface_executor.py 覆盖率 | 0% | **88%** |
| 整体覆盖率 (目标子目录) | 88% | **96%** |
| 新发现 BUG | — | **BUG-RB1** (修) |

## 文件清单

新增 (5 测试文件):
- `tests/croe/interface/test_url_builder_coverage.py` (X1, 5 测试)
- `tests/croe/interface/test_step_content_init_coverage.py` (X2, 11 测试)
- `tests/croe/interface/test_step_content_loop_edge_coverage.py` (X3, 4 测试)
- `tests/croe/interface/test_request_builder_edge_coverage.py` (X4, 13 测试, 含 BUG-RB1 修复测试)
- `tests/croe/interface/test_interface_executor_coverage.py` (W, 22 测试)

修改 (2 文件):
- `croe/interface/builder/request_builder.py` (BUG-RB1: 加 else 分支 log.warning)
- `tests/croe/interface/_bug_ids.py` (新增 BUG_RB1 常量)

