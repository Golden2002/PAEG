"""PAEG 服务配置层(v0.40 P1-1 server.py Phase1 拆分)。

集中托管 server.py 的"只读配置":
  - 环境变量(SECRET_KEY / LLM_PROVIDER / LLM_MODEL / PORT / MCP_PORT / PAEG_HOST)
  - 路径常量(GUI_DIR / FALLBACK_DOWNLOAD_DIR / PROJECT_DIR)
  - HTTP 绑定(APP_HOST)

设计原则:
  - 只放"取值后不再变更"的常量(不含带副作用的 print/初始化)
  - 副作用(启动警告 / LLM 实例化 / Flask secret_key 赋值)保留在 server.py
  - server.py 通过 `from config import SECRET_KEY, LLM_PROVIDER, ...` 使用

注意: 业务逻辑禁止搬到这里——本文件只承担"配置读取与路径常量"两件事。
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

# server.py 所在目录(05_实现原型/)
PROJECT_DIR: Path = Path(__file__).resolve().parent

# 前端 GUI 目录(05_实现原型 的兄弟目录: 09_GUI前端/)
GUI_DIR: Path = PROJECT_DIR.parent / "09_GUI前端"

# 文件生成器失败时的下载目录回退(FileGenerator.download_dir 不可用时使用)
FALLBACK_DOWNLOAD_DIR: str = str(PROJECT_DIR / "downloads")


# ---------------------------------------------------------------------------
# 环境变量: 安全基线
# ---------------------------------------------------------------------------

# P0-2 安全基线: 生产必须设置 PAEG_SECRET_KEY; 开发默认值仅供本地启动
# v0.43 ⭐ P0-E 升级：双轨制——PAEG_ENV=production 时强制 KeyError（堵生产裸跑漏洞），
# 开发环境（development 默认）保留默认值丝滑启动，不破坏现有部署。
PAEG_ENV: str = os.environ.get("PAEG_ENV", "development")
SECRET_KEY: str = os.environ.get("PAEG_SECRET_KEY", "dev-insecure-change-me")

# 是否使用开发默认值(启动期打印警告用, server.py 读取此 flag)
SECRET_KEY_IS_DEV_DEFAULT: bool = SECRET_KEY == "dev-insecure-change-me"

# 生产环境强制密钥（fail-fast：缺失即启动失败，防裸跑）
if PAEG_ENV == "production" and SECRET_KEY_IS_DEV_DEFAULT:
    raise RuntimeError(
        "[PAEG][SECURITY] PAEG_ENV=production 时必须设置 PAEG_SECRET_KEY 环境变量！"
        "（复制 .env.example 并填写随机字符串）"
    )


# ---------------------------------------------------------------------------
# 环境变量: LLM 选型
# ---------------------------------------------------------------------------

# v0.5 默认 auto 自动发现真实 LLM 凭据
LLM_PROVIDER: str = os.environ.get("PAEG_LLM_PROVIDER", "auto")

# 未设置则交给 create_llm 自行选默认模型
LLM_MODEL = os.environ.get("PAEG_LLM_MODEL")


# ---------------------------------------------------------------------------
# 环境变量: HTTP / MCP 端口
# ---------------------------------------------------------------------------

# 主服务端口(v0.19+ 标准: 开发 5000, 生产可改)
APP_PORT: int = int(os.environ.get("PORT", 5000))

# 绑定地址(0.0.0.0 让 LAN 设备也可访问; 本机测试可改为 127.0.0.1)
APP_HOST: str = os.environ.get("PAEG_HOST", "0.0.0.0")

# MCP 工具网关端口(v0.19 P0-3 后台线程)
MCP_PORT: int = int(os.environ.get("MCP_PORT", 8765))


# ---------------------------------------------------------------------------
# 公开符号(避免 from config import * 误带私有项)
# ---------------------------------------------------------------------------
__all__ = [
    # 路径
    "PROJECT_DIR", "GUI_DIR", "FALLBACK_DOWNLOAD_DIR",
    # 安全
    "SECRET_KEY", "SECRET_KEY_IS_DEV_DEFAULT",
    # LLM
    "LLM_PROVIDER", "LLM_MODEL",
    # 端口
    "APP_PORT", "APP_HOST", "MCP_PORT",
]