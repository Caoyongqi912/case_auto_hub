# WorkPool 启用后流程与实际应用文档

> 文档日期：2026-06-16  
> 适用项目：CaseAutoHub / case_auto_hub  
> 模块路径：`common/worker_pool/`

---

## 一、项目概述

`common/worker_pool` 是 CaseAutoHub 的 **Redis 分布式异步任务工作池**，用于替代或补充原先直接在 HTTP 请求/Celery 中同步执行长耗时任务的方式。启用后，所有接口自动化、UI 自动化等“重任务”都会先被提交到 Redis 队列，再由后台 Worker 协程异步消费执行。

### 1.1 设计目标

- **异步解耦**：HTTP 接口只负责任务提交，不阻塞等待执行结果。
- **分布式能力**：基于 Redis 实现多实例共享队列，天然支持多机部署。
- **可控并发**：通过 Worker 数量限制并发执行数，避免瞬时资源打满。
- **状态可见**：任务状态、结果、统计信息持久化在 Redis，可查询可监控。
- **失败隔离**：失败任务进入死信队列，支持重试与清理。

### 1.2 开关配置

WorkPool 由配置项 `WORKER_POOL` 控制是否启用（默认 `False`）：

```python
# config.py
class LocalConfig(BaseConfig):
    WORKER_POOL = False          # 是否启用 Redis Worker Pool
    TASK_WORKER_POOL_SIZE = 10   # Worker 数量
    REDIS_WORKER_POOL_BD = 10    # WorkPool 使用的 Redis DB
```

当 `WORKER_POOL = False` 时，`init_worker_pool()` 不会真正启动工作池，业务代码中若仍调用 `submit_to_redis()` 会因 `is_running` 为 `False` 而抛异常。因此启用前需确保所有调用链路已适配。

---

## 二、架构组成

模块采用分层设计，职责清晰：

| 文件 | 职责 |
|------|------|
| `pool.py` | **工作池主入口**。组合连接、队列、执行器、监控；管理 Worker 协程生命周期。 |
| `connection.py` | **Redis 连接管理**。维护主连接与原始二进制连接，加载 Lua 原子脚本。 |
| `queue.py` | **任务队列操作**。负责任务入队、原子出队、取消、本地缓存。 |
| `executor.py` | **任务执行器**。根据函数注册表调用实际业务函数，处理超时、成功、失败、清理。 |
| `monitor.py` | **监控统计**。提供队列统计、任务状态查询、死信重试、旧任务清理。 |
| `models.py` | **任务模型**。定义 `Job` 数据类、`JobStatus` 枚举、序列化逻辑。 |
| `tasks.py` | **业务函数注册**。注册接口/UI 自动化执行的入口函数，供 Worker 反射调用。 |

### 2.1 核心类关系

```
RedisWorkerPool (pool.py)
    ├─ RedisConnectionManager (connection.py)  # Redis 连接 + Lua 脚本
    ├─ TaskQueue (queue.py)                    # 队列操作
    ├─ TaskExecutor (executor.py)              # 函数注册 + 执行
    └─ PoolMonitor (monitor.py)                # 统计 + 清理
```

---

## 三、启动流程

### 3.1 应用启动顺序

在 `main.py:71` 的 `lifespanApp` 中定义：

```
1. 打印 Banner
2. init_essential()        # 数据库 + Redis
3. init_services()         # Worker Pool + APScheduler
4. init_optional()         # 代理/UI方法/配置等
```

`init_worker_pool(rc)` 逻辑：

```python
async def init_worker_pool(rc):
    from common.worker_pool import r_pool
    if Config.WORKER_POOL:
        await r_pool.set_redis_client(rc)   # 注入外部 RedisClient
        await r_pool.start()                # 启动连接、Worker、监控
        return r_pool
```

### 3.2 RedisWorkerPool.start() 内部流程

