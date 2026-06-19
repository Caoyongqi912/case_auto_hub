# BUG-N2 + 覆盖率补强 (5 文件) Fix Report

**Branch**: `master`
**Commit**: (TBD)
**测试基线**: 294 → 337 unit + 1 skipped + 3 deselected (integration), 0 fail
**覆盖率**: step_content 子目录 47% → **88%** (+41pp)

---

## 修复前 / 修复后 对照

| 项目 | 修复前 | 修复后 | 测试 |
|---|---|---|---|
| **BUG-N2** [低] | `page_case_results` / `query_case_result` 是 dead code (raise NotImplementedError, 0 caller) | 直接删, 注释指引走 `list_by_filter` / `get_by_id` | 4 个 (test_bug_n2_*) |
| **覆盖率** `step_content_loop.py` | 18% (137 行, 112 未测) | **93%** (9 未测, 都是边角) | 10 个 (test_step_content_loop_*) |
| **覆盖率** `step_content_condition.py` | 19% (52 行, 42 未测) | **100%** | 6 个 (test_step_content_condition_*) |
| **覆盖率** `step_content_group.py` | 27% (41 行, 30 未测) | **100%** | 5 个 (test_step_content_group_*) |
| **覆盖率** `step_content_script.py` | 30% (43 行, 30 未测) | **100%** | 5 个 (test_step_content_script_*) — 顺手修了一个真实 BUG |
| **覆盖率** `request_builder.py` | 43% (147 行, 84 未测) | **69%** (45 未测) | 13 个 (test_request_builder_*) |

---

## 顺手修的 BUG

### step_content_script.py: list comp 在 extracted_vars=None 时崩溃

**修前**:
```python
script_vars=[
    {"key":k, "value":v, "target":11}
    for k ,v in extracted_vars.items() if extracted_vars
]
```
Python `for x in expr1 if expr2: ...` 实际是 `for x in (x for x in expr1 if expr2)`,
先 evaluate `extracted_vars.items()` 再 filter, 当 `extracted_vars=None` (script_text 为空 / 抛错时)
抛 `AttributeError: 'NoneType' object has no attribute 'items'`。

**修后**:
```python
script_vars=(
    [{"key": k, "value": v, "target": 11}
     for k, v in extracted_vars.items()]
    if extracted_vars is not None else []
),
```

**测试**: `test_script_step_empty_script_text_writes_result` 锁住 script_text="" 不再崩溃。

---

## 修复详情

### BUG-N2 [低] 删 dead code

**位置**: `app/mapper/interfaceApi/interfaceResultMapper.py:39-62`

**根因**: D9 修时把 `pass` 改成 `raise NotImplementedError` 防静默吞错, 但本质是
dead code 一直在, 0 caller。N2 进一步: 直接删, 真要分页走 `list_by_filter + 分页参数`,
查单个走 `get_by_id` (D9 注释里已经给了指引)。

**测试**:
- `test_bug_n2_page_case_results_removed_from_mapper` - 方法已删
- `test_bug_n2_query_case_result_removed_from_mapper` - 方法已删
- `test_bug_n2_no_caller_in_croe_app` - 全项目 0 caller (扫 croe/ + app/)
- `test_bug_n2_d9_comment_still_recommends_get_by_id` - 注释保留指引

**配套**: 旧的 3 个 BUG-D9 测试 (`test_bug_d9_*_raises_not_implemented`) 改成 BUG-N2 测试,
锁住"两个方法都不在 mapper 上"。

### step_content_loop.py 18% → 93%

10 个新单测, 覆盖:
1. loop 不存在 → return False
2. loop_steps 为空 → 写完 content_result 即返 True
3. LoopTimes 全成功 → success_num +1
4. LoopTimes 有失败 → fail_num +1 + result=ERROR
5. LoopItems JSON 解析 → 3 items × 1 api = 3 次
6. LoopItems CSV fallback ('a,b,c' 非 JSON) → 3 items
7. LoopItems 空 items → loop_count=0
8. LoopCondition 断言通过 → break
9. 未知 loop_type → log.warning + return False
10. loop_interval > 0 → 触发 asyncio.sleep

