"""WebUI 开发服务器：mock LLM + 独立临时数据目录。

用途：前端开发/演示/冒烟测试，不需要 SpecModule 配置链（无 API key 也能跑）。
真实服务用 `treechat webui`。

    python webui/devserver.py [--port 8700]
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import uvicorn
from llm import LLMResponse

from treechat.config import TreeChatConfig
from treechat.webapp.app import create_app


class MockLLM:
    """chat + complete 双能力 mock：回复回显 + 固定卡片 JSON。"""

    config = type("Config", (), {"model": "mock-model"})()

    async def chat(self, messages):
        current = messages[-1].content
        reply = (
            f"这是 **mock 回复**（devserver）。你刚才说：「{current[:60]}」\n\n"
            "- 当前路径由 `path_to(指针)` 组装\n"
            "- 在树页签点节点可开分支 / 命名\n"
        )
        return LLMResponse(content=reply, usage={"input_tokens": 10, "output_tokens": 20})

    async def complete(self, **kwargs):
        payload = json.dumps(
            {"title": "冒烟测试卡片",
             "body": "## 要点\n\n- devserver mock 提炼的卡片正文\n- 脱离原对话可独立读懂"}
        )
        return LLMResponse(content=payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8700)
    args = parser.parse_args()
    data_dir = Path(tempfile.gettempdir()) / "treechat-webui-dev"
    config = TreeChatConfig(data_dir=data_dir)
    print(f"devserver: data_dir = {data_dir}")
    uvicorn.run(
        create_app(config, client_factory=lambda model=None: MockLLM()),
        host=args.host,
        port=args.port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
