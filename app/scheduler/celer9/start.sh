# 启动 Worker
celery -A app.scheduler.celer9.app:celery_app worker -l info

# 启动 Beat 调度器
celery -A app.scheduler.celer9.app:celery_app beat -l info