```
1. 建立 Redis 连接
   - 创建原始连接 raw_redis（decode_responses=False，用于 pickle 二进制数据）
   - 使用外部注入的 redis_client 作为主连接 redis
2. 加载 Lua 脚本到 Redis，得到 script_sha
3. 创建 N 个 Worker 协程（N = worker_count，默认 5）
4. 创建监控协程（每 5 分钟打印一次统计）
```

### 3.3 关闭流程

在应用关闭时：

```
1. 关闭 APScheduler
2. pool.stop()：
   - 设置 is_running = False
   - 取消监控任务
   - 取消所有 Worker 任务
   - 断开 Redis 连接
3. 关闭 Redis 连接池
```

---

## 四、任务流转流程

### 4.1 任务状态定义

```python
class JobStatus(Enum):
    PENDING   = "pending"     # 等待执行
    RUNNING   = "running"     # 执行中
    COMPLETED = "completed"   # 执行完成
    FAILED    = "failed"      # 执行失败
    CANCELLED = "cancelled"   # 已取消
```

### 4.2 任务提交流程

业务方调用 `r_pool.submit_to_redis(...)`：

```python
await r_pool.submit_to_redis(
    func=register_interface_task_Handle,
    job_id=task_job.uid,
    job_name=task_job.interface_task_title,
    job_kwargs={"task_id": task_job.id, "env_id": task.env_id, "user": starter}
)
```

内部处理：

```
1. 检查任务池是否就绪（is_running + Redis 连接正常）
2. 用 func.__name__ 作为 func_name 构建 Job 对象
3. 将 Job 序列化为 pickle 二进制，写入 Redis Hash：job_data:{queue_name}
4. 将 job_id 加入有序集合 job_queue:{queue_name}，score 为当前时间戳
5. 本地缓存该 Job，记录日志
```

### 4.3 Worker 消费流程

每个 Worker 协程循环执行：

```
1. 通过 Lua 脚本原子地从 job_queue 取出 job_id，并从 job_data 读取任务数据
   - 同时把任务写入 processing_key:{server_id}_worker_{i}
2. 反序列化得到 Job 对象
3. 标记任务为 RUNNING，记录 worker_id、start_time
4. 在 TaskExecutor 中查找 func_name 对应的注册函数并执行
   - 默认超时 3600 秒
5. 执行成功：结果写入 job_results:{queue_name}
6. 执行失败：错误信息写入 dead_letter:{queue_name}
7. 清理 processing_key 中的记录
```

### 4.4 状态流转图

```
                submit_to_redis
                       │
                       ▼
                   ┌─────────┐
                   │ PENDING │◄──── retry_failed_jobs
                   └────┬────┘
                        │ Worker 取出
                        ▼
                   ┌─────────┐
                   │ RUNNING │
                   └────┬────┘
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐
   │COMPLETED│    │ FAILED  │    │CANCELLED│
   └─────────┘    └────┬────┘    └─────────┘
                       │
                       ▼
              dead_letter:{queue}
```

---

## 五、Redis 数据结构

WorkPool 使用独立的 Redis DB（默认 DB 10），键名按队列名隔离：

| Redis Key | 类型 | 说明 |
|-----------|------|------|
| `job_queue:{queue_name}` | Sorted Set | 等待执行的任务队列，score 为时间戳 |
| `job_processing:{queue_name}:{server_id}_worker_{i}` | Hash | 各 Worker 正在处理的任务 |
| `job_data:{queue_name}` | Hash | 所有任务序列化数据 |
| `job_results:{queue_name}` | Hash | 已完成任务的结果（JSON） |
| `job_dead_letter:{queue_name}` | List | 失败任务的死信队列 |

### 5.1 原子出队 Lua 脚本

```lua
local job_id = redis.call('zpopmin', KEYS[1])      -- queue_key
if not job_id or #job_id == 0 then return nil end
local job_data = redis.call('hget', KEYS[2], job_id[1])  -- job_data_key
if not job_data then return nil end
redis.call('hset', KEYS[3], job_id[1], job_data)   -- processing_key
return {job_id[1], job_data}
```

