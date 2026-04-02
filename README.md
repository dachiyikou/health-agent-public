# Health Agent Public

一个基于 FastAPI 的健康助手原型项目，包含健康 Copilot、健康档案、记录录入和提醒管理四个核心模块。

## Current Layout

- `app/`: FastAPI Web 应用、页面路由、API 路由、模板和静态资源
- `health_agent/`: 核心运行时、agents、services、repositories、schemas、memory、tools
- `scripts/`: 手动运维/验证脚本，例如 Qdrant collection 重建和 Qwen 连通性测试
- `tests/`: 轻量回归测试

## Prerequisites

- Python 3.11+
- Qdrant
- DashScope API Key

## Configuration

1. 在项目根目录创建 `.env.local`
2. 参考 `.env.example` 填写至少以下配置

```env
DASHSCOPE_API_KEY=your_key
VECTOR_DB_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_key
```

常用配置项都集中在 `health_agent/config.py`。

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run The Web App

推荐直接使用 Uvicorn:

```bash
python3 -m uvicorn app.main:app --reload
```

也可以使用项目自带脚本:

```bash
bash health_agent/run.sh
```

启动后可以访问:

- `http://127.0.0.1:8000/healthz`
- `http://127.0.0.1:8000/copilot`
- `http://127.0.0.1:8000/profile`
- `http://127.0.0.1:8000/records`
- `http://127.0.0.1:8000/reminders`

## Utility Scripts

重建 Qdrant collections:

```bash
python3 -m scripts.rebuild_qdrant_collections
```

验证 DashScope/Qwen 聊天与 embedding:

```bash
python3 -m scripts.test_qwen
```

## Test

```bash
python3 -m unittest tests.test_project_layout -v
```

这个测试主要用于防止旧的路径依赖和过时启动命令重新回到仓库。
