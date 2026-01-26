FROM python:3.12-slim

# 只安装必要依赖（不更换系统源）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    default-mysql-client \
    redis-tools \
    libaio1 \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /case_auto_hub

# 复制依赖文件（注意文件名）
COPY requirment.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirment.txt -i https://mirrors.aliyun.com/pypi/simple/

# 安装Playwright浏览器
RUN playwright install --with-deps

# 复制项目文件
COPY . .

RUN chmod +x wait-for.sh

# 暴露端口
EXPOSE 5050

CMD ["./wait-for.sh", "gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:hub"]