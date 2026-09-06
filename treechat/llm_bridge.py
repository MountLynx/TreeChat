"""SpecModule 依赖面 —— treechat 唯一 import llm/module_harness 的地方。

职责：① 对话轮次（client.chat 多轮，V1 非流式）；② 卡片提炼（call_harness
结构化调用 + {title, body} 显式校验）。测试替换点：带 chat/complete 的假客户端。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from llm import LLMConfig, LLMError, Message, create_llm_client
from module_harness import call_harness
from module_harness.core.config import HarnessConfig
from module_harness.core.outputfmt import OutputFormat

from .core.errors import TreeChatError

CARD_PROMPT_CORE = """\
你是上下文压缩器。把下面这段对话提炼成一张"卡片"：脱离原对话也能独立读懂的浓缩产出。

## 对话转录
{transcript}

## 提炼指令
{instruction}

要求：
- body 自包含：不出现"上面/刚才/对方/这段对话"等指代；保留事实、决策、结论与关键理由
- 去对话语气，写成结构化 markdown（可用小标题/列表）
- title 为一句话概括
"""

CARD_HARNESS_CONFIG = HarnessConfig(
    prompt_core=CARD_PROMPT_CORE,
    prompt_modes={"default": "按核心模板执行。"},
    output_format=OutputFormat(
        type="json_object",
        instruction='输出 JSON 对象：{"title": "一句话标题", "body": "markdown 正文"}',
    ),
    notdo=["不要在 JSON 之外输出任何文字"],
)


def create_client(model: str | None = None,
                  project_root: Path | None = None) -> Any:
    """env 驱动创建客户端（复用 SpecModule 配置回退链：项目根 → ~/.specmodule）。"""
    overrides: dict[str, Any] = {"model": model} if model else {}
    config = LLMConfig.from_env(
        project_root=project_root or Path.cwd(),
        store_root=Path.home() / ".specmodule",
        **overrides,
    )
    return create_llm_client(config)


async def chat_turn(client: Any, system: str, history: list[dict[str, str]],
                    current: str) -> tuple[str, dict[str, int]]:
    """一轮对话：组装 messages（system 打头）→ client.chat → (回复, usage)。

    失败 LLMError 原样上抛（调用方保证此时 user_msg 已落盘，悬而未答节点保留）。
    """
    messages = [Message(role="system", content=system)]
    messages += [Message(role=m["role"], content=m["content"]) for m in history]
    messages.append(Message(role="user", content=current))
    resp = await client.chat(messages)
    return resp.content, dict(resp.usage or {})


async def extract_card(transcript: str, instruction: str, *,
                       llm_client: Any) -> dict[str, str]:
    """卡片提炼：call_harness 校验 json_object，再显式校验 {title, body} 键。"""
    result = await call_harness(
        CARD_HARNESS_CONFIG,
        {"transcript": transcript, "instruction": instruction},
        llm_client=llm_client,
        promptmode="default",
    )
    value = result.value
    if not isinstance(value, dict) or "title" not in value or "body" not in value:
        raise TreeChatError(f"卡片提炼输出缺 title/body: {value!r}")
    return {"title": str(value["title"]), "body": str(value["body"])}
