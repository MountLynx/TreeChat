"""WebApp：REST API 覆盖（假客户端注入，无网络）。"""
import json

import pytest
from fastapi.testclient import TestClient
from llm import LLMError, LLMResponse

from treechat.config import TreeChatConfig
from treechat.webapp.app import create_app


class FakeLLM:
    """chat + complete 双能力假客户端（对话轮次 + 卡片提炼）。"""

    def __init__(self) -> None:
        self.fail = False
        self.chat_calls = 0
        self.config = type("Config", (), {"model": "fake-model"})()

    async def chat(self, messages):
        self.chat_calls += 1
        if self.fail:
            raise LLMError("模拟基础设施故障")
        return LLMResponse(content="mock reply", usage={"input_tokens": 1, "output_tokens": 2})

    async def complete(self, **kwargs):
        return LLMResponse(content=json.dumps({"title": "卡片标题", "body": "卡片正文"}))


@pytest.fixture
def api(tmp_path):
    fake = FakeLLM()
    config = TreeChatConfig(data_dir=tmp_path)
    client = TestClient(create_app(config, client_factory=lambda model=None: fake))
    client.fake = fake
    return client


def test_health(api):
    r = api.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and "llmConfigured" in body


def test_session_crud_and_management(api):
    # 创建（默认 200，返回 sid）
    r = api.post("/api/sessions", json={"name": "测试", "system": "sys"})
    assert r.status_code == 200 and r.json()["sid"] == "测试"
    # 重复创建 → 409
    assert api.post("/api/sessions", json={"name": "测试"}).status_code == 409
    # 枚举
    assert [s["sid"] for s in api.get("/api/sessions").json()] == ["测试"]
    # 改名 / 分类 / 归档（会话状态全量返回）
    st = api.post("/api/sessions/测试/rename", json={"name": "改名"}).json()
    assert st["name"] == "改名"
    st = api.post("/api/sessions/测试/category", json={"category": "工作"}).json()
    assert st["category"] == "工作"
    st = api.post("/api/sessions/测试/archive", json={"archived": True}).json()
    assert st["archived"] is True
    # 删除 → 204，之后 404
    assert api.delete("/api/sessions/测试").status_code == 204
    assert api.get("/api/sessions/测试").status_code == 404
    assert api.get("/api/sessions").json() == []


def test_turn_branch_leaf_and_node_rename(api):
    sid = "t"
    api.post("/api/sessions", json={"name": sid})
    st = api.post(f"/api/sessions/{sid}/turn", json={"text": "问一"}).json()
    assert st["pointer"] == 3  # meta=1 → user=2, assistant=3
    assert [n["role"] for n in st["nodes"]] == ["user", "assistant"]
    # 分支：parent=2 长新枝
    st = api.post(f"/api/sessions/{sid}/turn", json={"text": "分支问", "parent": 2}).json()
    assert st["pointer"] == 5
    assert next(n for n in st["nodes"] if n["seq"] == 4)["parent"] == 2
    # 叶子：parent=null
    st = api.post(f"/api/sessions/{sid}/turn", json={"text": "叶子问", "leaf": True}).json()
    assert next(n for n in st["nodes"] if n["seq"] == 6)["parent"] is None
    # 节点命名
    st = api.post(f"/api/sessions/{sid}/nodes/4/rename", json={"label": "概念澄清"}).json()
    assert next(n for n in st["nodes"] if n["seq"] == 4)["label"] == "概念澄清"
    # 非法 parent / 未知节点命名 → 400
    assert api.post(f"/api/sessions/{sid}/turn", json={"text": "x", "parent": 99}).status_code == 400
    assert api.post(f"/api/sessions/{sid}/nodes/99/rename", json={"label": "x"}).status_code == 400


def test_turn_llm_failure_keeps_dangling_then_retry(api):
    sid = "t"
    api.post("/api/sessions", json={"name": sid})
    api.fake.fail = True
    r = api.post(f"/api/sessions/{sid}/turn", json={"text": "问题"})
    assert r.status_code == 502
    st = r.json()["state"]
    assert st["unansweredUser"] == 2 and st["pointer"] is None  # 悬而未答已落盘
    api.fake.fail = False
    st = api.post(f"/api/sessions/{sid}/retry").json()
    assert st["pointer"] == 3


def test_retry_without_dangling_conflicts(api):
    api.post("/api/sessions", json={"name": "x"})
    assert api.post("/api/sessions/x/retry").status_code == 409


def test_cards_flow(api):
    sid = "c"
    api.post("/api/sessions", json={"name": sid})
    api.post(f"/api/sessions/{sid}/turn", json={"text": "讨论"})
    st = api.post(f"/api/sessions/{sid}/cards", json={"instruction": "总结"}).json()
    assert len(st["cards"]) == 1 and st["cards"][0]["pinned"] is True
    cid = st["cards"][0]["id"]
    st = api.post(f"/api/sessions/{sid}/cards/{cid}/pin", json={"pinned": False}).json()
    assert st["cards"][0]["pinned"] is False
    # all 模式再提炼一张
    st = api.post(f"/api/sessions/{sid}/cards", json={"mode": "all"}).json()
    assert len(st["cards"]) == 2
    # 非法区间 → 400
    assert api.post(f"/api/sessions/{sid}/cards",
                    json={"mode": "range", "start": 9, "end": 99}).status_code == 400


def test_sid_path_traversal_rejected(api):
    # Starlette 对 %2F 的解码行为不同：可能 400（到达校验）或 404（路由拒绝），绝不 200
    r = api.get("/api/sessions/..%2F..%2Fsecret")
    assert r.status_code in (400, 404)
    assert api.post("/api/sessions", json={"name": "a/b"}).status_code == 400
