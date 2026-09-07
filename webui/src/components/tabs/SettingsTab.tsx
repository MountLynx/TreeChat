import { Settings } from "lucide-react";
import type { Health } from "../../types";

interface Props {
  health: Health | null;
}

/** 设置（侧边栏）—— 仅占位，不做实际功能（见 webui/ROADMAP.md） */
export function SettingsTab(_: Props) {
  return (
    <div className="flex h-full flex-col">
      <div className="px-3 pb-2 pt-3 text-[13px] font-semibold">设置</div>
      <div className="px-3 text-[12.5px] leading-6 text-muted-foreground">
        <p className="rounded-panel border border-dashed px-2.5 py-3">设置功能敬请期待。</p>
        <p className="pt-2">规划中的能力（暂未实现）：</p>
        <ul className="list-disc pl-4 pt-1">
          <li>主题切换（当前跟随系统）</li>
          <li>data_dir / 窗口预算 / 默认模型</li>
          <li>token 用量统计</li>
        </ul>
      </div>
    </div>
  );
}

/** 主区设置占位页 */
export function SettingsPlaceholder({ health }: Props) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-muted-foreground">
      <Settings className="h-10 w-10 opacity-30" />
      <div className="text-lg font-medium text-foreground">设置 · 敬请期待</div>
      <div className="max-w-md text-center text-[13px] leading-6">
        设置入口已占位，暂无实际功能。主题、存储位置、模型配置等将在后续版本提供。
      </div>
      {health && (
        <div className="mt-2 space-y-0.5 text-center font-mono text-[11.5px] opacity-70">
          <div>data_dir: {health.dataDir}</div>
          <div>LLM: {health.llmConfigured ? "已配置" : "未配置（对话不可用，管理功能正常）"}</div>
        </div>
      )}
    </div>
  );
}
