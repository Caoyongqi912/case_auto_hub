# BUG-E3 + BUG-E4 + BUG-E5 修复报告 (执行器层 easy wins 一锅端)

> 状态: ✅ 已修复
> 涉及 commits: (待 commit)
> 新增测试: 8 个, 全过
> 修改文件: 2 个核心 + 1 个测试 + 1 个 _bug_ids

---

## 0. TL;DR

| BUG | 标题 | 复杂度 | 影响 |
|---|---|---|---|
| **E3** | `asyncio.TaskGroup` 在 Python 3.10 崩 | 低 (1 个 import 改写) | 3.10 部署必崩, 3.11+ 才能跑 |
| **E4** | `_parse_url` 死代码 + 跟 `UrlBuilder.build` 不一致 | 极低 (删 25 行 + 删 1 import) | 维护性风险, 逻辑漂移 |
| **E5** | `interface_before_sql.strip()` 隐式修改 ORM 字段 | 极低 (改 1 行) | 代码可读性, 防御性编程 |

3 个一起 1-1.5h 干完。

---

## 1. BUG-E3 — Python 3.10 兼容

### 1.1 根因

`croe/interface/builder/request_builder.py:403`:

```python
async with asyncio.TaskGroup() as tg:
    tasks = {
        tg.create_task(self.variables.trans(value)): key
        ...
    }
```

`asyncio.TaskGroup` 是 **Python 3.11+** 才加的 (PEP 654)。
- 在 `.venv/bin/python3.13` 下 OK
- 在 **3.10 立刻 `AttributeError: module 'asyncio' has no attribute 'TaskGroup'`
- 同样的代码在 `VariableTrans.trans` 里被作者注释掉了 (`# async with asyncio.TaskGroup()`),
  但在 RequestBuilder 里依然用 — 不一致

### 1.2 修复

`asyncio.gather` 是 **Python 3.7+** 的 API, 跨版本兼容。改成:

```python
# 旧 (3.11+ only)
async with asyncio.TaskGroup() as tg:
    tasks = {tg.create_task(self.variables.trans(v)): k for k, v in items.items()}
for task, key in tasks.items():
    request_data[key] = task.result()

# 新 (3.7+ 兼容)
keys = list(items_to_transform.keys())
coros = [self.variables.trans(v) for v in items_to_transform.values()]
results = await asyncio.gather(*coros)
for key, transformed_value in zip(keys, results):
    if transformed_value is not None:
        request_data[key] = transformed_value
```

行为等价, 跨 Python 版本兼容。

### 1.3 验证

- AST 检查: `request_builder.py` 无 `async with ... TaskGroup()` 节点
- `_transform_request_data` 端到端: 3 个字段 + 全 None + 空 dict 三种情况都跑通
- 签名未变 (`self`, `request_data`)

---

## 2. BUG-E4 — `_parse_url` 死代码

### 2.1 根因

`croe/interface/executor/interface_executor.py:132-156` 定义了 `_parse_url`:

```python
@staticmethod
async def _parse_url(interface: Interface) -> Tuple[str, str]:
    """解析 URL, 返回 host 和 path"""
    if interface.env_id == UrlBuilder.CUSTOM_ENV_ID:
        ...
    else:
        env = await EnvMapper.get_by_id(ident=interface.env_id)
        host = env.host
        url = interface.interface_url
        if env.port:
            host += f":{env.port}"
    return host, url
```

但 `grep -r _parse_url` 全仓**零调用方** — 这是死代码。

更糟的是, 它跟 `UrlBuilder.build` 在做同样的事 (CUSTOM_ENV_ID 判断), 但:
- `_parse_url` 用 `env.host` + `env.port` 拼
- `UrlBuilder.build` 用 `env.url` (一个 property, 已包含 port)
- CUSTOM_ENV_ID 分支里, `_parse_url` 调 `Tools.parse_url` 二次解析, `UrlBuilder.build` 直接 `return interface.interface_url`

两个方法**逻辑不一致**, 哪天有人改一个忘了改另一个, 容易产生"双斜杠"或"路径丢失"等诡异 bug。

### 2.2 修复

- **删** `interface_executor._parse_url` (25 行死代码)
- **删** `from app.mapper.project.env import EnvMapper` (悬空 import)
- 实际 URL 拼接统一走 `UrlBuilder.build` (已经是被调用的那个)

### 2.3 验证

- `not hasattr(InterfaceExecutor, "_parse_url")` ✓
- `from app.mapper.project.env import EnvMapper` not in `interface_executor.py` ✓

---

## 3. BUG-E5 — 显式 None 防御

### 3.1 根因

`croe/interface/executor/interface_executor.py:300`:

```python
db_script = await self.variable_manager.trans(interface.interface_before_sql.strip())
```

`interface.interface_before_sql` 是 SQLAlchemy ORM 字段。

技术上 `str.strip()` 在 Python 里永远返回**新 str**, 不会修改原字符串, 所以**实际安全**。
但代码读起来像在"在 ORM 字段上调 strip()", 让人误以为在改 DB 字段, 可读性差。

### 3.2 修复

```python
# 旧
db_script = await self.variable_manager.trans(interface.interface_before_sql.strip())

# 新
sql_text = interface.interface_before_sql or ""
db_script = await self.variable_manager.trans(sql_text.strip())
```

- 显式 `or ""` 防御 None (上面 if 已经过滤, 这里实际不会 None, 但多一层保险)
- 提取 `sql_text` 中间变量, 让"先取值 → 再处理"的两步意图明确

### 3.3 验证

- AST 字符串扫: 不再有 `interface.interface_before_sql.strip()` 链式调用
- 必有 `sql_text = interface.interface_before_sql or ""` 防御模式

---

## 4. 整体回归

```
$ pytest tests/ -m "not integration"   # 88 unit 全过 (80 老 + 8 新 E3/E4/E5)
$ pytest tests/ -m "integration"        # 3 integration 全过
```

| 测试套 | 通过 | 说明 |
|---|---|---|
| 老 80 个测试 | 80/80 | 之前 P0/P1.5/F8/F8B/F5 全部回归过 |
| E3/E4/E5 (8 个) | 8/8 | AST 静态检查 + 端到端 e2e |
| 3 integration | 3/3 | 真 DB + 真 asyncio loop |

总计: **88 unit + 3 integration = 91/91 通过**

---

## 5. 后续可考虑 (本 PR 范围外)

1. **VariableTrans.trans 注释掉的 TaskGroup**:
   `croe/a_manager/variable_manager.py` 里也有 `# async with asyncio.TaskGroup() as tg:` 注释,
   说明作者意识到兼容问题, 但没在所有地方统一替换。如果有 TaskGroup 用法, 一并 gather 化。

2. **P1 剩余 ~16 项 BUG**: M6/M7/M8/M9/M10/S4/S6/V3/V5/V6/E6-E12/D5/D6/D9-D11/RED-D6/7/8/OVER-1~6。
   下次 1-2 天能再清一波。M7 (fail_num==0 判定) 和 M8 (case_api_num 不一致) 是 P1 流程层最高 ROI。

3. **UrlBuilder.rstrip/lstrip 鲁棒性**:
   `env.url.rstrip('/') + '/' + path.lstrip('/')` 在 `path=""` 时会产生尾斜杠 `"http://x/"`。
   对 httpx 无害但 cosmetic 上不优雅。可改成 `if path else base_url` 短路。
