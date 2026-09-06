"""斜杠命令路由。返回 True 表示退出 REPL。

state（REPL 会话态，repl 层持有）：{"leaf_next": bool}；/retry 目标由
`conv.unanswered_user()` 视图给出（跨 REPL 打开仍然有效）。
"""
from __future__ import annotations

from typing import Any, Callable

from llm import LLMError

from ..config import TreeChatConfig
from ..core.errors import TreeChatError
from ..session import TreeChatSession

Say = Callable[[str], None]

_HELP = """\
命令：
  /tree                 树视图（* 指针 ◆ 主干末端 [卡片]）
  /branch <seq>         指针挪到历史节点 → 下一条输入长新枝
  /trunk                指针跳回主干末端
  /leaf                 下一条输入 = 无上下文叶子提问
  /retry                对最后一个悬而未答节点重新调 LLM
  /card [all|<a>-<b>|指令]   提炼卡片（默认当前分支段）
  /cards；/card show <id>；/pin /unpin <id>；/card export <id> <file>
  /where                当前位置
  /system [新指令]       查看/修改会话级 system
  /model [名]           查看/切换模型
  /help；/quit
"""

_UNIMPLEMENTED = {"tree", "branch", "trunk", "leaf", "card", "cards",
                  "pin", "unpin", "system", "model"}


async def handle_command(session: TreeChatSession, config: TreeChatConfig,
                         line: str, *, state: dict[str, Any], say: Say) -> bool:
    """处理斜杠命令；返回 True = 退出 REPL。业务错误显式显示，不中断会话。"""
    parts = line[1:].strip().split(maxsplit=1)
    cmd = parts[0] if parts else "help"
    rest = parts[1].strip() if len(parts) > 1 else ""
    conv = session.conversation
    try:
        if cmd in ("quit", "q"):
            return True
        if cmd == "help":
            say(_HELP)
        elif cmd == "where":
            depth = len(conv.path_to(conv.pointer)) if conv.pointer else 0
            say(f"指针: #{conv.pointer} · 路径深度 {depth} · 会话 {conv.name}")
        elif cmd in _UNIMPLEMENTED:
            say(f"/{cmd} 尚未实现（Task 10/11）")
        else:
            say(f"未知命令: /{cmd}（/help 查看命令）")
    except LLMError as exc:
        dangling = conv.unanswered_user()
        say(f"LLM 调用失败：{exc}"
            + (f"\n节点 #{dangling} 悬而未答；/retry 重试" if dangling else ""))
    except TreeChatError as exc:
        say(f"错误：{exc}")
    return False