---

## 六、实际应用场景

WorkPool 当前已在以下 4 个场景落地：

### 6.1 手动执行接口任务

**入口**：`app/controller/interface/interfaceTaskController.py:201`

```python
@router.post("/execute", description="手动执行任务")
async def execute_task(task: ExecuteTask, starter: User = Depends(Authentication())):
    from common.worker_pool import r_pool, register_interface_task_Handle
    task_job = await InterfaceTaskMapper.get_by_id(task.task_id)
    await r_pool.submit_to_redis(
        func=register_interface_task_Handle,
        job_id=task_job.uid,
        job_name=task_job.interface_task_title,
        job_kwargs={"task_id": task_job.id, "env_id": task.env_id, "options": ["API", "CASE"], "user": starter}
    )
```

**说明**：用户在页面点击“执行”，任务立即进入队列，接口立刻返回成功提示，实际执行由后台 Worker 完成。

### 6.2 Jenkins 触发接口任务

**入口**：`app/controller/interface/interfaceTaskController.py:234`

与手动执行类似，但使用 `register_interface_task_RoBot`，不带 `user` 对象，供外部 CI 调用。

### 6.3 手动/UI 自动化任务

**入口**：`app/controller/play/play_task.py:90`

```python
@router.post("/handleExecute", description="添加任务")
async def handleExecute(taskInfo: GetPlayTaskByIDSchema, user: User = Depends(Authentication())):
    from common.worker_pool import r_pool, register_play_task_handle
    task = await PlayTaskMapper.get_by_id(ident=taskInfo.taskId)
    await r_pool.submit_to_redis(
        func=register_play_task_handle,
        job_id=task.uid,
        job_name=task.title,
        job_kwargs={"task_id": task.id, "user": user}
    )
```

Jenkins 触发则使用 `register_play_task_robot`。

### 6.4 APScheduler 定时任务

**入口**：`app/scheduler/aps/jobs.py`

```python
async def aps_submit_interface_task(job: AutoJob):
    if not r_pool.is_running:
        raise RuntimeError("任务池未启动")
    for task_id in job.job_task_id_list:
        await r_pool.submit_to_redis(
            func=register_interface_task_RoBot,
            job_id=task_id,
            job_name=job.job_name,
            job_kwargs={"task_id": task_id, "env_id": job.job_env_id, "retry": job.job_max_retry_count, ...}
        )
```

APS 定时任务被触发后，会把对应任务批量提交到 WorkPool，Worker 异步执行。

### 6.5 Celery 定时任务

**入口**：`app/scheduler/celer9/tasks.py`

Celery Beat 触发 `celery_submit_interface_task` / `celery_submit_play_task`，其内部通过 `asyncio.run(_execute())` 调用同样的 `submit_to_redis()` 逻辑。相当于把 Celery 作为调度器，执行仍交给 WorkPool。

> 注意：这里每个 Celery task 内部用 `asyncio.run()` 跑协程，与 FastAPI 主事件循环是独立的。

### 6.6 场景对比

| 场景 | 触发方式 | 使用的注册函数 | 是否带 user |
|------|---------|---------------|------------|
| 接口任务-手动 | HTTP API | `register_interface_task_Handle` | 是 |
| 接口任务-Jenkins | HTTP API | `register_interface_task_RoBot` | 否 |
| 接口任务-定时 | APScheduler / Celery | `register_interface_task_RoBot` | 否 |
| UI 任务-手动 | HTTP API | `register_play_task_handle` | 是 |
| UI 任务-Jenkins | HTTP API | `register_play_task_robot` | 否 |
| UI 任务-定时 | APScheduler / Celery | `register_play_task_robot` | 否 |

---

## 七、任务注册机制

所有可执行函数必须在 `common/worker_pool/tasks.py` 中通过装饰器注册到 `r_pool`：

