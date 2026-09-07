import { GitFork, Layers, MessageSquare, Settings } from "lucide-react";
import type { Tab } from "../types";
import { cn } from "../lib/utils";

const TOP_TABS: { key: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "chat", label: "对话", icon: MessageSquare },
  { key: "tree", label: "对话树", icon: GitFork },
  { key: "cards", label: "卡片", icon: Layers },
];

interface Props {
  tab: Tab;
  onTab: (t: Tab) => void;
}

/** 最左活动栏（VSCode 式）：图标 = 侧边栏页签切换；底部设置入口（占位） */
export function ActivityBar({ tab, onTab }: Props) {
  const item = (t: Tab, label: string, Icon: React.ComponentType<{ className?: string }>) => (
    <button
      key={t}
      title={label}
      onClick={() => onTab(t)}
      className={cn(
        "relative flex h-12 w-full items-center justify-center transition-colors",
        tab === t
          ? "text-foreground"
          : "text-activitybar-foreground hover:text-foreground",
      )}
    >
      {tab === t && (
        <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-full bg-foreground" />
      )}
      <Icon className="h-5 w-5" />
    </button>
  );

  return (
    <nav className="flex h-full w-12 shrink-0 flex-col items-center bg-activitybar text-activitybar-foreground">
      <div className="flex w-full flex-col">{TOP_TABS.map((t) => item(t.key, t.label, t.icon))}</div>
      <div className="flex-1" />
      {item("settings", "设置（占位）", Settings)}
    </nav>
  );
}
