# Celery 调度模块技术文档

## 目录

1. [模块架构说明](#1-模块架构说明)
2. [核心类与函数使用说明](#2-核心类与函数使用说明)
3. [任务定义与注册方法](#3-任务定义与注册方法)
4. [定时任务配置方式](#4-定时任务配置方式)
5. [完整调用示例代码](#5-完整调用示例代码)
6. [常见问题解决方案](#6-常见问题解决方案)
7. [与 APScheduler 对比](#7-与-apscheduler-对比)

---

## 1. 模块架构说明

### 1.1 整体架构

```
app/scheduler/celer9/
├── __init__.py      # 模块初始化，导出公共接口
├── app.py           # Celery 应用配置和调度构建器
├── trigger.py       # 触发器封装（CRON/间隔/单次）
├── tasks.py         # 任务定义（接口/UI/心跳等）
├── scheduler.py     # 调度器核心类
└── service.py       # 服务层封装
```

### 1.2 模块职责

| 模块 | 职责 |
|------|------|
| `app.py` | Celery 应用实例创建、配置管理、Beat Schedule 构建 |
| `trigger.py` | 触发器抽象，支持 CRON、固定间隔、单次执行三种模式 |
| `tasks.py` | 定义具体的 Celery 任务，包括接口测试、UI 测试、心跳等 |
| `scheduler.py` | 调度器核心，提供任务注册、移除、启用/禁用等操作 |
| `service.py` | 服务层封装，提供统一的 API 接口 |

### 1.3 设计原则

- **接口一致性**：与 APScheduler 模块保持 API 兼容
- **分布式支持**：基于 Redis 实现分布式锁和任务存储
- **可扩展性**：支持自定义任务类型和触发器
- **类型安全**：完整的类型注解支持

---

## 2. 核心类与函数使用说明

### 2.1 CeleryHubScheduler

调度器核心类，提供完整的任务管理能力。

```python
from app.scheduler.celer9 import CeleryHubScheduler, celeryHubScheduler

# 使用全局实例（推荐）
scheduler = celeryHubScheduler

# 或创建新实例
scheduler = CeleryHubScheduler()
```

#### 主要方法

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| `initialize(redis)` | 初始化调度器 | RedisClient | bool（是否为主节点） |
| `add_auto_job(job)` | 添加自动化任务 | AutoJob | bool |
| `remove_job(job_id)` | 移除任务 | str | bool |
| `switch_job(job_id, enable)` | 启用/禁用任务 | str, bool | bool |
| `modify(job)` | 修改任务配置 | AutoJob | bool |
| `get_job(job_id)` | 获取任务信息 | str | Optional[Dict] |
| `get_jobs()` | 获取所有任务 | - | List[Dict] |
| `shutdown()` | 关闭调度器 | - | None |

### 2.2 CeleryTrigger

触发器封装类，支持三种触发类型。

```python
from app.scheduler.celer9 import CeleryTrigger, create_trigger
from enums import TriggerTypeEnum

# 通用创建方式
trigger = create_trigger(
    trigger_type=TriggerTypeEnum.CRON,
    kw={"cron": "0 12 * * *"}
)

# 检查有效性
if trigger.is_valid:
    print(f"调度对象: {trigger.schedule}")
```

### 2.3 CeleryScheduleService

服务层封装，提供便捷的操作接口。

```python
from app.scheduler.celer9 import CeleryScheduleService

# 初始化
await CeleryScheduleService.initialize(redis_client)

# 添加任务
await CeleryScheduleService.add_auto_job(job)

# 启用/禁用任务
await CeleryScheduleService.enable_job(job_id)
await CeleryScheduleService.disable_job(job_id)

# 获取统计信息
stats = CeleryScheduleService.get_schedule_statistics()
```

### 2.4 CeleryScheduleBuilder

调度配置构建器，用于构建 Beat Schedule 条目。

```python
from app.scheduler.celer9 import CeleryScheduleBuilder

# 构建 CRON 调度
cron_schedule = CeleryScheduleBuilder.build_cron_schedule("0 12 * * *")

# 构建间隔调度
interval_schedule = CeleryScheduleBuilder.build_interval_schedule(
    minutes=30
)

# 构建完整的 schedule 条目
entry = CeleryScheduleBuilder.build_beat_schedule_entry(
    task_name="my_task",
    task_path="app.scheduler.celer9.tasks.celery_custom_task",
    schedule_config=cron_schedule,
    args=(1, 2, 3),
    kwargs={"key": "value"},
    queue="default",
)
```

---

## 3. 任务定义与注册方法

### 3.1 定义新任务

使用 `@celery_app.task` 装饰器定义任务：

```python
from app.scheduler.celer9.app import celery_app
from celery.app.task import Task

@celery_app.task(name="my_custom_task", bind=True, max_retries=3)
def my_custom_task(self: Task, param1: str, param2: int) -> dict:
    """
    自定义任务示例
    
    Args:
        self: Celery Task 实例（bind=True 时可用）
        param1: 参数1
        param2: 参数2
    
    Returns:
        dict: 执行结果
    """
    try:
        self.update_state(state="PROGRESS", meta={"status": "执行中"})
        
        result = do_something(param1, param2)
        
        self.update_state(state="SUCCESS", meta={"result": result})
        return {"success": True, "result": result}
        
    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise
```

### 3.2 异步任务处理

对于需要执行异步代码的任务：

```python
import asyncio

@celery_app.task(name="async_task", bind=True)
def async_task(self: Task, data: dict) -> dict:
    async def _execute():
        await async_operation(data)
        return {"status": "completed"}
    
    return asyncio.run(_execute())
```

### 3.3 注册定时任务

#### 方式一：通过调度器注册

```python
from app.scheduler.celer9 import celeryHubScheduler, create_cron_trigger

trigger = create_cron_trigger("0 9 * * *")  # 每天9点执行

await celeryHubScheduler.add_job(
    task_func=my_custom_task,
    trigger=trigger,
    job_id="daily_report",
    name="每日报告任务",
    args=("report", 100),
    queue="default",
)
```

#### 方式二：通过服务层注册

```python
from app.scheduler.celer9 import CeleryScheduleService
from app.model.base.job import AutoJob

job = AutoJob(
    uid="job_001",
    job_name="测试任务",
    job_type=1,  # 接口测试
    job_trigger_type=2,  # CRON
    job_execute_cron="0 12 * * *",
    job_task_id_list=[1, 2, 3],
    job_enabled=True,
)

await CeleryScheduleService.add_auto_job(job)
```

---

## 4. 定时任务配置方式

### 4.1 CRON 表达式

CRON 表达式格式：`分 时 日 月 周`

```python
from app.scheduler.celer9 import create_cron_trigger

# 每天中午12点
trigger = create_cron_trigger("0 12 * * *")

# 每小时执行
trigger = create_cron_trigger("0 * * * *")

# 每周一早上8点
trigger = create_cron_trigger("0 8 * * 1")

# 每月1号凌晨执行
trigger = create_cron_trigger("0 0 1 * *")
```

### 4.2 固定间隔

```python
from app.scheduler.celer9 import create_interval_trigger

# 每30秒执行
trigger = create_interval_trigger(seconds=30)

# 每5分钟执行
trigger = create_interval_trigger(minutes=5)

# 每2小时执行
trigger = create_interval_trigger(hours=2)

# 组合使用：每1小时30分钟
trigger = create_interval_trigger(hours=1, minutes=30)
```

### 4.3 单次执行

```python
from app.scheduler.celer9 import create_once_trigger
from datetime import datetime, timedelta

# 指定时间执行
run_time = datetime.now() + timedelta(hours=1)
trigger = create_once_trigger(run_time)

# 使用字符串
trigger = create_once_trigger("2025-12-31T23:59:59")
```

### 4.4 直接配置 Beat Schedule

```python
from app.scheduler.celer9 import update_beat_schedule, CeleryScheduleBuilder

# 构建调度配置
schedule_entry = CeleryScheduleBuilder.build_beat_schedule_entry(
    task_name="my_scheduled_task",
    task_path="app.scheduler.celer9.tasks.my_custom_task",
    schedule_config=CeleryScheduleBuilder.build_cron_schedule("0 9 * * *"),
    args=("daily",),
    queue="default",
)

# 更新配置
update_beat_schedule({"my_scheduled_task": schedule_entry})
```

---

## 5. 完整调用示例代码

### 5.1 应用启动时初始化

```python
from fastapi import FastAPI
from common import rc
from app.scheduler.celer9 import init_celery_scheduler, shutdown_celery_scheduler

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化调度器"""
    await rc.init_pool()
    is_master = await init_celery_scheduler(rc)
    if is_master:
        print("当前节点为主节点，负责调度任务")
    else:
        print("当前节点为从节点")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    await shutdown_celery_scheduler()
```

### 5.2 添加定时任务

```python
from app.scheduler.celer9 import CeleryScheduleService
from app.model.base.job import AutoJob

async def create_scheduled_task():
    """创建定时任务"""
    job = AutoJob(
        uid="api_test_daily",
        job_name="API每日测试",
        job_type=1,
        job_trigger_type=2,
        job_execute_cron="0 9 * * *",
        job_task_id_list=[1, 2, 3],
        job_env_id=1,
        job_max_retry_count=3,
        job_retry_interval=60,
        job_enabled=True,
    )
    
    success = await CeleryScheduleService.add_auto_job(job)
    if success:
        print(f"任务 {job.job_name} 创建成功")
    return success
```

### 5.3 管理任务

```python
from app.scheduler.celer9 import CeleryScheduleService

async def manage_tasks():
    """任务管理示例"""
    
    # 获取所有任务
    jobs = await CeleryScheduleService.get_all_jobs()
    print(f"当前共有 {len(jobs)} 个任务")
    
    # 禁用任务
    await CeleryScheduleService.disable_job("job_001")
    
    # 启用任务
    await CeleryScheduleService.enable_job("job_001")
    
    # 移除任务
    await CeleryScheduleService.remove_job("job_001")
    
    # 获取统计信息
    stats = CeleryScheduleService.get_schedule_statistics()
    print(f"统计: {stats}")
```

### 5.4 查询任务执行结果

```python
from app.scheduler.celer9 import CeleryTaskResultService

def check_task_result(task_id: str):
    """查询任务执行结果"""
    result = CeleryTaskResultService.get_task_result(task_id)
    
    print(f"任务ID: {result['task_id']}")
    print(f"状态: {result['status']}")
    
    if result['status'] == 'SUCCESS':
        print(f"结果: {result['result']}")
    elif result['status'] == 'FAILURE':
        print(f"错误: {result['traceback']}")

def revoke_running_task(task_id: str):
    """撤销正在执行的任务"""
    CeleryTaskResultService.revoke_task(task_id, terminate=True)
```

### 5.5 自定义任务完整示例

```python
from app.scheduler.celer9.app import celery_app
from app.scheduler.celer9 import celeryHubScheduler, create_interval_trigger
from celery.app.task import Task
import asyncio

@celery_app.task(name="data_sync_task", bind=True, max_retries=5)
def data_sync_task(self: Task, source: str, target: str) -> dict:
    """数据同步任务"""
    async def _execute():
        await sync_data(source, target)
        return {"synced": True}
    
    try:
        self.update_state(state="PROGRESS", meta={"source": source, "target": target})
        result = asyncio.run(_execute())
        self.update_state(state="SUCCESS", meta=result)
        return result
    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise

async def register_sync_task():
    """注册数据同步任务"""
    trigger = create_interval_trigger(minutes=10)
    
    await celeryHubScheduler.add_job(
        task_func=data_sync_task,
        trigger=trigger,
        job_id="data_sync_10min",
        name="数据同步任务",
        kwargs={"source": "db1", "target": "db2"},
        queue="default",
    )
```

---

## 6. 常见问题解决方案

### 6.1 任务不执行

**问题**：配置了定时任务但没有执行

**解决方案**：
1. 确认 Celery Beat 进程正在运行：
   ```bash
   celery -A app.scheduler.celer9.app:celery_app beat -l info
   ```

2. 确认 Worker 进程正在运行：
   ```bash
   celery -A app.scheduler.celer9.app:celery_app worker -l info
   ```

3. 检查任务是否正确注册：
   ```python
   from app.scheduler.celer9 import get_beat_schedule
   print(get_beat_schedule())
   ```

### 6.2 分布式锁问题

**问题**：多实例部署时任务重复执行

**解决方案**：
1. 确保只有一个节点获取到主节点锁
2. 检查 Redis 连接是否正常
3. 查看日志确认节点角色：
   ```
   [CeleryScheduler] 初始化为主节点
   # 或
   [CeleryScheduler] 初始化为从节点
   ```

### 6.3 任务执行超时

**问题**：任务执行时间过长导致超时

**解决方案**：
1. 调整任务超时配置：
   ```python
   celery_app.conf.update(
       task_time_limit=7200,  # 硬超时 2小时
       task_soft_time_limit=6600,  # 软超时 1小时50分钟
   )
   ```

2. 在任务中处理软超时：
   ```python
   from celery.exceptions import SoftTimeLimitExceeded
   
   @celery_app.task(bind=True)
   def long_task(self):
       try:
           do_work()
       except SoftTimeLimitExceeded:
           cleanup()
   ```

### 6.4 任务重试策略

**问题**：任务失败后需要自动重试

**解决方案**：
```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 重试间隔60秒
)
def retry_task(self, data):
    try:
        process(data)
    except Exception as exc:
        raise self.retry(exc=exc)
```

### 6.5 任务队列配置

**问题**：不同类型任务需要隔离执行

**解决方案**：
```python
# 启动 Worker 时指定队列
celery -A app.scheduler.celer9.app:celery_app worker -Q interface_tasks,play_tasks,default

# 注册任务时指定队列
await scheduler.add_job(
    task_func=interface_task,
    trigger=trigger,
    job_id="api_task",
    queue="interface_tasks",  # 指定队列
)
```

### 6.6 时区问题

**问题**：CRON 任务执行时间与预期不符

**解决方案**：
1. 确认配置的时区：
   ```python
   celery_app.conf.timezone = "Asia/Shanghai"
   celery_app.conf.enable_utc = True
   ```

2. 使用正确的 CRON 表达式（基于配置时区）

---

## 7. 与 APScheduler 对比

### 7.1 功能对照表

| 功能 | APScheduler | Celery (celer9) |
|------|-------------|-----------------|
| CRON 定时 | ✅ CronTrigger | ✅ crontab |
| 固定间隔 | ✅ IntervalTrigger | ✅ schedule |
| 单次执行 | ✅ DateTrigger | ✅ schedule (一次性) |
| 分布式锁 | ✅ Redis 锁 | ✅ Redis 锁 |
| 任务持久化 | ✅ RedisJobStore | ✅ Celery Beat |
| 任务状态查询 | ✅ get_job() | ✅ get_job() |
| 动态添加任务 | ✅ add_job() | ✅ add_job() |
| 暂停/恢复 | ✅ pause/resume | ✅ switch_job |
| 心跳机制 | ✅ 自定义 | ✅ 内置 |

### 7.2 API 对照

```python
# APScheduler
from app.scheduler.aps import hubScheduler

await hubScheduler.add_auto_job(job)
await hubScheduler.remove_job(job_id)
await hubScheduler.switch_job(job_id, enable)
await hubScheduler.modify(job)

# Celery (celer9) - 完全兼容
from app.scheduler.celer9 import celeryHubScheduler

await celeryHubScheduler.add_auto_job(job)
await celeryHubScheduler.remove_job(job_id)
await celeryHubScheduler.switch_job(job_id, enable)
await celeryHubScheduler.modify(job)
```

### 7.3 迁移指南

从 APScheduler 迁移到 Celery：

1. **替换导入**：
   ```python
   # 原来
   from app.scheduler.aps import hubScheduler
   
   # 现在
   from app.scheduler.celer9 import celeryHubScheduler
   ```

2. **启动方式变更**：
   ```bash
   # APScheduler 内嵌于应用
   
   # Celery 需要单独启动
   celery -A app.scheduler.celer9.app:celery_app worker -l info
   celery -A app.scheduler.celer9.app:celery_app beat -l info
   ```

3. **配置调整**：
   - 确保 Redis 配置正确
   - 检查任务队列配置

---

## 附录

### A. 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `broker_url` | 消息代理地址 | Redis DB1 |
| `result_backend` | 结果存储地址 | Redis DB2 |
| `task_serializer` | 任务序列化格式 | json |
| `timezone` | 时区 | Asia/Shanghai |
| `task_time_limit` | 任务硬超时 | 3600秒 |
| `worker_prefetch_multiplier` | 预取任务数 | 1 |

### B. 错误码说明

| 错误码 | 说明 |
|--------|------|
| `INVALID_TRIGGER` | 无效的触发器配置 |
| `JOB_NOT_FOUND` | 任务不存在 |
| `LOCK_ACQUIRE_FAILED` | 获取分布式锁失败 |
| `TASK_TIMEOUT` | 任务执行超时 |
| `TASK_REJECTED` | 任务被拒绝 |

### C. 监控指标

建议监控以下指标：
- 任务执行成功率
- 任务平均执行时间
- Worker 队列长度
- Beat 调度延迟
- Redis 连接状态