```python
r_pool = RedisWorkerPool.get_instance()

@r_pool.register_function
async def register_interface_task_Handle(user: User, **kwargs):
    runner = TaskRunner(APIStarter(user))
    await runner.execute_task(params=TaskParams(**kwargs))
```

Worker 消费时通过 `job.func_name` 在 `function_registry` 中查找并调用。新增任务类型需要：

1. 在 `tasks.py` 定义 async 函数并加 `@r_pool.register_function`。
2. 在业务侧调用 `submit_to_redis(func=xxx, ...)` 提交。

---

## 八、监控与运维

### 8.1 日志输出

- 启动：`Redis工作池启动: {worker_count} workers, server={server_id}`
- Worker 开始：`worker:【{worker_name}】start, connect to redis success`
- 任务开始：`{worker_name} 开始处理任务 {job.id}: {job.name}`
- 任务完成：`任务 {job} 执行完成 result: ... 耗时 {duration:.2f}s`
- 监控心跳（每 5 分钟）：队列长度、处理中、已完成、失败、服务器列表

### 8.2 可调用接口

`RedisWorkerPool` 提供以下运维方法：

```python
await pool.get_stats()                     # 获取队列统计
await pool.get_job_status(job_id)          # 查询单个任务状态
await pool.cancel_job(job_id)              # 取消等待中的任务
await pool.retry_failed_jobs(limit=10)     # 从死信队列重试
await pool.cleanup_old_jobs(hours=24)      # 清理 24 小时前的已完成/失败任务
```

### 8.3 死信队列

任务执行抛异常后会被写入 `job_dead_letter:{queue_name}`，可通过 `retry_failed_jobs()` 重新生成新 Job ID 并入队重试。

---

## 九、注意事项与潜在问题

1. **开关一致性**  
   `WORKER_POOL = False` 时，所有调用 `submit_to_redis()` 的地方都会报错。目前 APS/Celery 代码已检查 `r_pool.is_running`，但仍需保证配置与调用链路一致。

2. **任务函数注册时机**  
   `r_pool` 是模块导入时通过 `RedisWorkerPool.get_instance()` 创建的单例，注册函数在 `tasks.py` 导入时完成。必须确保 `tasks.py` 在 Worker 启动前被导入。

3. **参数序列化**  
   `Job.args` / `Job.kwargs` 使用 `pickle` 序列化并保存为 hex 字符串。提交的任务参数必须可 pickle，且在不同 Python 版本/代码版本间保持兼容。

4. **User 对象序列化**  
   手动执行任务时会把 SQLAlchemy `User` 对象作为 kwargs 传入。必须确认 `User` 模型可被 pickle，否则 Worker 反序列化会失败。

5. **Worker 超时**  
   默认任务超时 3600 秒，超时会抛出 `TimeoutError` 并进入死信队列。UI 自动化、接口批量执行需评估是否需要调整。

6. **processing_key TTL**  
   `PROCESSING_KEY_TTL = 300` 秒，Worker 异常退出后处理中记录会过期自动清理，但期间统计的 `processing` 数量可能不准。

7. **多实例部署**  
   多个 CaseAutoHub 实例使用同一个 Redis DB 时，`server_id` 由 `hostname_pid` 组成，天然隔离。所有实例共享队列，Worker 会竞争消费，实现负载均衡。

8. **Celery 与 WorkPool 并用**  
   Celery 目前只作为“调度触发器”，真正执行仍依赖 WorkPool。如果 Celery Worker 与 FastAPI 不在同一进程，需确保两者都能连上同一个 Redis DB。

9. **清理效率**  
   `cleanup_old_jobs()` 使用 `hscan` 分批扫描，旧任务多时可能较慢，建议放在低峰期执行。

---

## 十、总结

WorkPool 启用后，CaseAutoHub 的任务执行从“同步/直接调用”转变为“Redis 队列 + 异步 Worker 消费”。核心收益：

