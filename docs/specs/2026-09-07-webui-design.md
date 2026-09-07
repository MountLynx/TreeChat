# TreeChat WebUI 设计 — VSCode 式布局的对话树 Web 界面

> 日期：2026-09-07
> 状态：设计确定（自主执行：用户已给定布局/页签/功能边界，细节决策由本文件记录）
> 关联：`SpecModule/docs/dev/superpowers/specs/2026-09-06-treechat-conversation-engine-design.md`（引擎设计，V1 已完成）
> 参考外观与技术栈：`开发/参考/nanobot/webui`（React 18 + Vite + TS + Tailwind 3.4 + shadcn 风格 neutral 主题）

## 0. 需求与边界

为 TreeChat 制作 WebUI，界面采用 VSCode 式布局：

- **最左活动栏**（图标条）：每个图标对应一个侧边栏页签
  1. **Chat**（MessageSquare）：历史对话列表 + 对话管理（创建、删除、分类、归档）
  2. **Tree**（GitGraph）：当前对话的对话树分支图——节点 + 线条，git 图式；叶子放对应节点旁
  3. **Cards**（Layers）：当前对话的卡片管理（功能未完善部分记入 roadmap）
  4. **Settings**（齿轮，活动栏底部）：设置入口，**仅占位**，无实际功能
- **主区**：当前对话的聊天视图（活跃路径消息 + 输入框）

不做（记入 roadmap）：流式输出（等待 `llm.chat()` 补 `on_token`，引擎 spec §10）、模型切换 UI、卡片编辑/删除/导入、多端同步、i18n。

## 1. 后端补充（引擎层，用户指出的缺口）

### 1.1 新增 4 种事件（7 → 11 种，沿用严格校验风格）

| 事件 | 字段 | 语义 |
|---|---|---|
| `session_rename` | `name` | 总对话命名（显示名；文件名/sid 不变，sid 即会话 ID） |
| `session_category` | `category` | 分类（空串 = 未分类） |
| `session_archive` | `archived: bool` | 归档/取消归档 |
| `node_rename` | `seq`, `label` | 对话节点命名（label 空串 = 清除） |

全部走追加日志 + `_apply` 重放（派生态：`Conversation.category/archived`、`MsgNode.label`）。旧代码读新文件硬报错、新代码读旧文件正常——单仓库同步演进，符合 spec「版本前向兼容到需要时再做」。

### 1.2 会话枚举升级：`SessionSummary`

`list_sessions` 返回 `SessionSummary(sid, path, name, created_at, system, category, archived, node_count, mtime)`：

- 全文件轻解析（只取 meta/rename/category/archive/计数），撕裂尾容忍、坏文件跳过（与现有枚举纪律一致）
- `sid` = 文件名 stem（稳定 ID）；`mtime` = 最近活动时间（事件不携带 user/assistant 时间戳，不为 UI 加字段）
- CLI `treechat list` 适配新返回值

### 1.3 指针语义（WebUI 关键）

- 指针不落盘（引擎现状保留）：服务端进程内持有打开的 `TreeChatSession`，指针跨请求存活
- `turn` 请求显式带分支目标：`{text, parent?: int, leaf?: bool}`——缺省 = 当前指针；`parent=N` = 从节点 N 长新枝（先 `set_pointer`）；`leaf=true` = 无上下文叶子
- 服务重启后指针 = 重放出的最后一个 assistant 节点（引擎现状，可接受）

## 2. Web 服务层（`treechat/webapp/`）

**框架：FastAPI + uvicorn**（可选依赖 `webui = ["fastapi", "uvicorn"]`）。理由：LLM 桥是 async（`client.chat`），uvicorn 原生事件循环零桥接；CLI 的零依赖哲学只约束库核与 CLI，Web 服务是新消费层。CLI 增加 `treechat webui [--host --port]` 子命令（懒 import）。

```
treechat/webapp/
  __init__.py
  registry.py    # SessionRegistry：sid → 打开的 TreeChatSession + 每会话 asyncio.Lock（串行化轮次）
  app.py         # create_app(config)：路由 + 静态挂载 webui/dist + sid 路径安全校验
```

### 2.1 API（REST；除枚举外全部返回完整会话状态——会话规模小，全量最简单且无同步 bug）

```
GET    /api/sessions                          → SessionSummary[]
POST   /api/sessions {name, system?}          → summary（409 已存在）
GET    /api/sessions/{sid}                    → ConvState
DELETE /api/sessions/{sid}                    → 204（删文件 + 关闭注册表条目）
POST   /api/sessions/{sid}/rename {name}      → ConvState
POST   /api/sessions/{sid}/category {category}→ ConvState
POST   /api/sessions/{sid}/archive {archived} → ConvState
POST   /api/sessions/{sid}/nodes/{seq}/rename {label} → ConvState
POST   /api/sessions/{sid}/turn {text, parent?, leaf?}   → ConvState（LLM 失败 502 {error, state}，悬而未答节点已落盘）
POST   /api/sessions/{sid}/retry              → ConvState（无悬而未答 → 409）
POST   /api/sessions/{sid}/cards {instruction, mode: branch|all|range, start?, end?} → ConvState
POST   /api/sessions/{sid}/cards/{cid}/pin {pinned} → ConvState
GET    /api/health                            → {ok, llmConfigured, model}
```

