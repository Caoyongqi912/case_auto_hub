from sqlalchemy import Column, String, INTEGER, JSON, ForeignKey

from app.model.basic import BaseModel


class AutoJob(BaseModel):
    __tablename__ = "auto_job"

    job_tag = Column(String(100), nullable=False, comment="标签")
    job_id = Column(String(250), nullable=False, unique=True, index=True, comment="任务ID")
    job_name = Column(String(250), nullable=False, comment="任务名称")
    job_running_status = Column(INTEGER, nullable=False, default=0, comment="运行状态")
    job_trigger = Column(String(29), nullable=True, comment="trigger")
    job_executor = Column(String(29), nullable=True, comment="executor")
    job_kwargs = Column(JSON, nullable=True, comment="kwargs")

    project_id = Column(INTEGER, ForeignKey("project.id", ondelete="CASCADE"))

    def __repr__(self):
        return "<AutoJob job_id: %s job_name %s>" % (self.job_id, self.job_name)
