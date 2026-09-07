# TreeChat

对话树一等公民 + 卡片式上下文产出的可嵌入对话引擎（V1 开发中）。

- 会话 = 追加式事件日志（JSONL），分支/叶子是 `parent` 指针的原生语义
- 卡片 = 结构化 LLM 提炼的上下文产出，pinned 后注入后续轮次
- LLM 层复用 [SpecModule](https://pypi.org/project/specmodule/)（配置回退链 / 输出校验）

## 安装（开发态）

    pip install -e ".[dev]"
    python -m pytest tests/ -q

配置复用 SpecModule 的回退链：项目根 `config.json`/`.env` → `~/.specmodule`。

## 使用

    treechat new 日常 [--system "简洁回答"]   # 新会话进 REPL
    treechat list
    treechat open 日常

REPL 内：裸输入对话；`/branch <seq>` 在任意历史节点开分支；`/leaf` 无上下文提问；
`/card [指令]` 把当前分支段提炼为卡片（默认 pinned，注入后续轮次）；`/tree` 看树
（`*` 指针、`◆` 主干末端、`[card_x]` 卡片来源）；`/trunk` 回主干末端；`/retry`
重试失败轮次。谁最长谁是主干——树上没有存储的主干，只有最长路径这条视图规则。

## WebUI

    pip install -e ".[webui]"
    treechat webui                # http://127.0.0.1:8700（首次需 cd webui && npm run build）

VSCode 式布局：活动栏（对话 / 对话树 / 卡片 / 设置占位）+ 侧边栏 + 主聊天区。
对话管理（创建/重命名/分类/归档/删除）、git 图式对话树（分支/叶子/节点命名/
从此分支）、卡片生成与 pin。详见 [webui/README.md](webui/README.md)。

## 编程 API

    from treechat import TreeChatSession
    s = TreeChatSession.create(path, "会话名", system="...")
    a = await s.turn("问题")          # 失败留下悬而未答节点，s.turn_retry(节点号) 重试
    cid = await s.make_card("总结为卡片")   # 默认当前分支段，产出即 pinned
    s.export_card(cid, "卡片.md")           # 跨会话复用走导出文件

## 配置

复用 SpecModule 配置回退链：项目根 `config.json`（providers/models）+ `.env`（API key）
→ `~/.specmodule` 用户级。`/model 名` 会话内切换（重建客户端）。