- HTTP 接口响应更快，不会因为执行耗时而超时。
- 任务执行与 Web 服务解耦，Web 重启不影响已入队任务。
- 支持多实例共享队列，水平扩展 Worker 能力。
- 统一了手动执行、Jenkins、APScheduler、Celery 四种触发方式的执行通道。

要启用 WorkPool，只需在对应环境配置中设置 `WORKER_POOL = True`，并确认 Redis 连接正常即可。后续新增后台任务类型时，建议统一走 WorkPool 注册-提交流程，避免再引入新的执行通道。

---

## 十一、设计评价与改进建议

### 11.1 总体评价

整体而言，`common/worker_pool` 是一个**结构清晰、可运行的自研任务队列中间件**，基本覆盖了生产所需的核心能力，但在连接生命周期、序列化方案、与 Celery 的关系、可观测性等方面还有明显的打磨空间。

---

### 11.2 做得好的地方

1. **模块职责划分合理**  
   `pool/connection/queue/executor/monitor/models/tasks` 七个子模块职责清晰，符合单一职责原则，便于快速定位修改点。

2. **队列原子性有保障**  
   使用 Redis Lua 脚本实现 `zpopmin + hget + hset processing` 的原子操作，避免多 Worker 竞争同一条任务，这是分布式队列的关键。

3. **统一了多种触发通道**  
   手动执行、Jenkins、APScheduler、Celery 最终都调用同一套 `submit_to_redis` + Worker 消费链路，避免了以前“接口直接跑、定时任务另跑一套”的混乱。

4. **具备一定的运维能力**  
   提供了队列统计、任务状态查询、死信队列、手动重试、旧任务清理等能力，对于自研组件来说已经比较完整。

5. **多实例天然支持**  
   `server_id = hostname_pid`，多个 CaseAutoHub 实例共享 Redis DB 即可实现负载均衡，无需额外服务发现。

---

### 11.3 存在的问题与风险

#### 1. 与 Celery 的关系没有厘清（架构层面最大疑问）

项目里已经有完整的 Celery 调度体系（`app/scheduler/celer9/`），却又自研了一套 Redis Worker Pool，这带来几个问题：

- **重复造轮子**：Celery 本身就是基于 Redis/RabbitMQ 的分布式任务队列，支持 Worker、重试、死信、监控、定时调度。
- **维护成本**：队列语义、失败恢复、并发控制、序列化、连接池都需要自己维护。
- **调用链路绕**：Celery task 里再用 `asyncio.run(_execute())` 调 WorkPool，相当于用 Celery 当触发器，执行交给 WorkPool，增加了复杂度和延迟。

> 建议：要么彻底用 WorkPool 替代 Celery 执行层，要么直接用 Celery 做执行，保留一个调度入口。现在两者并存，长期维护成本高。

#### 2. 序列化方案选 pickle 有隐患

`Job.args` / `Job.kwargs` 用 `pickle.dumps().hex()` 序列化：

- **兼容性问题**：Python 版本升级、类结构变化后，旧任务可能反序列化失败。
- **安全风险**：Redis 一旦被写入恶意 pickle payload，Worker 反序列化时会执行任意代码。
- **User 对象直接 pickle**：手动执行任务时把 SQLAlchemy `User` 模型塞进去，跨进程/跨服务时容易出问题。

> 建议：优先用 JSON / msgpack 传简单参数（如 `user_id` 而非 `User` 对象），需要时再查库。

#### 3. Worker 生命周期和连接管理有瑕疵

`pool.py` 中多个方法会先 `await self._connection.connect()`：

```python
async def get_stats(self):
    await self._connection.connect()
    return await self._monitor.get_stats(self.redis)
```

如果 `raw_redis` 已经连接，重复调用不会有大问题，但 `connect()` 内部没有完善的幂等校验；且 `set_client()` 直接把 `_is_connected` 设为 `True`，却不保证 `raw_redis` 已创建。

