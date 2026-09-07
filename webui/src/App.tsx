import { useCallback, useEffect, useState } from "react";
import * as api from "./api";
import type { ConvState, Health, SessionSummary, Tab } from "./types";
import { ActivityBar } from "./components/ActivityBar";
import { ChatListTab } from "./components/tabs/ChatListTab";
import { TreeTab } from "./components/tabs/TreeTab";
import { CardsTab } from "./components/tabs/CardsTab";
import { SettingsPlaceholder, SettingsTab } from "./components/tabs/SettingsTab";
import { ChatView } from "./components/chat/ChatView";
import { Composer } from "./components/chat/Composer";

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSid, setActiveSid] = useState<string | null>(null);
  const [conv, setConv] = useState<ConvState | null>(null);
  const [branchParent, setBranchParent] = useState<number | null>(null);
  const [leafMode, setLeafMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSeq, setSelectedSeq] = useState<number | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  const refreshSessions = useCallback(() => {
    api.listSessions().then(setSessions).catch(() => setSessions([]));
  }, []);

  useEffect(() => {
    refreshSessions();
    api.health().then(setHealth).catch(() => setHealth(null));
  }, [refreshSessions]);

  // ── 会话管理 ──

  const openSession = useCallback(async (sid: string) => {
    try {
      const st = await api.getState(sid);
      setActiveSid(sid);
      setConv(st);
      setBranchParent(null);
      setLeafMode(false);
      setSelectedSeq(null);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const createSession = async (name: string, system: string) => {
    await api.createSession(name, system);
    refreshSessions();
    await openSession(name);
  };

  const deleteSession = async (sid: string) => {
    await api.deleteSession(sid);
    if (activeSid === sid) {
      setActiveSid(null);
      setConv(null);
    }
    refreshSessions();
  };

  const mutateSession = async (
    fn: (sid: string) => Promise<ConvState>,
    sid: string,
  ) => {
    const st = await fn(sid);
    if (activeSid === sid) setConv(st);
    refreshSessions();
  };

  // ── 轮次 ──

  const send = async (text: string) => {
    if (!activeSid || busy) return;
    const parent = branchParent ?? undefined;
    const leaf = leafMode || undefined;
    setBusy(true);
    setError(null);
    setBranchParent(null);
    setLeafMode(false);
    try {
      const r = await api.turn(activeSid, { text, parent, leaf });
      setConv(r.state);
      if (r.error) setError(r.error);
      refreshSessions();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    if (!activeSid || busy) return;
    setBusy(true);
    try {
      setConv(await api.retry(activeSid));
      setError(null);
      refreshSessions();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const branchFrom = (seq: number) => {
    setBranchParent(seq);
    setLeafMode(false);
    setTab("chat");
  };

  // ── 卡片 ──

  const createCard = async (req: Parameters<typeof api.createCard>[1]) => {
    if (!activeSid) return;
    setBusy(true);
    try {
      setConv(await api.createCard(activeSid, req));
      refreshSessions();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const pinCard = async (cid: string, pinned: boolean) => {
    if (!activeSid) return;
    setConv(await api.pinCard(activeSid, cid, pinned));
  };

  const showSettings = tab === "settings";

  return (
    <div className="flex h-full w-full overflow-hidden">
      {/* 活动栏（最左图标条） */}
      <ActivityBar tab={tab} onTab={setTab} />

      {/* 侧边栏（页签内容） */}
      <aside className="flex h-full w-[280px] shrink-0 flex-col border-r bg-sidebar">
        {tab === "chat" && (
          <ChatListTab
            sessions={sessions}
            activeSid={activeSid}
            onOpen={openSession}
            onCreate={createSession}
            onRename={(sid, name) => mutateSession((s) => api.renameSession(s, name), sid)}
            onCategory={(sid, cat) => mutateSession((s) => api.setCategory(s, cat), sid)}
            onArchive={(sid, a) => mutateSession((s) => api.setArchived(s, a), sid)}
            onDelete={deleteSession}
          />
        )}
        {tab === "tree" && (
          <TreeTab
            conv={conv ?? { sid: "", name: "", system: "", category: "", archived: false, pointer: null, trunkEnd: null, unansweredUser: null, nodes: [], cards: [] }}
            selectedSeq={selectedSeq}
            onSelect={setSelectedSeq}
            onRenameNode={async (seq, label) => {
              if (!activeSid) return;
              setConv(await api.renameNode(activeSid, seq, label));
            }}
            onBranchFrom={branchFrom}
          />
        )}
        {tab === "cards" && (
          <CardsTab conv={conv} onCreateCard={createCard} onPin={pinCard} />
        )}
        {showSettings && <SettingsTab health={health} />}
      </aside>

      {/* 主区 */}
      <main className="flex h-full min-w-0 flex-1 flex-col bg-background">
        {showSettings ? (
          <SettingsPlaceholder health={health} />
        ) : conv ? (
          <>
            <header className="flex h-11 shrink-0 items-center gap-2 border-b px-4">
              <span className="truncate text-[13.5px] font-semibold">{conv.name}</span>
              {conv.category && (
                <span className="rounded-full bg-foreground/[0.07] px-2 py-0.5 text-[11px] text-muted-foreground">
                  {conv.category}
                </span>
              )}
              {conv.archived && (
                <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground">
                  已归档
                </span>
              )}
              {conv.system && (
                <span title={`system: ${conv.system}`}
                      className="max-w-[30%] truncate text-[11px] text-muted-foreground/70">
                  system: {conv.system}
                </span>
              )}
              <span className="ml-auto font-mono text-[11px] text-muted-foreground/70">
                指针 #{conv.pointer ?? "—"}{health && !health.llmConfigured && " · LLM 未配置"}
              </span>
            </header>
            <ChatView conv={conv} busy={busy} error={error} onRetry={retry} />
            <Composer
              branchParent={branchParent}
              leafMode={leafMode}
              busy={busy}
              disabled={false}
              onClearBranch={() => setBranchParent(null)}
              onToggleLeaf={() => setLeafMode((v) => !v)}
              onSend={send}
            />
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
            <div className="text-4xl">🌳</div>
            <div className="text-[14px]">在左侧选择或创建一个对话</div>
            <div className="text-[12px] opacity-70">对话树 + 卡片式上下文产出</div>
          </div>
        )}
      </main>
    </div>
  );
}
