import type { ConvState, Health, SessionSummary } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function req<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      if (body?.error) msg = body.error;
    } catch {
      /* 非 JSON 错误体 */
    }
    throw new ApiError(msg, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

// ── 枚举 / 健康 ──

export const listSessions = () => req<SessionSummary[]>("/api/sessions");
export const health = () => req<Health>("/api/health");

// ── 会话管理 ──

export const createSession = (name: string, system: string) =>
  req<SessionSummary>("/api/sessions", json("POST", { name, system }));
export const deleteSession = (sid: string) =>
  req<void>(`/api/sessions/${encodeURIComponent(sid)}`, { method: "DELETE" });
export const getState = (sid: string) =>
  req<ConvState>(`/api/sessions/${encodeURIComponent(sid)}`);
export const renameSession = (sid: string, name: string) =>
  req<ConvState>(`/api/sessions/${encodeURIComponent(sid)}/rename`, json("POST", { name }));
export const setCategory = (sid: string, category: string) =>
  req<ConvState>(`/api/sessions/${encodeURIComponent(sid)}/category`, json("POST", { category }));
export const setArchived = (sid: string, archived: boolean) =>
  req<ConvState>(`/api/sessions/${encodeURIComponent(sid)}/archive`, json("POST", { archived }));
export const renameNode = (sid: string, seq: number, label: string) =>
  req<ConvState>(`/api/sessions/${encodeURIComponent(sid)}/nodes/${seq}/rename`, json("POST", { label }));

// ── 轮次 ──

export interface TurnResult {
  error?: string;
  state: ConvState;
}
/** turn 特殊处理：LLM 失败返回 502 {error, state}——user 节点已落盘，前端要更新状态 */
export async function turn(
  sid: string,
  body: { text: string; parent?: number; leaf?: boolean },
): Promise<TurnResult> {
  const res = await fetch(`/api/sessions/${encodeURIComponent(sid)}/turn`, {
    headers: { "Content-Type": "application/json" },
    method: "POST",
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (res.status === 502) return { error: data.error, state: data.state };
  if (!res.ok) throw new ApiError(data?.error ?? res.statusText, res.status);
  return { state: data as ConvState };
}
export const retry = (sid: string) =>
  req<ConvState>(`/api/sessions/${encodeURIComponent(sid)}/retry`, json("POST", {}));

// ── 卡片 ──

export interface CardReq {
  instruction: string;
  mode: "branch" | "all" | "range";
  start?: number;
  end?: number;
}
export const createCard = (sid: string, body: CardReq) =>
  req<ConvState>(`/api/sessions/${encodeURIComponent(sid)}/cards`, json("POST", body));
export const pinCard = (sid: string, cid: string, pinned: boolean) =>
  req<ConvState>(`/api/sessions/${encodeURIComponent(sid)}/cards/${cid}/pin`, json("POST", { pinned }));