#### 4. `_cleanup_job` 的 key 处理脆弱

```python
processing_key.split(':')[0] + ':' + ':'.join(processing_key.split(':')[1:2])
```

这种字符串拼接逻辑完全依赖 `processing_key` 的冒号层级，一旦 key 命名调整就会写错位置。建议直接传入 `job_data_key` 作为目标。

#### 5. 死信队列只进不出，无上限

失败任务被 `rpush` 进 `dead_letter`，但没有任何自动淘汰或容量限制。长期运行可能占用大量 Redis 内存。

#### 6. 重试丢失任务血缘

`retry_failed_jobs()` 重新生成 `uuid` 作为新 job_id：

```python
job.id = str(uuid.uuid4())
```

原任务 ID 丢失，无法追踪“这次重试是从哪次失败来的”。

#### 7. 没有真正的优先级队列

虽然用了 `Sorted Set`，但 score 只是 `time.time()`，本质上是先进先出，没有支持高优先级任务插队。

#### 8. 监控心跳太稀疏

`_run_monitor` 每 5 分钟才打一次日志。对于运行中的任务，5 分钟才感知一次队列堆积偏慢。

#### 9. Celery 集成方式性能差

Celery task 是同步函数，内部用 `asyncio.run(_execute())` 创建/销毁事件循环。每个任务都跑一次，开销较大。

---

### 11.4 值得追问的设计决策

| 问题 | 当前现状 | 建议 |
|------|---------|------|
| 为什么不用 Celery 直接执行？ | 自研 WorkPool + Celery 双轨 | 二选一，或明确分工 |
| 为什么用 pickle？ | 传参方便，可直接传 User 对象 | 改为 JSON + 传 ID |
| Worker 数量固定为 5/10，能否按队列配置？ | 单例固定 | 支持按任务类型配置不同队列/Worker 数 |
| 任务结果如何通知调用方？ | 写入 Redis results，无主动通知 | 增加 WebSocket/回调/SSE 通知 |
| 运行中的任务如何取消？ | 只能取消 PENDING | 支持中断 RUNNING（需要任务协作） |

---

### 11.5 改进建议（按优先级）

#### 高优先级

1. **明确 Celery 与 WorkPool 的边界**  
   建议让 WorkPool 完全接管异步执行，Celery 仅作为遗留或外部调度兼容层；或者反过来，移除 WorkPool，统一用 Celery。

2. **序列化从 pickle 迁移到 JSON/msgpack**  
   参数只传基础类型 + ID，不要传 ORM 对象。

3. **修复 `_cleanup_job` 的 key 处理**  
   直接传入 `job_data_key`，不要依赖字符串 split。

#### 中优先级

4. **死信队列增加容量限制与元信息**  
   保留原 job_id，记录失败次数，超过阈值丢弃或告警。

5. **监控心跳改为可配置，并增加告警阈值**  
   例如队列堆积超过 N 条时立即告警。

6. **Celery task 改为异步或常驻事件循环**  
   避免每个任务 `asyncio.run()`。

#### 低优先级

7. **支持任务优先级**  
   给 `submit_to_redis` 增加 `priority` 参数，映射到 Sorted Set 的 score 计算。

8. **增加 Worker 健康检查与优雅退出**  
   当前 `stop()` 直接 cancel，运行中任务会被强制中断。

---

### 11.6 一句话总结

> 这是一个“能跑、结构不错、但工程细节需要收紧”的中型自研组件。如果团队有精力持续维护，它可以很好地贴合业务；如果希望降低长期成本，建议评估迁移到 Celery 或 RQ 等成熟方案，只保留业务层的 `tasks.py` 注册逻辑。

---

## 十二、WorkPool 独立进程部署方案

> 针对 **Gunicorn 多 workers 部署** 场景，推荐将 WorkPool 从 Web 进程中拆分出来，作为独立进程运行。

