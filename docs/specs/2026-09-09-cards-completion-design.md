# 卡片功能补全设计 — 编辑/删除、导出/导入、跨会话卡库、树图选点提炼

> 日期：2026-09-09
> 状态：设计确定（自主执行：范围 = `webui/ROADMAP.md`「卡片」区块全部 4 项，实现细节由本文件记录）
> 关联：`docs/specs/2026-09-07-webui-design.md`（WebUI 设计）、引擎 spec（§3.3 卡片事件）

## 0. 范围

ROADMAP「卡片」区块的 4 项全部补齐：

1. **编辑 / 删除卡片**（引擎无事件，本设计补齐）
2. **卡片导出 / 导入 UI**（引擎已有 `export_card`，Web 层与 UI 未接）
3. **跨会话卡库与引用**
4. **树图选节点点选 → 自定义提炼范围生成卡片**

## 1. 引擎层（事件 11 → 13 种）

沿用「追加日志 + `_apply` 重放共用一份语义 + 严格校验」纪律。

| 事件 | 字段 | 语义 |
|---|---|---|
| `card_edit` | `card_id`, `title`, `body` | 整体替换标题与正文（不部分更新——重放确定性最简单） |
| `card_delete` | `card_id` | 删除卡片并移除 pin 状态 |

- `_apply` 对未知 `card_id` 抛 `TreeChatError`（与 `node_rename` 同纪律）；追加时先落盘再 `_apply` 校验，不变量与现有事件一致
- `CardRegistry` 新增 `remove(card_id)`（含清 pin）与 `update(card_id, title, body)`；`Conversation` 新增 `edit_card` / `delete_card`
- 不做墓碑/软删除：事件日志天然保留历史，派生态只呈现现存卡片
- `session.py`：`card_markdown(card)` 抽出（`export_card` 复用，Web 导出同一格式 `# title\n\nbody\n`）；新增 `list_library_cards(config) -> list[LibraryCard]`（全库枚举，坏文件跳过，与 `list_sessions` 同纪律）

## 2. 跨会话卡库 = 复制导入语义（关键决策）

卡库条目来自各会话文件的重放（`Conversation.open`，不建 LLM 客户端）。**「引用」实现为复制导入**：导入 = 在当前会话追加一张普通 `card_create`（新 id、`from_path=[]`、instruction 记来源），不做跨文件引用。

理由：会话事件日志保持自包含（重放同一性不受外部文件生死影响）；上下文组装零改动；id 冲突不可能发生。跨文件实时引用（源卡片改了副本跟着变）记入 roadmap。

## 3. Web 服务层（`treechat/webapp/app.py`）

```
PATCH  /api/sessions/{sid}/cards/{cid}        {title, body}          → ConvState
DELETE /api/sessions/{sid}/cards/{cid}                               → ConvState
GET    /api/sessions/{sid}/cards/{cid}/export                      → markdown 附件下载（Content-Disposition: {cid}.md）
POST   /api/sessions/{sid}/cards/import       {title, body, instruction?} → ConvState（不经 LLM，直接 add_card）
GET    /api/cards                                                    → 卡库条目[]（sid/sessionName + 卡片全字段）
```

- `CardBody.mode` 增加 `"seqs"`：`seqs: list[int]` 显式节点列表（树图选点用；空列表 → 400）
- 导入默认 pinned（`add_card` 现状）；删除未知卡片 → 400（与 pin 行为一致）
- 卡库枚举是只读扫描，不进会话锁、不打开 registry

## 4. CLI

- `/card edit <id> [新标题]`：改标题；省略新标题 = 查看当前标题/正文（正文多行编辑留在 WebUI，REPL 行输入不做多行）
- `/card delete <id>`：删除
- `/help` 同步更新

## 5. 前端（`webui/src`）

- **CardsTab**：
  - 展开卡片 → 操作行：编辑（Dialog：标题 Input + 正文 Textarea）、导出（隐藏 `<a download>` 触发 GET 导出端点）、删除（AlertDialog 确认）
  - 头部「导入」按钮 → Dialog：标题 + 正文 Textarea，可选上传 `.md/.txt`（首个 `# ` 行作为标题预填）
  - 底部「跨会话卡库」折叠区：展开时懒加载 `GET /api/cards`，排除当前会话，逐条「导入」（instruction 记 `导入自「会话名」`）
  - 原「Roadmap·未完善」区块移除（4 项全部完成）
- **TreeTab**：节点详情加「选入卡片范围」切换；页签底部范围条（seq chips + 生成卡片 + 清除）；「生成卡片」切到 Cards 页签并打开生成 Dialog（`seqs` 模式预填所选节点，可改指令）
- **App**：`cardSeqs` / `cardGenOpen` 状态上提；api.ts 补 `editCard` / `deleteCard` / `importCard` / `listLibraryCards` / `cardExportUrl`

## 6. 测试

- **events**：`card_edit` / `card_delete` roundtrip、未知类型/缺字段严格校验（沿用现有用例风格）
- **cards（registry）**：`remove`（含清 pin）、`update`、未知 id 报错
- **conversation**：edit/delete 追加即生效；重放（重开文件）派生一致；对未知卡片操作抛错
- **session**：`card_markdown` 格式、`list_library_cards` 跨会话枚举 + 坏文件跳过
- **webapp**：PATCH/DELETE/export/import/卡库 + `seqs` 模式 + 未知卡片 400 + 路径安全不回退
- **cli**：`/card edit`、`/card delete`（沿用现有测试风格）
- **前端**：`tsc -b && vite build` 通过 + vitest 现有用例不回归

## 7. Roadmap 变更

卡片 4 项移出未完成；新增一条：跨会话卡片**实时引用**（源卡片更新同步到副本——需跨文件事件订阅设计）。
