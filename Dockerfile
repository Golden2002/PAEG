# PAEG Docker 化（v0.67 单容器最小可行版）
# 用户方案：Docker 统一 Python 3.12——manim 0.19 兼容 3.12，无需隔离 venv。
# 覆盖：教学/闲聊/PPT/讲义/manim 动画 五大场景。
# Python 3.12（manim 0.19 兼容最稳）
FROM python:3.12-slim

# 系统依赖：ffmpeg（manim/音视频）+ build tools（moderngl 备用编译）
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        build-essential \
        pkg-config \
        libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装主依赖（缓存层优化）
COPY 05_实现原型/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# manim 直接装同一镜像（用户方案：统一 3.12，放弃隔离 venv 换部署简化）
RUN pip install --no-cache-dir manim==0.19.0 imageio-ffmpeg

# 复制全部源码（server.py + 前端 + Library 等）
COPY . .

# 持久化数据卷（运行时挂载）
VOLUME ["/app/05_实现原型/users_data", "/app/05_实现原型/downloads", "/app/Library"]

# Flask 端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health').read()" || exit 1

# 启动（入口 server.py）
WORKDIR /app/05_实现原型
CMD ["python", "server.py"]