### 12.1 为什么需要独立部署

当前 `main.py` 在 FastAPI lifespan 中启动 WorkPool，意味着 **每个 Gunicorn worker 进程都会启动一套 WorkPool**。例如：

```bash
gunicorn main:caseHub -k uvicorn.workers.UvicornWorker -w 4
```

若 WorkPool `worker_count=5`，则总执行并发数为 `4 × 5 = 20`。这会导致：

- **Web 进程与执行任务耦合**：Gunicorn worker 重启、滚动更新会中断正在执行的任务；
- **并发数不可控**：总并发数取决于 Gunicorn workers 数量，而非 WorkPool 配置；
- **资源竞争**：UI 自动化任务需要启动浏览器，20 个并发浏览器实例会压垮服务器；
- **监控噪音**：每个进程都打印监控日志，造成重复输出。

### 12.2 目标架构

```
用户 / 前端
    │
    ▼
Gunicorn + Uvicorn Worker (1-2 workers)
  FastAPI 应用
    • 接收 HTTP 请求
    • APScheduler 定时触发
    • submit_to_redis() 提交任务
    • 不启动 WorkPool
    │
    ▼
Redis 队列（按任务类型隔离）
    │
    ├─→ job_queue:interface ──→ 独立进程：interface WorkPool (N workers)
    ├─→ job_queue:ui ─────────→ 独立进程：ui WorkPool (N workers)
    └─→ job_queue:default ────→ 独立进程：default WorkPool (N workers)
```

### 12.3 核心改造点

#### 1. Web 进程不再启动 WorkPool

在 `config.py` 中增加开关：

```python
# 是否在 Web 进程中启动 WorkPool
RUN_WORKER_POOL_IN_WEB = False
```

在 `main.py` 的 `init_services()` 中根据开关决定是否启动 WorkPool：

```python
async def init_services(redis_client: RedisClient):
    pool = None
    if Config.RUN_WORKER_POOL_IN_WEB:
        pool = await init_worker_pool(redis_client)
    aps = await init_aps(redis_client)
    return pool, aps
```

#### 2. 新增独立 WorkPool 启动入口

新建 `run_worker_pool.py`：

```python
#!/usr/bin/env python
# -*- coding:utf-8 -*-
import argparse
import asyncio
import signal

from common import rc
from common.worker_pool import RedisWorkerPool
from utils import MyLoguru

log = MyLoguru().get_logger()


async def main():
    parser = argparse.ArgumentParser(description="CaseAutoHub WorkPool Worker")
    parser.add_argument("--queue", type=str, default="default", help="队列名称")
    parser.add_argument("--workers", type=int, default=5, help="Worker 数量")
    args = parser.parse_args()

    await rc.init_pool()

    pool = RedisWorkerPool.get_instance(
        queue_name=args.queue,
        worker_count=args.workers
    )
    await pool.set_redis_client(rc)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(pool.stop()))

    log.info(f"启动 WorkPool: queue={args.queue}, workers={args.workers}")
    await pool.start()

    try:
        while pool.is_running:
            await asyncio.sleep(1)
    finally:
        await pool.stop()
        await rc.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
```

启动示例：

```bash
python run_worker_pool.py --queue interface --workers 10
python run_worker_pool.py --queue ui --workers 2
```

#### 3. 业务侧按任务类型分队列提交

在 `common/worker_pool/tasks.py` 中定义不同队列的 pool 实例：

```python
from common.worker_pool.pool import RedisWorkerPool

interface_pool = RedisWorkerPool.get_instance(queue_name="interface", worker_count=10)
ui_pool = RedisWorkerPool.get_instance(queue_name="ui", worker_count=2)
r_pool = RedisWorkerPool.get_instance(queue_name="default", worker_count=5)
```

接口任务提交：

```python
from common.worker_pool import interface_pool, register_interface_task_Handle

await interface_pool.submit_to_redis(
    func=register_interface_task_Handle,
    job_id=task_job.uid,
    job_name=task_job.interface_task_title,
    job_kwargs={...}
)
```

