# TreeChat WebUI

VSCode 式布局的 Web 界面：最左活动栏（图标 = 页签）+ 侧边栏 + 主聊天区。
技术栈与外观参考 [nanobot/webui](../../../参考/nanobot/webui)：React 18 + Vite + TypeScript + Tailwind CSS（shadcn 风格 neutral 主题）+ Radix + lucide-react。

## 页签

| 图标 | 页签 | 内容 |
|---|---|---|
| 💬 | 对话 | 历史对话列表 + 管理（创建 / 重命名 / 分类 / 归档 / 删除） |
| 🌿 | 对话树 | 当前对话的分支图（git 图式：节点 + 连线 + lane；叶子在对应节点旁；点节点 → 命名 / 从此分支） |
| 🗂 | 卡片 | 当前对话的卡片管理（生成 / pin / 查看 / **编辑 / 删除 / 导出 / 导入 / 跨会话卡库**；树图选点自定义提炼范围；剩余见 [ROADMAP.md](./ROADMAP.md)） |
| ⚙ | 设置（底部） | 占位，无实际功能 |

## 运行

后端（FastAPI，服务 REST + 静态托管本目录构建产物）：

    pip install -e ".[webui]"
    treechat webui                # http://127.0.0.1:8700 ，需 SpecModule 配置链有 LLM

无 LLM 配置也能跑（树/管理功能正常，对话轮次显式报错）；
纯前端开发/演示用 mock LLM 服务器：

    python webui/devserver.py     # mock 回复 + 临时数据目录

前端开发：

    cd webui
    npm install
    npm run dev                   # Vite 5173，/api 代理到 8700
    npm run build                 # 产物 dist/，由后端静态托管
    npm test                      # vitest（树布局纯函数）

## 架构

```
webui/                 React SPA（本目录）
treechat/webapp/       FastAPI 服务层
  registry.py          sid → 打开会话（指针进程内存活）+ 每会话锁
  app.py               REST API（全量状态返回）+ 静态挂载
```

- 指针不落盘（引擎语义）：服务进程内持有打开的会话；`turn` 请求显式带
  `parent`（分支目标）或 `leaf`，缺省 = 当前指针。
- 除枚举外所有变更接口返回**完整会话状态**——会话规模小，全量最简单且无同步 bug。
- LLM 失败返回 502 `{error, state}`：user 节点已落盘（悬而未答），前端展示错误条 + 重试。
- 引擎侧新增 4 种事件支撑对话管理：`session_rename` / `session_category` /
  `session_archive` / `node_rename`（见 `docs/specs/2026-09-07-webui-design.md`）。
- 卡片功能补全（2026-09-09）：引擎再增 `card_edit` / `card_delete` 事件；
  Web 层补卡片编辑/删除/导出/导入与跨会话卡库（复制导入语义）端点
  （见 `docs/specs/2026-09-09-cards-completion-design.md`）。
