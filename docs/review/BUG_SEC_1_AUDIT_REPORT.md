# BUG-SEC-1 安全审计报告

**审计范围**: `app/controller/`、`app/mapper/`、`app/scheduler/`、`app/service/`、`app/ws/`、`app/model/`
**审计时间**: 2026-06-21
**审计人**: code-reviewer skill + Codex

## 概述

本次审计共发现 3 类问题, 全部已修复并加单测:

1. **BUG-SEC-1 (P0)**: Jenkins 回调端点无鉴权, 任何人可触发任务执行 -> **已修复**
2. **BUG-P-1-1.2 (P2)**: Controller 层 1 处 `raise e` + 2 处 `log.error` 在 except 块内 -> **已修复**
3. **BUG-P-1-1.3 (P2)**: non-controller 层 24 处 `log.error` + 5 处 `raise e` 在 except 块内 -> **已修复**

## BUG-SEC-1: Jenkins 回调无鉴权 (P0)

### 发现

Controller 安全扫描 v4 (修正则后) 找到 2 个写操作无鉴权:
- `app/controller/interface/interfaceTaskController.py:235` `POST /execute_by_jenkins`
- `app/controller/play/play_task.py:117` `POST /executeJenkins`

两个端点都接受 `task_id` 并通过 Redis 队列触发任务执行, **任何能访问 API 的人都可触发任意任务执行**。

中间件层 (`app/middware/`) 只有 CORS + 请求日志, **无 IP 白名单、无共享密钥、无其他兜底**。

### 修复

新增 `JenkinsWebhookAuth` FastAPI 依赖类 (`app/controller/__init__.py`):
- 检查请求头 `X-Jenkins-Token` 与 `Config.JENKINS_WEBHOOK_TOKEN` 是否匹配
- 未配置 token -> 401 + 明确报错信息 (fail-closed)
- header 缺失或不匹配 -> 401
- 配置 + 匹配 -> 放行

新增配置 `Config.JENKINS_WEBHOOK_TOKEN` (默认空字符串, 强制要求 env 注入):
- 部署前在 `.env` 设 `JENKINS_WEBHOOK_TOKEN=<强随机字符串>`
- Jenkins 调用方在 header `X-Jenkins-Token` 带入相同值

### 部署注意

- **不设置 token = 端点完全不可用** (fail-closed, 这是预期)
- 旧 Jenkins pipeline 升级到新版本时必须在调用 header 带上 token
- 推荐用 `openssl rand -hex 32` 生成 token
- 定期轮换, 不复用 `SECRET_KEY`

### 测试

`tests/controller/test_bug_sec_1_jenkins_webhook.py` 9 个测试:
- 2 个静态扫: 端点必须挂 `Depends(JenkinsWebhookAuth)`
- 6 个行为: token 未配置 / header 缺失 / header 空 / header 不匹配 -> 401, header 匹配 -> 200
- 1 个 env 注入: `JENKINS_WEBHOOK_TOKEN` 能从 env 读出

## BUG-P-1-1.2: Controller 层 traceback 丢失 (P2)

### 发现

延续 P-1-1.1 (mapper 层) 的修复, 扫描 `app/controller/` 发现 1 处 `raise e` + 2 处 `log.error` 在 except 块内:

- `app/controller/interface/interfaceController.py:228-229`
  ```python
  except Exception as e:
      log.error(f"导出YAML失败: {e}")
      raise e
  ```
- `app/controller/test_case/case_plan.py:516-520` (IntegrityError 转换)

### 修复

- `interfaceController.export_interfaces_yaml`: `raise e` -> bare `raise`, `log.error` -> `log.exception`
- `case_plan.delete_plan_cases_permanent`: `log.error` -> `log.exception` (无 re-raise, 仍补 traceback)

### 测试

`tests/controller/test_p1_1_2_controller_traceback.py` 66 个测试:
- 64 个静态扫 (parametrized x 32 文件): 无 `raise e` / 无 `log.error` in except
- 2 个行为证明: interfaceController 和 case_plan 的修复点

