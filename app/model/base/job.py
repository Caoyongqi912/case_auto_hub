from sqlalchemy import Column, String, INTEGER, JSON, ForeignKey, BOOLEAN

from app.model.basic import BaseModel


class AutoJob(BaseModel):
    __tablename__ = "auto_job"

    job_type = Column(INTEGER, nullable=False, comment="类型")
    job_name = Column(String(250), nullable=False, comment="任务名")
    job_task_ids = Column(JSON, nullable=True, comment="任务id  'xxx,abc,qwe' ")
    job_enabled = Column(BOOLEAN, nullable=False, default=True, comment="是否启用")
    job_trigger_type = Column(String(29), nullable=True, comment="trigger_type")

    # 执行时间。仅当trigger_type为once 有效
    job_execute_time = Column(String(29), nullable=True, comment="execute_time")
    # 执行corn 。仅当trigger_type为cron 有效
    job_execute_cron = Column(String(29), nullable=True, comment="corn")
    # 执行间隔。仅当trigger_type为fixedRate 、
    job_execute_interval = Column(INTEGER, nullable=True, comment="interval")

    job_max_retry_count = Column(INTEGER, nullable=True, default=0, comment="最大重试次数")
    job_retry_interval = Column(INTEGER, nullable=True, default=0, comment="重试间隔")

    job_executor = Column(String(29), nullable=True, comment="executor")
    job_kwargs = Column(JSON, nullable=True, comment="kwargs")

    job_push_enabled = Column(BOOLEAN, nullable=True, default=False, comment="是否推送")
    job_push_id = Column(INTEGER, ForeignKey("push_config.id", ondelete="SET NULL"), nullable=True)

    project_id = Column(INTEGER, ForeignKey("project.id", ondelete="CASCADE"))
    job_running_status = Column(INTEGER, nullable=False, default=0, comment="运行状态")

    def __repr__(self):
        return f"<AutoJob(id={self.id}, name={self.job_name}, type={self.job_type}, enabled={self.job_enabled}, tasks:{self.job_task_ids})>"
