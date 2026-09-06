"""CLI：非交互命令 + REPL 对话/where/help/quit/retry。"""
import asyncio

from llm import LLMError
from treechat.cli.repl import main, run_repl
from treechat.config import TreeChatConfig


def _make_input(lines):
    it = iter(lines)

    async def input_fn(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    return input_fn


def _make_say():
    out = []

    def say(text=""):
        out.append(str(text))

    return say, out


def _open_session(tmp_path, fake_chat, fake_card_client):
    from treechat.core.conversation import Conversation
    from treechat.core.context import TokenWindowStrategy
    from treechat.session import TreeChatSession
    conv = Conversation.create(tmp_path / "t.jsonl", name="t", system="sys")
    s = TreeChatSession(conversation=conv, client=fake_chat,
                        window=TokenWindowStrategy(budget_tokens=10_000),
                        card_llm=fake_card_client)
    return s


def test_main_new_creates_session(tmp_path, capsys, fake_chat, monkeypatch):
    # create/open 走 create_client → env 配置链，单测不依赖环境 → 假客户端替身
    from treechat import llm_bridge
    monkeypatch.setattr(llm_bridge, "create_client", lambda model=None: fake_chat)
    config = TreeChatConfig(data_dir=tmp_path)
    # new 会进 REPL；喂 /quit 立即退出
    code = main(["new", "甲", "--system", "s"], config=config,
                input_fn=_make_input(["/quit"]))
    assert code == 0
    assert (config.sessions_dir() / "甲.jsonl").exists()


def test_main_list(tmp_path, capsys):
    config = TreeChatConfig(data_dir=tmp_path)
    config.sessions_dir().mkdir(parents=True)
    from treechat.core.conversation import Conversation
    Conversation.create(config.sessions_dir() / "乙.jsonl", name="乙")
    code = main(["list"], config=config)
    assert code == 0
    assert "乙" in capsys.readouterr().out


def test_repl_bare_input_and_where(tmp_path, fake_chat, fake_card_client):
    s = _open_session(tmp_path, fake_chat, fake_card_client)
    say, out = _make_say()
    code = run_repl(s, TreeChatConfig(data_dir=tmp_path),
                    input_fn=_make_input(["你好", "/where", "/quit"]), say=say)
    assert code == 0
    assert any("mock reply" in line for line in out)
    assert any("/where" in line or "指针" in line for line in out)


def test_repl_llm_failure_surface_and_retry(tmp_path, fake_chat, fake_card_client):
    s = _open_session(tmp_path, fake_chat, fake_card_client)
    say, out = _make_say()
    fake_chat.fail = True
    code = run_repl(s, TreeChatConfig(data_dir=tmp_path),
                    input_fn=_make_input(["问题", "/retry", "/quit"]), say=say)
    fake_chat.fail = False
    assert code == 0
    assert any("LLM 调用失败" in line for line in out)
    assert any("悬而未答" in line for line in out)


def test_repl_help_and_unknown_command(tmp_path, fake_chat, fake_card_client):
    s = _open_session(tmp_path, fake_chat, fake_card_client)
    say, out = _make_say()
    run_repl(s, TreeChatConfig(data_dir=tmp_path),
             input_fn=_make_input(["/help", "/nope", "/quit"]), say=say)
    assert any("命令" in line for line in out)
    assert any("未知命令" in line for line in out)
