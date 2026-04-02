<div align="center">

# CaseHUB

### 接口 & UI 自动化测试工具

[![FastAPI](https://img.shields.io/badge/FastAPI-0.121.3-blue)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/)
[![Httpx](https://img.shields.io/badge/Httpx-0.28.1-blue)](https://www.python-httpx.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.56.0-blue)](https://playwright.dev/python/docs/api/class-playwright)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-orange)](https://www.mysql.com/)
[![Redis](https://img.shields.io/badge/Redis-7.1.0-red)](https://redis.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**接口测试** · **UI自动化** · **定时任务** · **测试报告**

</div>

---

## 📖 目录

- [项目简介](#-项目简介)
- [核心特性](#-核心特性)
- [技术架构](#-技术架构)
- [快速开始](#-快速开始)
- [功能展示](#-功能展示)
- [配置说明](#-配置说明)
- [更新日志](#-更新日志)
- [联系我们](#-联系我)

---

## 🎯 项目简介

**CaseHUB** 是一个接口与UI自动化测试工具，主要用于测试团队进行自动化测试工作。工具集成了接口测试、UI自动化测试、定时任务调度、测试报告生成等功能，支持测试流程编排和断言验证，帮助团队提升测试效率。

### 前端项目

🔗 [前端项目地址](https://github.com/Caoyongqi912/caseHubWeb)

---

## ✨ 核心特性

### 🔌 接口自动化测试

#### 完整的HTTP请求支持
- 支持HTTP请求类型：GET、POST、PUT、DELETE
- 灵活的参数配置：URL、Header、Query、Body等
- CURL命令解析导入，快速生成测试用例

#### 智能变量管理
- **变量提取**：从响应数据中提取变量，支持JSONPath、JMESPath等多种提取方式
- **变量引用**：在后续请求中灵活引用提取的变量
- **全局变量**：跨用例、跨项目的变量共享机制
- **函数变量**：支持自定义函数生成动态变量

#### 强大的断言能力
- **状态码断言**：验证HTTP响应状态码
- **内容断言**：验证响应体内容，支持JSONPath、JMESPath表达式
- **变量断言**：验证变量值的正确性
- **SQL断言**：验证数据库查询结果

#### 灵活的测试流程
- **前后置脚本**：在用例执行前后执行自定义Python脚本
- **SQL执行**：支持在测试流程中执行SQL语句
- **条件判断**：根据条件动态控制测试流程
- **循环执行**：支持LOOP循环执行器
- **等待机制**：支持步骤等待功能

#### 业务流程编排
- 支持引用公共API和API组
- 支持添加私有API
- 支持逻辑判断、脚本执行、等待等步骤
- 支持用例拖拽排序和复制

#### 调试与执行
- **调试模式**：逐步执行测试用例，实时查看日志
- **同步执行**：实时展示测试日志，便于问题排查
- **异步执行**：后台执行任务，支持轮询结果
- **单用例/批量执行**：灵活的执行方式

#### 定时任务与报告
- **定时任务**：基于APScheduler的定时任务调度
- **任务池管理**：支持任务池管理和调度
- **测试报告**：自动生成HTML格式测试报告
- **结果推送**：支持企业微信等多种推送方式

#### 接口录制
- 支持接口录制功能（当前版本体验不佳，待优化）

---

### 🖥️ UI自动化测试

#### Playwright集成
- 基于Playwright的浏览器自动化测试
- 支持Chrome、Firefox、Safari等主流浏览器
- 支持无头模式和运行日志可视化模式

#### 步骤管理
- **步骤录入**：可视化录入测试步骤
- **公共步骤**：创建和管理可复用的公共步骤
- **步骤拖拽**：灵活调整步骤执行顺序
- **步骤组**：支持步骤组管理，提升复用性
- **SQL操作**：支持在UI测试中执行SQL
- **脚本操作**：支持在UI测试中执行python脚本
- **接口请求**：支持在UI测试中执行接口请求



#### 全局配置
- **环境配置**：支持多环境切换
- **方法配置**：自定义UI测试方法
- **任务调度**：支持UI测试任务的定时执行

---

### 📊 测试用例管理

#### 用例生命周期管理
- **用例CRUD**：完整的用例增删改查功能
- **用例复制**：快速复制已有用例
- **用例拖拽**：灵活调整用例顺序
- **用例关联**：关联需求，实现需求追溯

#### 用例库
- **用例库管理**：集中管理测试用例
- **动态生成**：支持用例动态生成
- **用例分类**：支持模块化用例管理

#### 脑图能力
- **Mind Map**：集成脑图功能用于测试用例编写（开发中）

> 说明：用例管理模块目前为初步版本，功能尚未完全开发，后续可能会进行重构

---

### 🚀 性能测试

#### Locust集成
- 集成Locust性能测试框架
- 压测任务创建和执行
- 待完成：数据记录、断言、变量等功能

> 说明：性能测试模块目前为半成品，功能不完善，使用体验不佳，待重构

---

## 🏗️ 技术架构

### 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| **后端框架** | FastAPI | 0.121.3 |
| **编程语言** | Python | 3.12+ |
| **HTTP客户端** | Httpx | 0.28.1 |
| **UI自动化** | Playwright | 1.56.0 |
| **数据库** | MySQL | 8.0+ |
| **缓存** | Redis | 7.1.0 |
| **ORM** | SQLAlchemy | 2.0.44 |
| **定时任务** | APScheduler | 3.10.4 |
| **异步任务** | Celery | 5.4.0 |
| **性能测试** | Locust | 2.42.5 |
| **日志** | Loguru | 0.7.3 |
| **数据验证** | Pydantic | 2.12.4 |

### 项目结构

```
case_auto_hub/
├── app/                    # 应用核心模块
│   ├── controller/         # 控制器层
│   │   ├── interface/      # 接口测试相关接口
│   │   ├── play/          # UI自动化相关接口
│   │   ├── caseHub/       # 用例管理相关接口
│   │   ├── project/       # 项目管理相关接口
│   │   └── user/          # 用户管理相关接口
│   ├── mapper/            # 数据访问层
│   ├── model/             # 数据模型
│   ├── schema/            # 数据验证Schema
│   ├── scheduler/         # 定时任务调度
│   └── ws/                # WebSocket服务
├── croe/                  # 核心执行引擎
│   ├── interface/         # 接口执行引擎
│   │   ├── executor/      # 执行器
│   │   ├── manager/       # 管理器（断言、变量、条件等）
│   │   └── builder/       # 请求构建器
│   └── play/              # UI执行引擎
├── common/                # 公共工具
│   ├── httpxClient.py     # HTTP客户端
│   ├── mysqlClient.py     # MySQL客户端
│   ├── redisClient.py     # Redis客户端
│   └── notifyManager.py   # 通知管理器
├── utils/                 # 工具类
├── enums/                 # 枚举定义
├── resource/              # 资源文件
├── script/                # 脚本文件
├── config.py              # 配置文件
├── main.py                # 应用入口
└── run.py                 # 启动脚本
```

---

## 🚀 快速开始

### 环境准备

#### 1. 安装依赖服务

**MySQL**
```bash
# 创建数据库
CREATE DATABASE autoHub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

**Redis**
```bash
# 确保Redis服务已启动
redis-server
```

**Python**
```bash
# 确保Python版本 >= 3.12
python --version
```

#### 2. 安装项目依赖

```bash
# 克隆项目
git clone https://github.com/yourusername/case_auto_hub.git
cd case_auto_hub

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirment.txt
```

#### 3. 配置文件

编辑 `config.py` 文件，根据本地环境进行配置：

```python
class LocalConfig(BaseConfig):
    # 服务器配置
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = 5050
    DOMAIN = f"http://{SERVER_HOST}:{SERVER_PORT}"
    
    # 任务配置
    TASK_WORKER_POOL_SIZE = 10
    
    # 代理录制
    Record_Proxy = False
    
    # MySQL配置
    MYSQL_SERVER = "127.0.0.1"
    MYSQL_PASSWORD = "your_password"
    
    # Redis配置
    REDIS_DB = 0
    REDIS_SERVER = "127.0.0.1"
    REDIS_URL: str = f"redis://{REDIS_SERVER}:{BaseConfig.REDIS_PORT}/{REDIS_DB}"
    
    # Oracle客户端（可选）
    CX_Oracle_Client_Dir = "/your/instantclient_23_3"
    
    # UI自动化配置
    INIT_PLAY_BROWSER = False
    UI_Headless = True
    UI_Timeout = 10000
    UI_SLOW = 500
    
    # 定时任务配置
    APS = False
    APS_TZ = pytz.timezone('Asia/Shanghai')
```

#### 4. 初始化数据库

执行初始化SQL脚本：

```bash
# 执行初始化脚本
mysql -u root -p autoHub < script/initSQL.sql
```

初始化脚本会创建默认管理员账户：
- 用户名：`admin`
- 密码：`admin123`

#### 5. 启动项目

```bash
使用run.py启动（推荐开发环境）
python run.py
```

启动成功后，访问：
- API文档：http://127.0.0.1:5050/docs
- 前端页面：部署前端项目后访问

#### 6. 部署前端

参考 [前端项目](https://github.com/Caoyongqi912/caseHubWeb) 进行前端部署。

---

## 📸 功能展示

### 🏠 首页数据展示

![首页](resource/index.png)

### 📋 API列表

展示所有接口的概览，支持快速筛选和搜索。

![API列表](resource/api.png)

### 🔍 API详情

查看单个接口的详细信息，包括请求参数、响应示例等。

![API详情](resource/apiDetail.png)

### ⚙️ 前置操作

#### 前置变量
![前置变量](resource/api_before1.png)

#### 前置脚本
![前置脚本](resource/api_before2.png)

#### SQL执行
![SQL执行](resource/api_before3.png)

### 📤 响应提取

从响应数据中提取变量，支持多种提取方式。

![响应提取](resource/extract.png)

### ✅ 接口断言

强大的断言功能，支持多种断言类型。

![接口断言](resource/api_asserts.png)

### 🔧 变量写入

支持在URL、Header、Query、Body、SQL中写入变量。

![变量写入](resource/var0.png)
![变量写入](resource/var1.png)

### 🎯 引用变量

可视化变量引用功能，提升用例编写效率。

![引用变量](resource/set_var.gif)

### 📥 CURL解析导入

支持CURL命令解析导入，快速生成测试用例。

![CURL导入](resource/curl.png)

### 🧪 APITry

在UI中直接执行接口请求，快速验证API可用性。

![APITry](resource/try.gif)

### 🔄 API业务流

支持引用公共API、添加私有API、引用API组、添加逻辑判断、脚本执行、等待等。

![API业务流](resource/caseContents.png)

### 🏃 RunCase调试

支持同步执行和后台执行，实时展示测试日志。

![同步执行](resource/runBySync.gif)
![异步执行](resource/runByAsync.gif)


展示业务步骤的详细执行结果。

![业务步骤详情](resource/caseContentResult.png)

### 📝 业务步骤日志

展示业务步骤的详细执行日志。

![业务步骤日志](resource/caseContentLog.png)

### 📅 Task接口任务

任务可关联多个API用例，支持定时任务执行和结果推送。

![Task接口任务](resource/task_detail.png)

### 📈 Task任务报告

生成并展示任务执行后的详细报告。

![任务报告](resource/report.png)

### 🎭 UI自动化

支持配置方法、环境、公共步骤、操作任务的调度，支持步骤拖拽排序。

![UI自动化](resource/ui_detail.gif)


### 🧠 脑图功能

集成脑图功能用于测试用例编写。

![脑图](resource/mind.png)

### 📊 业务步骤详情结果


### ⏰ Job管理

任务与定时任务分离，支持任务池管理。

![Job管理](resource/job.png)



## 📋 用例&需求管理

添加需求-管理测试用例

### 需求表
![用例需求管理](resource/reqTable.png)

### 需求用例
![需求用例](resource/reqCase.png)

### 用例详情
![用例详情](resource/text_case.png)

---

## ⚙️ 配置说明

### 数据库配置

```python
# MySQL配置
MYSQL_SERVER = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_PASSWORD = "your_password"
MYSQL_DATABASE = 'autoHub'

# 异步MySQL连接
ASYNC_SQLALCHEMY_URI = f'mysql+aiomysql://root:{MYSQL_PASSWORD}@{MYSQL_SERVER}:{MYSQL_PORT}/{MYSQL_DATABASE}'
```

### Redis配置

```python
# Redis配置
REDIS_SERVER = "127.0.0.1"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_URL: str = f"redis://{REDIS_SERVER}:{REDIS_PORT}/{REDIS_DB}"

# Redis Broker（用于Celery）
REDIS_Broker: str = f"redis://{REDIS_SERVER}:{REDIS_PORT}/1"
REDIS_Backend: str = f"redis://{REDIS_SERVER}:{REDIS_PORT}/2"
```

### UI自动化配置

```python
# UI自动化配置
INIT_PLAY_BROWSER = False  # 是否初始化浏览器
UI_Headless = True          # 是否使用无头模式
UI_Timeout = 10000          # 超时时间（毫秒）
UI_SLOW = 500               # 慢动作延迟（毫秒）
```

### 定时任务配置

```python
# 定时任务配置
APS = False  # 是否开启定时任务
APS_TZ = pytz.timezone('Asia/Shanghai')  # 时区

# Redis JobStore
APSJobStores = {
    'default': RedisJobStore(
        db=1,
        jobs_key='apscheduler.jobs',
        run_times_key='apscheduler.run_times',
        host=REDIS_SERVER,
        port=REDIS_PORT,
        password=None
    )
}
```

### 任务池配置

```python
# 任务池配置
TASK_WORKER_POOL_SIZE = 10  # 工作线程池大小
REDIS_WORKER_POOL_BD = 10   # Redis工作池数据库
```

### 通知配置

```python
# 企业微信配置
WeChatBaseUrl = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"

# 邮件配置
Email_Sender_Username = "your_email@163.com"
Email_Sender_Password = "your_password"
Smtp_Server = "smtp.163.com"
Smtp_port = 578
```

---

## 📝 更新日志

### 2026-02-28
- UI重构合并
- 若干优化

### 2026-01-26
- 接口运行拆分重构
- 接口添加执行器LOOP

### 2025-12-15
- Task与定时任务分离（API大致完成）
- 新增JOB模型
- 新增任务池
- 重写APScheduler

### 2025-11-28
- 业务步骤详情结果展示优化
- 日志优化（优化了些细节）

### 2025-11-20
- 增加指定（api、case、task）环境运行能力

### 2025-10-30
- 步骤等待、脚本录入能力

### 2025-10-24
- 接口用例执行重构
- 若干数据库字段更改
- 接口执行调整
- 添加步骤变量判断能力

### 2025-09-17
- 测试用例能力
  - 添加了用例的基本增删改查
  - 复制、拖拽等
  - 用例动态生成
  - 关联需求
  - 用例库

### 2025-08-05
- 新增用例管理CRUD

### 2025-07-25
- UI自动化进行了重写
- 接口执行使用了接口功能、不在自定义
- 添加了UI组能力执行
- 整体UI页面优化

### 2025-05-22
- 集成Locust压测（半成品）
- 待完成：数据记录、断言、变量等

### 2025-05-16
- 断言重构
- 支持JMESPath
- 支持变量断言
- UI重构

### 2025-03-07
- 优化前端代码、接口修改操作优化
- 添加DB链接测试接口



### 2026-04-02
- 前端代码通过AI 样式重构设计
- 用例管理重构优化
---

## 🤝 贡献指南

欢迎贡献代码、提出问题或建议！

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

---

## 📞 联系我

如果您有任何问题或建议，欢迎通过以下方式联系我：

- 微信：![微信](resource/wx.png)
- GitHub Issues：[提交问题](https://github.com/yourusername/case_auto_hub/issues)

---

<div align="center">
**如果觉得这个项目对您有帮助，请给我们一个 ⭐️ Star！**

</div>