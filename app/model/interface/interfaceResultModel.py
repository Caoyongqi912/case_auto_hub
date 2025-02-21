#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/26# @Author : cyq# @File : interfaceResultModel# @Software: PyCharm# @Desc:from sqlalchemy import Column, INTEGER, String, ForeignKey, TEXT, JSON, DATETIME, Float, DATEfrom datetime import datetime, datefrom app.model import BaseModelclass InterfaceResultModel(BaseModel):    __tablename__ = 'interface_result'    interfaceID = Column(INTEGER, ForeignKey('interface.id', ondelete='CASCADE'), comment="所属用例")    interfaceName = Column(String(20), comment="用例名称")    interfaceUid = Column(String(20), comment="用例Uid")    interfaceDesc = Column(String(50), comment="用例描述")    interfaceProjectId = Column(INTEGER, comment="所属项目")    interfacePartId = Column(INTEGER, comment="所属模块")    interfaceEnvId = Column(INTEGER, comment="所属环境")    interfaceGroupId = Column(INTEGER, comment="所属组")    startTime = Column(DATETIME, default=datetime.now, comment="开始时间")    useTime = Column(String(50), nullable=True, comment="用时")    response_txt = Column(TEXT, nullable=True, comment="响应报文")    response_status = Column(INTEGER, comment="响应Code")    response_head = Column(JSON, nullable=True, comment="响应头")    request_head = Column(JSON, nullable=True, comment="请求头")    request_txt = Column(TEXT, nullable=True, comment="请求报文")    request_method = Column(String(10), nullable=True, comment="请求方法")    extracts = Column(JSON, nullable=True, comment="请求变量")    asserts = Column(JSON, nullable=True, comment="断言信息")    starterId = Column(INTEGER, comment="运行人ID")    starterName = Column(String(20), comment="运行人姓名")    result = Column(String(10), nullable=False, comment="运行结果")    interface_case_result_Id = Column(INTEGER, ForeignKey("interface_case_result.id",                                                          ondelete='CASCADE'), nullable=True, comment="所属case result")    interface_task_result_Id = Column(INTEGER, ForeignKey("interface_task_result.id",                                                          ondelete='CASCADE'), nullable=True, comment="所属task result")    @property    def baseInfo(self):        return {            "id": self.id,            "interfaceID": self.interfaceID,            "interfaceName": self.interfaceName,            "interfaceUid": self.interfaceUid,            "interfaceDesc": self.interfaceDesc,            "interfaceEnvId": self.interfaceEnvId,            "request_method": self.request_method,            "useTime": self.useTime,            "response_status": self.response_status,            "result": self.result        }    def __repr__(self):        return f"<InterfaceResult(id={self.id}, interfaceID={self.interfaceID}, interfaceName={self.interfaceName}, result={self.result})>"class InterfaceCaseResultModel(BaseModel):    __tablename__ = 'interface_case_result'    interfaceCaseID = Column(INTEGER, ForeignKey('interface_case.id', ondelete='CASCADE'), comment="所属用例")    interfaceCaseName = Column(String(20), comment="用例名称")    interfaceCaseUid = Column(String(20), comment="用例Uid")    interfaceCaseDesc = Column(String(50), comment="用例描述")    interfaceCaseProjectId = Column(INTEGER, comment="所属项目")    interfaceCasePartId = Column(INTEGER, comment="所属模块")    interfaceLog = Column(TEXT, nullable=True, comment="运行日志")    progress = Column(Float, default=0.0, comment="进度")    startTime = Column(DATETIME, default=datetime.now, comment="开始时间")    useTime = Column(String(20), nullable=True, comment="用时")    total_num = Column(INTEGER, default=0, comment="总共数量")    success_num = Column(INTEGER, default=0, comment="成功数量")    fail_num = Column(INTEGER, default=0, comment="失败数量")    starterId = Column(INTEGER, comment="运行人ID")    starterName = Column(String(20), comment="运行人姓名")    status = Column(String(10), nullable=True, comment="运行状态")    result = Column(String(10), nullable=True, comment="运行结果")    interface_task_result_Id = Column(INTEGER, ForeignKey("interface_task_result.id",                                                          ondelete='CASCADE'), nullable=True, comment="所属task result")    def __repr__(self):        return (            f"<InterfaceCaseResult(id={self.id}, interfaceCaseID={self.interfaceCaseID}, interfaceCaseName={self.interfaceCaseName},"            f"successNum={self.success_num} failNum={self.fail_num}"            f"  result={self.result})>")class InterfaceTaskResultModel(BaseModel):    __tablename__ = 'interface_task_result'    status = Column(String(10), default="RUNNING", comment="状态")  # "RUNNING","DONE"    result = Column(String(10), nullable=True, comment="运行结果")  # SUCCESS FAIL    totalNumber = Column(INTEGER, comment="总运行数量")    successNumber = Column(INTEGER, default=0, comment="成功数量")    failNumber = Column(INTEGER, default=0, comment="失败梳理")    startBy = Column(INTEGER, nullable=False, comment="1user 2robot")    starterName = Column(String(20), nullable=True, comment="运行人名称")    starterId = Column(INTEGER, nullable=True, comment="运行人ID")    totalUseTime = Column(String(20), comment="运行时间")    start_time = Column(DATETIME, default=datetime.now, nullable=True, comment="开始时间")    end_time = Column(DATETIME, nullable=True, comment="结束时间")    taskId = Column(INTEGER, ForeignKey("interface_task.id", ondelete="CASCADE"), nullable=True)    taskUid = Column(String(10), nullable=False, comment="task索引")    taskName = Column(String(20), nullable=True, comment="任务名称")    runDay = Column(DATE, default=date.today(), comment="运行日期")    progress = Column(Float, default=0, comment="进度")    interfaceProjectId = Column(INTEGER, comment="所属项目")    interfacePartId = Column(INTEGER, comment="所属模块")    def __repr__(self):        return (            f"<Task Result l(taskId='{self.taskId}', taskName='{self.taskName}', "            f"runDay='{self.runDay}',status='{self.status}'),result='{self.result})>'")