#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/2/27# @Author : cyq# @File : locustClient# @Software: PyCharm# @Desc:import subprocessfrom locust import HttpUser, task, between, constant, events, run_single_userclass LocustClient:    @staticmethod    # 示例：动态生成Locust任务    def create_locust_task(api_config):        class DynamicUser(HttpUser):            @task            def test_endpoint(self):                self.client.request(                    method=api_config.method,                    url=api_config.url,                    headers=api_config.headers,                    json=api_config.body_template                )        return DynamicUser# 示例：启动Locust测试# @app.post("/start-test")# async def start_test(config: TestConfig):#     locust_process = subprocess.Popen(#         ["locust", "-f", "dynamic_tasks.py", "--headless", "--users", str(config.users)]#     )#     return {"status": "started", "process_id": locust_process.pid}