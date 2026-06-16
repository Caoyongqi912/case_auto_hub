# WorkPool 独立进程部署说明

本文档说明如何在生产环境以**独立进程**方式部署 CaseAutoHub 的 WorkPool。

---

## 一、部署模式说明

### 旧模式（不推荐用于生产）

```
Gunicorn (N workers)
  └── 每个 worker 启动 WorkPool
```

问题：
- Web 重启会中断任务；
- 并发数 = N × worker_count，不可控；
- 接口/UI 任务互相抢占资源。

### 新模式（推荐）

```
Gunicorn (1-2 workers)
  └── 只处理 HTTP 请求，不启动 WorkPool

独立进程 run_worker_pool.py --queue interface
独立进程 run_worker_pool.py --queue ui
```

优势：
- Web 与执行解耦；
- 并发数精确控制；
- 接口/UI 任务资源隔离；
- 可独立扩缩容。

---

## 二、关键配置

在 `config.py` 中：

```python
# 总开关：是否启用 WorkPool
WORKER_POOL = True

# Web 进程中是否启动 WorkPool
# False：Web 只提交任务，由独立进程消费
# True：兼容旧模式，Web 自己执行
RUN_WORKER_POOL_IN_WEB = False

# 各队列 Worker 数量
INTERFACE_WORKER_COUNT = 10
UI_WORKER_COUNT = 2
DEFAULT_WORKER_COUNT = 5

# 优雅退出等待超时（秒）
WORKER_POOL_GRACEFUL_TIMEOUT = 60.0
```

---

## 三、systemd 部署

### 1. 复制 service 文件

```bash
sudo cp deploy/systemd/casehub-web.service /etc/systemd/system/
sudo cp deploy/systemd/casehub-worker-interface.service /etc/systemd/system/
sudo cp deploy/systemd/casehub-worker-ui.service /etc/systemd/system/
```

### 2. 创建运行用户

```bash
sudo useradd -r -s /bin/false casehub
```

### 3. 设置目录权限

```bash
sudo chown -R casehub:casehub /opt/case_auto_hub
```

### 4. 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable casehub-web casehub-worker-interface casehub-worker-ui
sudo systemctl start casehub-web casehub-worker-interface casehub-worker-ui
```

### 5. 查看状态

```bash
sudo systemctl status casehub-web
sudo systemctl status casehub-worker-interface
sudo systemctl status casehub-worker-ui
```

---

## 四、Docker Compose 部署

```bash
cd deploy
docker-compose up -d
```

服务说明：

| 服务名 | 作用 |
|--------|------|
| web | FastAPI 应用，处理 HTTP 请求 |
| worker-interface | 消费 interface 队列，执行接口自动化任务 |
| worker-ui | 消费 ui 队列，执行 UI 自动化任务 |
| redis | Redis 服务 |
| mysql | MySQL 服务 |

---

## 五、本地开发

开发时可以保留旧模式，在 `LocalConfig` 中设置：

```python
RUN_WORKER_POOL_IN_WEB = True
```

这样只需要启动 Web 服务即可验证完整流程。

如需本地测试独立进程：

```bash
# 终端 1：启动 Web
python main.py

# 终端 2：启动 interface worker
python run_worker_pool.py --queue interface --workers 2

# 终端 3：启动 ui worker
python run_worker_pool.py --queue ui --workers 1
```

---

## 六、常见问题

### 1. Web 启动后任务没有被执行

检查：
- `RUN_WORKER_POOL_IN_WEB` 是否为 False；
- 是否启动了对应的独立 WorkPool 进程；
- Redis 中是否有任务堆积：`LLEN job_queue:interface`。

### 2. 独立进程提示“找不到函数”

确保 `run_worker_pool.py` 中导入了 `common.worker_pool.tasks`，否则函数注册表为空。

### 3. UI 任务执行失败

UI Worker 所在机器必须安装浏览器依赖（Chrome / Playwright），并确保有图形界面或无头模式配置正确。

### 4. 如何水平扩展 interface worker？

可以启动多个 interface WorkPool 进程，它们会竞争消费同一个 Redis 队列：

```bash
python run_worker_pool.py --queue interface --workers 10
python run_worker_pool.py --queue interface --workers 10
```

---

## 七、回滚方案

如果独立进程部署有问题，可以快速回滚到旧模式：

```python
# config.py
RUN_WORKER_POOL_IN_WEB = True
```

然后停止独立进程，重启 Web 服务即可。
