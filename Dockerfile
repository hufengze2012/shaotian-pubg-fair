FROM python:3.11-slim

WORKDIR /app

# 使用国内镜像加速（极空间在国内网络环境）
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 只复制运行需要的文件，不复制 config.json（通过 volume 挂载）
COPY pubg_web.py .
COPY pubg_web_app/ pubg_web_app/
COPY analyze_pubg.py .

EXPOSE 8000

CMD ["python", "pubg_web.py", "--host", "0.0.0.0", "--port", "8000"]