`ConvState`：`{sid, name, system, category, archived, pointer, trunkEnd, unansweredUser, nodes[], cards[]}`；节点含 `seq/parent/role/text/label/model`，卡片含 `id/title/body/fromPath/instruction/createdAt/pinned`。

**LLM 未配置的降级**：打开会话时 `create_client` 失败 → `client=None`，树/管理/卡片查看照常；turn 返回显式错误（user 节点已落盘，悬而未答，配置后 /retry 可补——spec「诚实状态」哲学）。

**路径安全**：sid 拒绝 `/ \ ..` 且 resolve 后必须在 `sessions_dir` 内。

## 3. 前端（`webui/`，React SPA）

### 3.1 技术栈（对齐 nanobot/webui）

- React 18 + Vite 5 + TypeScript；Tailwind 3.4（shadcn neutral 调色板 + CSS 变量，亮/暗双色 `class` 策略；细滚动条；system-ui 字体栈）
- 组件：Radix 原语（dialog/alert-dialog/dropdown-menu/tooltip/popover）+ `cn()`（clsx + tailwind-merge）+ lucide-react 图标
- Markdown：react-markdown + remark-gfm（V1 非流式，不需要 streamdown）
- 状态：React hooks + fetch 封装（无 WS——非流式轮次请求/响应即可）；无路由库（内部 state 切页，同 nanobot）
- 构建：`webui/dist` 由 FastAPI 静态托管；dev 时 Vite 代理 `/api` → `127.0.0.1:8700`
- UI 语言：中文（与仓库一致）

### 3.2 布局

```
┌────┬──────────────┬────────────────────────────┐
│ 💬 │ 侧边栏 272px  │ 主区                        │
│ 🌳 │ 页签内容:     │ 顶栏: 会话名 · 分类 · 指针    │
│ 🗂 │  chat 列表    │ 消息流（活跃路径）            │
│    │  git 图       │ 助手=markdown 全宽           │
│    │  卡片管理     │ 用户=右对齐气泡               │
│ ⚙  │  设置占位     │ 输入区（分支/叶子指示）        │
└────┴──────────────┴────────────────────────────┘
```

活动栏 48px，图标亮起 = 当前页签；底部齿轮。

### 3.3 各页签

- **Chat 页签**：顶部「新对话」（Dialog：名称 + 可选 system）+ 过滤框；列表项 = 名称、分类 chip、消息数、相对时间；hover 出 DropdownMenu（重命名 / 分类 / 归档 / 删除——删除走 AlertDialog）；分组：各分类 → 未分类 → 归档（默认折叠）
- **Tree 页签**：git 图式 SVG + HTML 混合渲染——纯函数布局（`lib/treelayout.ts`：lane 分配 + 子节点继承/新 lane + 释放，先到先得；seq 行序），SVG 画连线（同 lane 直线、换 lane 贝塞尔）与节点圆点，HTML 行展示 `#seq · 节点名 · 文本摘要 · [card_x]`，标记 `◆` 主干末端 / 高亮环 = 指针；点节点 → 底部详情卡（全文 + 重命名节点 + 从此分支）
- **Cards 页签**：卡片列表（id、标题、📌pinned、来源 seq）；点击展开 body（markdown）；生成卡片 Dialog（指令 + 范围：当前分支段/全部路径/区间）；pin/unpin 切换；底部「Roadmap」折叠区列未完善功能
- **Settings**：占位页（「设置 · 敬请期待」+ 版本 + data_dir）
- **主区聊天**：活跃路径 = `path_to(pointer)`；分支中输入框上方 chip「从 #N 分支 ·」可取消；叶子模式切换；LLM 失败 → 错误条 + 重试按钮（打悬而未答节点）

## 4. 测试

- **引擎层**：新事件 roundtrip/重放/严格校验（未知字段/缺字段/未知类型）、`SessionSummary`（rename/archive/category 派生、坏文件跳过、撕裂尾）
- **webapp**：FastAPI TestClient + conftest 假客户端注入（registry 测试构造器）；覆盖建/删/改名/分类/归档/turn/branch/leaf/retry/node-rename/卡片 pin；sid 路径穿越拒绝
- **前端**：vitest 覆盖 `treelayout.ts` 纯函数（lane 分配/释放/多根叶子）；API client 类型冒烟
- **端到端**：mock LLM 起服务，浏览器 GUI 冒烟（对话→分支→树图→卡片→管理操作）

## 5. Roadmap（卡片管理页签内亦展示）

- 卡片：编辑/删除卡片体、卡片导出/导入 UI、跨会话卡库
- 对话：模型切换 UI、流式输出、会话内搜索、拖拽排序、置顶
- 树：节点拖拽改 parent（引擎不支持重挂，需先设计）、子树折叠、迷你地图
- 设置：主题切换、data_dir/预算/默认模型配置、token 用量展示
