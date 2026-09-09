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
        self.complete_calls = 0
        self.config = type("Config", (), {"model": "fake-model"})()

    async def chat(self, messages):
        self.chat_calls += 1
        if self.fail:
            raise LLMError("模拟基础设施故障")
        return LLMResponse(content="mock reply", usage={"input_tokens": 1, "output_tokens": 2})

    async def complete(self, **kwargs):
        self.complete_calls += 1
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
    # seqs 模式：显式节点列表；空列表 → 400；未知节点 → 400
    st = api.post(f"/api/sessions/{sid}/cards",
                  json={"mode": "seqs", "seqs": [2, 3]}).json()
    assert len(st["cards"]) == 3
    assert api.post(f"/api/sessions/{sid}/cards",
                    json={"mode": "seqs", "seqs": []}).status_code == 400
    assert api.post(f"/api/sessions/{sid}/cards",
                    json={"mode": "seqs", "seqs": [2, 99]}).status_code == 400


def test_card_edit_delete_export_import(api):
    sid = "c"
    api.post("/api/sessions", json={"name": sid})
    api.post(f"/api/sessions/{sid}/turn", json={"text": "讨论"})
    st = api.post(f"/api/sessions/{sid}/cards", json={"instruction": "总结"}).json()
    cid = st["cards"][0]["id"]
    # 编辑：整体替换标题/正文，其余字段不动；重放一致（重开由 registry 缓存覆盖不了 → 全量状态即可）
    st = api.patch(f"/api/sessions/{sid}/cards/{cid}",
                   json={"title": "新标题", "body": "新正文"}).json()
    card = st["cards"][0]
    assert (card["title"], card["body"], card["fromPath"]) == ("新标题", "新正文", [2, 3])
    # 导出：markdown 附件
    r = api.get(f"/api/sessions/{sid}/cards/{cid}/export")
    assert r.status_code == 200
    assert r.text.startswith("# 新标题") and "新正文" in r.text
    assert "attachment" in r.headers["content-disposition"]
    # 导入：不经 LLM 直接落卡（fake.complete 若被调用会覆盖同标题 → 用计数确认没走 LLM）
    calls_before = api.fake.complete_calls
    st = api.post(f"/api/sessions/{sid}/cards/import",
                  json={"title": "导入卡", "body": "导入正文", "instruction": "导入"}).json()
    assert api.fake.complete_calls == calls_before
    assert [c["title"] for c in st["cards"]] == ["新标题", "导入卡"]
    assert st["cards"][1]["pinned"] is True and st["cards"][1]["fromPath"] == []
    # 删除 → 全量状态不再含；未知卡片 400
    st = api.delete(f"/api/sessions/{sid}/cards/{cid}").json()
    assert [c["id"] for c in st["cards"]] != [cid]
    assert api.delete(f"/api/sessions/{sid}/cards/{cid}").status_code == 400
    assert api.patch(f"/api/sessions/{sid}/cards/{cid}",
                     json={"title": "t", "body": "b"}).status_code == 400


def test_cards_library_across_sessions(api):
    api.post("/api/sessions", json={"name": "甲"})
    api.post("/api/sessions", json={"name": "乙"})
    api.post("/api/sessions/甲/turn", json={"text": "讨论"})
    api.post("/api/sessions/甲/cards", json={"instruction": "总结"})
    api.post("/api/sessions/乙/cards/import",
             json={"title": "乙卡", "body": "乙正文"})
    lib = api.get("/api/cards").json()
    assert sorted((e["sid"], e["title"]) for e in lib) == \
        sorted([("甲", "卡片标题"), ("乙", "乙卡")])
    by_sid = {e["sid"]: e for e in lib}
    assert by_sid["甲"]["sessionName"] == "甲" and by_sid["甲"]["pinned"] is True
    assert by_sid["乙"]["pinned"] is True
    # 复制导入：把甲的卡片导入乙 → 乙多一张，甲不变（各自独立副本）
    jia = by_sid["甲"]
    st = api.post("/api/sessions/乙/cards/import",
                  json={"title": jia["title"], "body": jia["body"],
                        "instruction": f"导入自「{jia['sessionName']}」"}).json()
    assert [c["title"] for c in st["cards"]] == ["乙卡", "卡片标题"]
    assert st["cards"][1]["id"] != jia["id"]  # 新 id，不建立跨文件引用


def test_sid_path_traversal_rejected(api):
    # Starlette 对 %2F 的解码行为不同：可能 400（到达校验）或 404（路由拒绝），绝不 200
    r = api.get("/api/sessions/..%2F..%2Fsecret")
    assert r.status_code in (400, 404)
    assert api.post("/api/sessions", json={"name": "a/b"}).status_code == 400
