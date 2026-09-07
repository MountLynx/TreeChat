import { MapPin, Pin, PinOff, Plus } from "lucide-react";
import { useState } from "react";
import type { ConvState } from "../../types";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";
import { Input, Textarea } from "../ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "../ui/dialog";
import { Markdown } from "../chat/Markdown";

interface Props {
  conv: ConvState | null;
  onCreateCard: (req: { instruction: string; mode: "branch" | "all" | "range"; start?: number; end?: number }) => Promise<void>;
  onPin: (cid: string, pinned: boolean) => Promise<void>;
}

/** Cards 页签：当前对话的卡片管理（未完善功能见底部 Roadmap 与 webui/ROADMAP.md） */
export function CardsTab(p: Props) {
  const [genOpen, setGenOpen] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const conv = p.conv;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-3 pb-2 pt-3">
        <span className="text-[13px] font-semibold">卡片</span>
        {conv && <span className="text-[11.5px] text-muted-foreground">{conv.name} · {conv.cards.length} 张</span>}
        <Button size="sm" className="ml-auto h-7" disabled={!conv}
                onClick={() => setGenOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> 生成卡片
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {!conv ? (
          <div className="px-3 py-10 text-center text-[12.5px] text-muted-foreground">先打开一个对话</div>
        ) : conv.cards.length === 0 ? (
          <div className="px-3 py-10 text-center text-[12.5px] text-muted-foreground">
            还没有卡片。把当前分支段提炼为「脱离原对话也能读懂」的结构化产出。
          </div>
        ) : (
          conv.cards.map((c) => (
            <div key={c.id}
                 onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                 className={cn("mb-1.5 cursor-pointer rounded-panel border px-2.5 py-2 transition-colors hover:bg-foreground/[0.03]",
                              expanded === c.id && "bg-foreground/[0.04]")}>
              <div className="flex items-center gap-1.5">
                <button title={c.pinned ? "取消 pin" : "pin（注入后续轮次）"}
                        onClick={(e) => { e.stopPropagation(); p.onPin(c.id, !c.pinned); }}
                        className={cn("shrink-0", c.pinned ? "text-primary" : "text-muted-foreground/50 hover:text-foreground")}>
                  {c.pinned ? <Pin className="h-3.5 w-3.5" /> : <PinOff className="h-3.5 w-3.5" />}
                </button>
                <span className="font-mono text-[10.5px] text-muted-foreground">{c.id}</span>
                <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{c.title}</span>
              </div>
              <div className="flex items-center gap-1 pt-0.5 text-[10.5px] text-muted-foreground/80">
                <MapPin className="h-3 w-3" />
                来源 {c.fromPath.map((s) => `#${s}`).join(" → ") || "—"}
                {c.instruction && <span className="truncate">· 指令「{c.instruction}」</span>}
              </div>
              {expanded === c.id && (
                <div className="mt-1.5 border-t border-border pt-1.5">
                  <Markdown text={c.body} />
                </div>
              )}
            </div>
          ))
        )}

        {/* Roadmap（未完善功能记录，同时见 webui/ROADMAP.md） */}
        <details className="mt-3 rounded-panel border border-dashed px-2.5 py-2 text-[12px] text-muted-foreground">
          <summary className="cursor-pointer select-none text-[12.5px] font-medium">Roadmap · 卡片功能未完善</summary>
          <ul className="list-disc pl-4 pt-1.5 leading-6">
            <li>编辑 / 删除卡片</li>
            <li>卡片导出 / 导入（引擎已有导出，UI 未接）</li>
            <li>跨会话卡库与引用</li>
            <li>自定义提炼范围点选（树图选节点 → 生成卡片）</li>
          </ul>
        </details>
      </div>

      <Dialog open={genOpen} onOpenChange={setGenOpen}>
        <DialogContent>
          <GenerateForm conv={conv} onDone={() => setGenOpen(false)} onCreate={p.onCreateCard} />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function GenerateForm(p: {
  conv: ConvState | null;
  onDone: () => void;
  onCreate: Props["onCreateCard"];
}) {
  const [instruction, setInstruction] = useState("");
  const [mode, setMode] = useState<"branch" | "all" | "range">("branch");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [busy, setBusy] = useState(false);
  const rangeValid = mode !== "range" || (Number(start) > 0 && Number(end) >= Number(start));
  return (
    <>
      <DialogTitle>生成卡片</DialogTitle>
      <DialogDescription>用 LLM 把对话段提炼为自包含卡片（默认 pinned）。</DialogDescription>
      <div className="grid gap-2.5">
        <Textarea autoFocus placeholder="提炼指令（留空 = 总结为卡片）" value={instruction}
                  onChange={(e) => setInstruction(e.target.value)} />
        <div className="flex gap-1.5 text-[12.5px]">
          {([["branch", "当前分支段"], ["all", "全部路径"], ["range", "区间"]] as const).map(([k, label]) => (
            <button key={k} onClick={() => setMode(k)}
                    className={cn("rounded-control border px-2 py-1 transition-colors",
                                 mode === k ? "border-primary bg-primary/10" : "hover:bg-accent")}>
              {label}
            </button>
          ))}
        </div>
        {mode === "range" && (
          <div className="flex items-center gap-2 text-[12.5px]">
            <Input className="h-7 w-20" placeholder="起始 seq" value={start} onChange={(e) => setStart(e.target.value)} />
            <span>→</span>
            <Input className="h-7 w-20" placeholder="结束 seq" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
        )}
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={p.onDone}>取消</Button>
        <Button disabled={busy || !p.conv || !rangeValid}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await p.onCreate({
                      instruction: instruction.trim() || "总结为卡片",
                      mode,
                      start: mode === "range" ? Number(start) : undefined,
                      end: mode === "range" ? Number(end) : undefined,
                    });
                    p.onDone();
                  } finally {
                    setBusy(false);
                  }
                }}>
          {busy ? "提炼中…" : "生成"}
        </Button>
      </DialogFooter>
    </>
  );
}
