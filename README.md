# TreeChat

对话树一等公民 + 卡片式上下文产出的可嵌入对话引擎（V1 开发中）。

- 会话 = 追加式事件日志（JSONL），分支/叶子是 `parent` 指针的原生语义
- 卡片 = 结构化 LLM 提炼的上下文产出，pinned 后注入后续轮次
- LLM 层复用 [SpecModule](https://pypi.org/project/specmodule/)（配置回退链 / 输出校验）

## 安装（开发态）

    pip install -e ".[dev]"
    python -m pytest tests/ -q

配置复用 SpecModule 的回退链：项目根 `config.json`/`.env` → `~/.specmodule`。
