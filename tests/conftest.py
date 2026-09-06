"""共享假客户端与 session 工厂。"""
import json

import pytest
from llm import LLMError, LLMResponse


class FakeChatClient:
    """带 chat() 的假客户端：固定回复，记录调用（轮次测试用）。"""

    def __init__(self, reply: str = "mock reply") -> None:
        self.reply = reply
        self.calls: list[list] = []
        self.fail = False

    async def chat(self, messages):
        self.calls.append(list(messages))
        if self.fail:
            raise LLMError("模拟基础设施故障")
        return LLMResponse(content=self.reply, usage={"input_tokens": 1, "output_tokens": 2})


class FakeCardClient:
    """带 complete() 的假客户端：返回合法卡片 JSON（走 call_harness 校验路径）。"""

    async def complete(self, **kwargs):
        return LLMResponse(content=json.dumps({"title": "卡片标题", "body": "卡片正文"}))


@pytest.fixture
def fake_chat():
    return FakeChatClient()


@pytest.fixture
def fake_card_client():
    return FakeCardClient()
