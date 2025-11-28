# CaseHUB

### 接口 & UI 自动化平台

[![FastAPI](https://img.shields.io/badge/FastAPI-blue)](https://www.python.org/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/)
[![Httpx](https://img.shields.io/badge/Httpx-blue)](https://www.python-httpx.org/)
[![Playwright](https://img.shields.io/badge/Playwright-blue)](https://playwright.dev/python/docs/api/class-playwright)
[![Mysql](https://img.shields.io/badge/Mysql-blue)]()
[![Redis](https://img.shields.io/badge/Redis-blue)]()

---

## 🚀 功能特点

### 接口自动化能力

✨ **核心功能**：

- **基础 HTTP 请求**：支持多种 HTTP 请求类型（GET、POST、PUT、DELETE 等）。
- **变量提取与写入**：可从响应中提取变量，支持在后续请求中使用。
- **断言功能**：提供响应状态码、内容等多种断言验证。
- **前后置脚本**：在用例执行前后执行自定义 Python 脚本。
- **各种函数变量写入**：在用例执行前后执行自定义函数变量。
- **调试模式**：逐步执行测试用例，便于精准排查问题。
- **用例执行**：支持单个或批量用例的执行。
- **定时任务**：定时执行接口测试任务，适用于定期测试。
- **报告展示**：自动生成并展示 HTML 格式的测试报告，明确显示成功与失败的详细信息。
- **实时日志可视化**：在测试执行过程中实时展示日志，便于进度监控。
- **接口录制（未完善）**：录制接口请求并快速生成对应的测试用例。（感觉不好用、思路不是很对）

### UI 自动化功能

✨ **Playwright 集成**：

- **UI 自动化支持**：集成了 Playwright，能够执行浏览器自动化测试，模拟用户操作界面。
- **步骤录入**：支持在 UI 测试中录入测试步骤，便于快速创建测试用例。
- **前后置接口请求**：每个步骤可与前后置接口请求结合，动态调整测试流程。
- **全局变量**：支持全局变量的管理，步骤和请求中的变量可以全局共享，方便管理和使用。
- **公共步骤编辑**：支持创建和管理公共步骤，可以重复使用，减少冗余，提升效率。
- **任务管理**：与接口测试类似，UI 测试任务支持定时执行与结果推送，支持企业微信等推送方式。
- **SQL 支持（未完成）**：计划在未来版本中支持 SQL 操作，增强数据处理能力。
- **IF 条件判断执行**：支持根据条件判断执行特定步骤，灵活控制测试流程。

---

## 🖥️ UI 展示

#### [前端项目地址](https://github.com/Caoyongqi912/caseHubWeb)

### 📊 首页数据展示

![index](resource/index.png)

### 📊 **API 列表**

展示所有接口的概览：

![API列表](resource/apiList.png)

---

### 🔍 **API 详情**

查看单个接口的详细信息

![API详情](resource/apiDetail.png)

---

### **前置操作**

-  **前置变量**
![前置](resource/api_before1.png)
- **前置脚本** 
![前置](resource/api_before2.png)
- **SQL执行**
![前置](resource/api_before3.png)


- **响应提取**
![extract](resource/extract.png)

- **接口断言**
![assert](resource/assert.png)

- **变量写入支持**
  - url
  - header
  - query
  - body
  - exec sql

   ![assert](resource/var1.png)
   ![assert](resource/var0.png)

-  **“引用变量”能力**
![set_var](resource/set_var.gif)

- **CURL解析导入**
![curl_var](resource/curl.png)
### 🖱️ **APITry**

支持在 UI 中直接执行接口请求，快速验证 API 可用性：

![APITry](resource/try.gif)

---

### ➕ **API 业务流**

支持：
- 引用公共 API
- 添加私有 API
- 引用API 组
- 添加 逻辑判断
- 添加 脚本执行
- 添加 等待

![img.png](resource/caseContents.png)

---

#### ⚡ **RunCase 调试业务流用例**

- **同步执行**：实时展示测试日志，确保每个步骤都可监控。
- **后台执行 & 轮询结果**：适用于长期任务或需要在后台执行的测试。

---

### 📅 **Task 接口任务**

任务可关联多个 API 用例，支持：

- 定时任务执行
- 执行结果推送（目前支持企业微信）

![Task接口任务](resource/task_detail.png)

---

### 📈 **Task 任务报告**

生成并展示任务执行后的详细报告，帮助团队了解测试状态。

![Report](resource/report.png)

## UI 自动化

- 支持配置方法、环境、公共步骤、操作任务的调度
- UI 执行步骤前后置接口请求、SQL（未完成）、IF 条件判断执行
- 步骤拖拽排序

![ui](resource/ui_detail.gif)

---

## 🛠️ 安装与使用

### 安装依赖

1. 环境准备
    - MYSQL
        - 创建一个database 'autoHub'
    - REDIS
    - Python 3.12
        - env `pip install requirment.txt`

2. 配置文件

    - 配置自己的数据库等相关内容
    - 编辑 `config.py`，根据本地情况进行自定义
    - 初始化数据到数据库 执行 `script/initSQL.sql`
   
    ```python 
    MYSQL_DATABASE = 'autoHub' # dbtabase
    
    class LocalConfig(BaseConfig):
        SERVER_HOST: str = "127.0.0.1" # or ur ip
        SERVER_PORT: int = 5050
        
        APS = False # 是否开启定时任务
        Record_Proxy = False # 是否开启代理录制
        
        MYSQL_SERVER = "127.0.0.1" # 数据库IP 
        MYSQL_PASSWORD = "your password" # 数据库密码
    
        # redis
        REDIS_DB = 0
        REDIS_SERVER = "127.0.0.1"
        REDIS_URL: str = f"redis://{REDIS_SERVER}:{BaseConfig.REDIS_PORT}/{REDIS_DB}"
        # Oracle 客户端 链接oracle 可能需要用的
        CX_Oracle_Client_Dir = "/your/instantclient_23_3"
        
    ```
3. 启动项目
    - `main.py`
      - 一些钩子函数
      - 初始化db （项目启动自动建表）
      - 初始化aps 是否启动定时任务
      - 初始化redis 连接redis
      - 代理 
    - `run.py`
      - 右键直接运行

5.前端部署见 [前端项目](https://github.com/Caoyongqi912/caseHubWeb)

6.其他先自行探索吧 

> 存在疑问？联系我
> 觉得还行 给个Star
>
![](resource/wx.png)



---
#### change log
- 2025-03-07
  - 优化前端代码、接口修改操作优化
  - 添加DB链接测试接口

- 2025-05-16
  - 断言重构
  - 支持jmespath
  - 支持变量断言
  - ui 重构
  - ![api_assert.png](resource/api_assert.png)


- 2025-05-22
 - 集成locust 压测 （半成品）
 - 待完成 数据记录、断言、变量等
 - ![api_perf.png](resource/api_perf.png)

- 2025-07-25
 - UI 自动化进行了重写
 - 接口执行使用了接口功能、不在自定义
 - 添加了UI 组能力执行
 - 整体UI页面优化

- 2025-08-05
  - ~~新增用例管理curd~~
  - ![case_hub.png](resource/casehub.png)
- 2025-09-17
  - 测试用例能力
    - 添加了用例的基本增删改查
    - 复制、拖拽等
    - 用例动态生成
    - 关联需求
    - 用例库
    - ![casehub.gif](resource/casehub.gif)
- 2025-10-24
  - 接口用例执行重构
    - 若干数据库字段更改
    - 接口执行调整
  - 添加步骤变量判断能力
- 2025-10-30
  - 步骤 等待、脚本录入能力
- 2025-11-20
  - 增加指定（api、case、task）环境运行能力


     