## BUG-P-1-1.3: non-controller 层 traceback 丢失 (P2)

### 发现

P-1-1.1 (mapper) + P-1-1.2 (controller) 的延续。扫描 `app/scheduler/`、`app/service/`、`app/ws/`、`app/model/` 共找到:

- 24 处 `log.error` 在 except 块内
- 5 处 `raise e` (全在 `app/ws/io.py` + 1 处 `app/model/__init__.py`)

### 修复

- `app/scheduler/celer9/{tasks,app,scheduler,trigger}.py`: 11 处 `log.error` -> `log.exception`
- `app/scheduler/aps/jobs.py`: 1 处
- `app/service/uploadCacheService.py`: 4 处
- `app/ws/io.py`: 5 处 `raise e` -> bare `raise` + 4 处 `log.error` -> `log.exception`
- `app/ws/ws.py`: 1 处
- `app/model/__init__.py`: 1 处 `raise e` -> bare `raise`
- `app/model/interfaceAPIModel/interfaceLoopModel.py`: 3 处 `log.error` -> `log.exception`

**回退**: `app/mapper/test_case/planCaseMapper.py:2237` 的非 except 块 `log.error` (业务日志, 保留 traceback 无意义, 维持原样)。

### 测试

`tests/controller/test_p1_1_3_non_controller_traceback.py` 146 个测试:
- 73 个静态扫 (parametrized x 73 文件): 无 `raise e` / 无 `log.error` in except
- 覆盖 4 个目录: scheduler / service / ws / model

## IDOR 深度审计 (No-op)

扫描所有 `{id}` 写路由 (含 39 个 case、35 个 play_case、32 个 case_plan、30 个 test_case 等 260+ 路由) 的函数体 owner 校验:

**结论**: 全部 POST + body 模式, 鉴权已挂, 但函数体无 `creator == user` 严格比对。**这是设计选择**, 不是 bug:
- 业务模型是 "任何已登录用户可改任何 case"
- owner 隔离靠业务层 (项目归属, 部门归属, admin 角色)
- 实际部署依赖 admin 角色区分 (部分路由用 `Authentication(isAdmin=True)`)

不修改业务逻辑, 仅在 SEC-1 报告里标注此设计选择。

## 测试基线

| 阶段 | pass | fail | 备注 |
|---|---|---|---|
| P-1-1.1 commit 前 | 775 | 0 | mapper fix + 90 mapper 单测 |
| P-1-1.2 commit 前 | 775 | 0 | + 66 controller 单测 |
| SEC-1 commit 前 | 841 | 0 | + 9 jenkins 单测 |
| P-1-1.3 commit 前 | 849 | 1 | + 146 non-controller 单测, f5 pre-existing |
| 当前 | 995 | 1 | 累计 311 新单测, f5 pre-existing (DB 不可达) |

## Commit 列表

| commit | 描述 |
|---|---|
| `37d3dac` | fix(BUG-P-1-1.1): 全量 mapper 改 bare raise + log.exception |
| `dca2010` | fix(BUG-P-1-1.2): controller 层补 bare raise + log.exception + 回归单测 |
| `980e4d5` | fix(BUG-SEC-1): 给 Jenkins 回调端点加共享密钥鉴权 (fail-closed) |
| `2387c11` | fix(BUG-P-1-1.3): non-controller 层 except 块改 log.exception + bare raise |

## 已知遗留

- `tests/croe/interface/test_bug_f5_error_stop_progress.py::test_bug_f5_error_stop_progress_is_intermediate` 持续失败
  - 原因: 导入链触发 MySQL 连接, 本地 MySQL 密码 `qq23qq` 不匹配
  - 影响: 1 个集成风格测试, 实际是 unit 标记
  - 建议: 重构为完全 mock 模式, 或在 conftest 里 mock DB engine 创建
  - 与本次安全审计无关, 暂不动
