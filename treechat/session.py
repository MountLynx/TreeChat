"""TreeChatSession —— 编程 API 门面：轮次 + 卡片（组合 Conversation 与 llm_bridge）。

轮次持久时序（spec §2.2）：send 先落 user_msg；complete 调 LLM 后落 assistant_msg。
LLM 失败 → 悬而未答节点保留，turn_retry 在原节点下补 assistant（问题不丢、不重复）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import llm_bridge
from .config import TreeChatConfig
from .core.context import TokenWindowStrategy, WindowStrategy, assemble
from .core.conversation import Conversation
from .core.errors import TreeChatError
from .core.events import SessionMeta
from .core.store import read_session_meta


@dataclass
class TreeChatSession:
    """一个打开的会话 + LLM 客户端 + 窗口策略。"""

    conversation: Conversation
    client: Any
    window: WindowStrategy | None = field(default_factory=TokenWindowStrategy)
    card_llm: Any = None
    """卡片提炼客户端（需支持 complete）；None = 复用 client（真客户端两者都有）。"""

    # ── 构造 ──

    @classmethod
    def create(cls, path: Path, name: str, system: str = "", *,
               model: str | None = None,
               window: WindowStrategy | None = None) -> "TreeChatSession":
        conv = Conversation.create(path, name, system)
        return cls(conversation=conv, client=llm_bridge.create_client(model),
                   window=_window_or_default(window))

    @classmethod
    def open(cls, path: Path, *, model: str | None = None,
             window: WindowStrategy | None = None) -> "TreeChatSession":
        conv = Conversation.open(path)
        return cls(conversation=conv, client=llm_bridge.create_client(model),
                   window=_window_or_default(window))

    # ── 轮次 ──

    def send(self, text: str, *, leaf: bool = False) -> int:
        """落 user_msg（先持久化，防丢），返回其 seq。"""
        return self.conversation.append_user(text, leaf=leaf)

    async def complete(self, user_seq: int) -> int:
        """组装 → chat → 落 assistant_msg → 指针推进。LLMError 上抛。"""
        conv = self.conversation
        if user_seq not in conv.nodes or conv.nodes[user_seq].role != "user":
            raise TreeChatError(f"complete 目标必须是 user 节点: {user_seq}")
        ctx = assemble(conv.path_to(user_seq), conv.system,
                       conv.cards.pinned_cards(), strategy=self.window)
        reply, usage = await llm_bridge.chat_turn(
            self.client, ctx.system, ctx.history, ctx.current)
        return conv.append_assistant(user_seq, reply, usage=usage)

    async def turn(self, text: str, *, leaf: bool = False) -> int:
        """send + complete 一步走。失败时 user 节点已落盘（悬而未答），turn_retry 重试。"""
        seq = self.send(text, leaf=leaf)
        return await self.complete(seq)

    async def turn_retry(self, user_seq: int) -> int:
        """对悬而未答的 user 节点重新调 LLM。"""
        return await self.complete(user_seq)

    # ── 卡片 ──

    def branch_segment(self, seq: int | None = None) -> list[int]:
        """默认提炼范围（spec §3.2）：fork_point 起到 seq（默认指针）；
        fork_point 为 user 节点时含其自身（提问属于这段讨论），assistant 则不含。"""
        target = seq if seq is not None else self.conversation.pointer
        if target is None:
            raise TreeChatError("空会话没有可提炼范围")
        path = self.conversation.path_to(target)
        fp = self.conversation.fork_point(target)
        if fp is None:
            return [n.seq for n in path]
        idx = next(i for i, n in enumerate(path) if n.seq == fp)
        start = idx if path[idx].role == "user" else idx + 1
        segment = [n.seq for n in path[start:]]
        return segment or [target]

    async def make_card(self, instruction: str, *, seq: int | None = None,
                        from_seqs: list[int] | None = None) -> str:
        """提炼卡片：默认当前分支段；from_seqs 显式区间（/card all / <a>-<b>）。"""
        seqs = from_seqs if from_seqs is not None else self.branch_segment(seq)
        if not seqs:
            raise TreeChatError("提炼范围为空")
        lines = []
        for s in seqs:
            n = self.conversation.nodes[s]
            lines.append(f"[{n.role}] {n.text}")
        transcript = "\n\n".join(lines)
        client = self.card_llm if self.card_llm is not None else self.client
        out = await llm_bridge.extract_card(transcript, instruction, llm_client=client)
        return self.conversation.add_card(out["title"], out["body"], seqs, instruction)

    def export_card(self, card_id: str, file_path: Path) -> Path:
        card = self.conversation.cards.get(card_id)
        out = Path(file_path)
        out.write_text(f"# {card.title}\n\n{card.body}\n", encoding="utf-8")
        return out


def _window_or_default(window: WindowStrategy | None) -> WindowStrategy:
    """create/open 的 window=None = 用默认 V1 窗口策略（而非关闭窗口）。"""
    return window if window is not None else TokenWindowStrategy()


def list_sessions(config: TreeChatConfig) -> list[tuple[Path, SessionMeta]]:
    """枚举 data_dir/sessions 下的会话（坏文件跳过——打开时才硬报错）。"""
    d = config.sessions_dir()
    if not d.exists():
        return []
    out: list[tuple[Path, SessionMeta]] = []
    for p in sorted(d.glob("*.jsonl")):
        try:
            out.append((p, read_session_meta(p)))
        except (TreeChatError, json.JSONDecodeError, OSError):
            continue
    return out