UI 任务提交：

```python
from common.worker_pool import ui_pool, register_play_task_handle

await ui_pool.submit_to_redis(
    func=register_play_task_handle,
    job_id=task.uid,
    job_name=task.title,
    job_kwargs={...}
)
```

#### 4. 进程管理（systemd 示例）

`/etc/systemd/system/casehub-worker-interface.service`：

```ini
[Unit]
Description=CaseAutoHub Interface WorkPool Worker
After=network.target redis.service

[Service]
Type=simple
User=casehub
WorkingDirectory=/opt/case_auto_hub
Environment=PYTHONPATH=/opt/case_auto_hub
ExecStart=/opt/case_auto_hub/venv/bin/python run_worker_pool.py --queue interface --workers 10
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/casehub-worker-ui.service`：

```ini
[Unit]
Description=CaseAutoHub UI WorkPool Worker
After=network.target redis.service

[Service]
Type=simple
User=casehub
WorkingDirectory=/opt/case_auto_hub
Environment=PYTHONPATH=/opt/case_auto_hub
ExecStart=/opt/case_auto_hub/venv/bin/python run_worker_pool.py --queue ui --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
systemctl enable casehub-worker-interface casehub-worker-ui
systemctl start casehub-worker-interface casehub-worker-ui
```

### 12.4 迁移步骤

| 阶段 | 动作 | 验证点 |
|------|------|--------|
| 阶段 1 | 新增 `run_worker_pool.py` 和 `RUN_WORKER_POOL_IN_WEB` 配置；保持旧模式 `RUN_WORKER_POOL_IN_WEB = True` | 代码不报错，功能无变化 |
| 阶段 2 | 接口/UI 任务分别使用 `interface_pool` / `ui_pool` 提交；Web 进程仍启动 WorkPool | 队列按任务类型分流 |
| 阶段 3 | 设置 `RUN_WORKER_POOL_IN_WEB = False`；启动独立 WorkPool 进程 | 任务正常被独立进程消费 |
| 阶段 4 | 配置 systemd / docker-compose / supervisor；增加监控告警 | 稳定运行，可独立扩缩容 |

### 12.5 预期收益

| 方面 | 改造前 | 改造后 |
|------|--------|--------|
| Web 重启影响 | 会中断正在执行的任务 | 不影响已入队任务 |
| 并发控制 | `Gunicorn workers × WorkPool workers` | 精确按队列配置 |
| 资源隔离 | 接口/UI 任务互相抢占 | 独立进程/队列，互不影响 |
| 扩容 | 只能扩 Gunicorn | 可单独扩接口 Worker 或 UI Worker |
| 稳定性 | Web 负载和执行负载耦合 | 解耦，故障域分离 |

### 12.6 注意事项

1. **独立进程必须导入 `tasks.py`**  
   否则函数注册表为空，Worker 无法找到执行函数：

   ```python
   from common.worker_pool import tasks  # noqa: F401
   ```

2. **UI 独立进程需要浏览器环境**  
   跑 UI 任务的机器必须安装 Chrome/Playwright 等依赖，并配置好无头/桌面环境。

3. **优雅退出**  
   当前 `pool.stop()` 直接 cancel Worker，长任务可能被中断。如果 UI 任务很长，建议改造 `stop()` 为等待当前任务完成后再退出。

4. **同一队列可启动多个进程**  
   例如接口任务量大，可以启动 2 个 `interface` WorkPool 进程，每个 10 workers，总并发 20，它们会竞争消费同一个 Redis 队列。

### 12.7 一句话总结

> **将 WorkPool 从 Gunicorn Web 进程拆分为独立进程，是当前架构最合理的演进方向。它能解决 Web 重启丢任务、并发数失控、接口/UI 任务资源竞争等核心问题，代价只是多维护一个进程。**
