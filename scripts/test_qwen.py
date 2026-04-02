from __future__ import annotations

import os

from openai import OpenAI


BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
CHAT_MODEL = os.getenv("DASHSCOPE_CHAT_MODEL", "qwen-plus")
EMBED_MODEL = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4")


def main() -> None:
    if not API_KEY:
        raise RuntimeError("DASHSCOPE_API_KEY is not set.")

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    chat = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "请用一句中文确认你可用。"},
        ],
    )
    print("chat_ok:", chat.choices[0].message.content)

    embedding = client.embeddings.create(
        model=EMBED_MODEL,
        input="健康助手embedding测试",
    )
    print("embedding_ok:", len(embedding.data[0].embedding))


if __name__ == "__main__":
    main()