### step_content_condition.py 19% → 100%

6 个新单测, 覆盖:
1. condition 不存在 → return False
2. condition 通过, 无子 API → success_num +1
3. condition 通过, 子 API 全成功 → success_num +1
4. condition 通过, 子 API 失败 → fail_num +1 + result=ERROR
5. condition 不通过 → 跳过子步骤, success_num +1
6. task_result 透传 + assert_data 写入 (锁 BUG-E11)

### step_content_group.py 27% → 100%

5 个新单测, 覆盖:
1. interface_list 为空 → return True
2. 全成功 → success_num +1
3. 第 1 个 fail → break, fail_num +1
4. 第 2 个 fail → 第 1 个算 success_api_num, 第 2 个后 break
5. task_result 透传

### step_content_script.py 30% → 100% (+ 修 BUG)

5 个新单测, 覆盖:
1. script_text="" → extracted_vars=None, 仍写 result (锁 BUG-fix)
2. script 成功 → add_vars, success_num +1
3. ScriptSecurityError → 兜住, success=False, fail_num +1
4. 普通 Exception → 兜住, success=False, fail_num +1
5. task_result 透传

**顺手修 BUG**: list comp 在 extracted_vars=None 时崩溃。

### request_builder.py 43% → 69%

13 个新单测, 覆盖:
1. `_prepare_headers` - merge (global + interface, 后者覆盖前者)
2. `_prepare_headers` - S7 黑名单拦截 (Host/Content-Length/Connection/Transfer-Encoding/Upgrade)
3. `_prepare_headers` - 空 headers + 空 global
4. `_process_get_params` - list2dict 过滤空值
5-8. `_process_request_body` - 4 种 body type (Raw text / Raw json / UrlEncoded / Data)
9-11. `_prepare_auth` - 3 种 auth type (No_Auth / Basic / Bearer)
12-13. `_filter_request_body` - 过滤空值 + Raw text 路径

---

## 验证

```bash
# 5 BUG + 39 个新覆盖率测试
.venv/bin/python -m pytest tests/croe/interface/test_bug_n2_*.py \
    tests/croe/interface/test_step_content_group_coverage.py \
    tests/croe/interface/test_step_content_script_coverage.py \
    tests/croe/interface/test_step_content_condition_coverage.py \
    tests/croe/interface/test_step_content_loop_coverage.py \
    tests/croe/interface/test_request_builder_coverage.py -v
# 43 passed

# 全量回归
.venv/bin/python -m pytest -m "not integration" -q
# 337 passed, 1 skipped, 3 deselected

# 覆盖率
.venv/bin/python -m coverage run --source=croe.interface.executor.step_content,croe.interface.builder -m pytest -m "not integration" -q
.venv/bin/python -m coverage report --include="croe/interface/executor/step_content/*,croe/interface/builder/*" --skip-covered
# TOTAL 88% (前 47%, +41pp)
# 7 文件 100% 覆盖
```

---

## 下批可推

| 项 | ROI | 时间 |
|---|---|---|
| `request_builder.py` 69% → 90%+ (剩 _prepare_file_upload + _transform_request_data + KV Auth) | 高 | 30 min |
| `url_builder.py` 44% → 80%+ | 高 | 20 min |
| `step_content/__init__.py` 69% → 100% (get_step_strategy 路由) | 中 | 15 min |
| `step_content_loop.py` 93% → 100% (剩 9 行, 边角) | 中 | 10 min |
| `croe/interface/executor/interface_executor.py` (0 覆盖) | 高 | 1h |
| 集成测试烟囱 (SQLite 跑 smoke) | 中 | 2h |
| 生产数据治理脚本 | 中 | 1h |
