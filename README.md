# Health Agent Public

一个基于 FastAPI 的健康助手原型项目，包含健康 Copilot、健康档案、记录录入和提醒管理四个核心模块。

## Current Layout

- `app/`: FastAPI Web 应用、页面路由、API 路由、模板和静态资源
- `health_agent/`: 核心运行时、agents、services、repositories、schemas、memory、tools
- `scripts/`: 手动运维/验证脚本


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

常用配置项都集中在 `health_agent/config.py`

## demo picture
1.对话界面
<img width="1872" height="906" alt="image" src="https://github.com/user-attachments/assets/832ed491-993a-459c-91af-8f76ada80591" />
2.健康档案界面
<img width="1852" height="917" alt="image" src="https://github.com/user-attachments/assets/85f3a2c8-cf8d-46ce-b4b4-7b767a4d66fc" />
3.身体记录界面
<img width="1512" height="891" alt="image" src="https://github.com/user-attachments/assets/992fb7ee-6ab0-4674-b706-fd50aaab7a5c" />
4.提醒界面
<img width="1518" height="818" alt="image" src="https://github.com/user-attachments/assets/e5a6e1bb-773a-4f2e-98b6-7366e4769bc8" />




