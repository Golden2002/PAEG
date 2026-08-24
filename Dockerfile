# PAEG Docker 化（v0.67 单容器最小可行版 → v0.73 魔搭部署兼容）
# 用户方案：Docker 统一 Python 3.12——manim 0.19 兼容 3.12，无需隔离 venv。
# 覆盖：教学/闲聊/PPT/讲义/manim 动画 五大场景。
# 魔搭创空间（ModelScope Studio）要求：服务监听 7860 端口 + ms_deploy.json 声明
#   port=7860 + sdk_type=docker。通过 PORT 环境变量切换（config.py 已支持）。
#   本地 docker-compose 传 PORT=5000；魔搭平台自动注入 PORT=7860（或 ms_deploy.json）。

# Python 3.12（manim 0.19 兼容最稳）
FROM python:3.12-slim

# 系统依赖：ffmpeg（manim/音视频）+ build tools + Pango/Cairo/GLib（manimpango 必需）
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        build-essential \
        pkg-config \
        libcairo2-dev \
        libpango1.0-dev \
        libglib2.0-dev \
        libgirepository1.0-dev \
        texlive-latex-base \
        texlive-fonts-recommended \
        texlive-lang-chinese \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装主依赖（缓存层优化）
COPY 05_实现原型/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# manim 直接装同一镜像（用户方案：统一 3.12，放弃隔离 venv 换部署简化）
RUN pip install --no-cache-dir manim==0.19.0 imageio-ffmpeg

# 复制全部源码（server.py + 前端 + Library 等）
COPY . .

# §3.59 ⭐ opencode auth.json 注入（Docker 无本地凭据——若项目根存在 auth.json 备份则复制，
# 使 llm_api 的 fallback 链能读到 DeepSeek key；.gitignore 已排除不入库，由部署前手动放置）
# 注意：auth.json 在 .gitignore 中（敏感），Docker 构建上下文需手动放入项目根
RUN if [ -f /app/auth.json ]; then mkdir -p /root/.config/opencode && cp /app/auth.json /root/.config/opencode/auth.json && echo "[PAEG] auth.json 已注入 /root/.config/opencode/"; else echo "[PAEG] 无 auth.json（用环境变量/Secrets 配 key）"; fi

# 持久化数据卷（运行时挂载）
VOLUME ["/app/05_实现原型/users_data", "/app/05_实现原型/downloads", "/app/Library"]

# 魔搭创空间固定暴露 7860；本地 compose 用 5000（PORT 环境变量覆盖，默认 5000 保持本地行为）
ENV PORT=7860
EXPOSE 7860

# 健康检查（/api/health 已在 server.py L379 实现）
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/api/health').read()" || exit 1

# 启动（入口 server.py；APP_PORT 读 PORT 环境变量）
WORKDIR /app/05_实现原型
CMD ["python", "server.py"]
