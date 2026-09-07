/** treelayout 纯函数：lane 分配 / 释放 / 多根叶子 / 新枝换道 */
import { describe, expect, it } from "vitest";
import { layoutTree, ROW_H, X0 } from "./treelayout";
import type { Node } from "../types";

const n = (seq: number, parent: number | null): Node => ({
  seq, parent, role: "user", text: `t${seq}`, label: "", model: "",
});

describe("layoutTree", () => {
  it("顺延对话都在 lane 0", () => {
    const t = layoutTree([n(1, null), n(2, 1), n(3, 2)]);
    expect(t.nodes.map((p) => p.lane)).toEqual([0, 0, 0]);
    expect(t.laneCount).toBe(1);
    expect(t.height).toBe(3 * ROW_H);
    expect(t.nodes[0]).toMatchObject({ x: X0, y: ROW_H / 2 });
  });

  it("新枝换新 lane，同 lane 无碰撞", () => {
    // 1 → 2 → 3 主干；4 从 #2 分支（2 有两个子）
    const t = layoutTree([n(1, null), n(2, 1), n(3, 2), n(4, 2)]);
    const lane = new Map(t.nodes.map((p) => [p.seq, p.lane]));
    expect(lane.get(3)).toBe(0); // 首子延续
    expect(lane.get(4)).not.toBe(lane.get(2)); // 新枝换道
    expect(t.edges.some((e) => e.curve)).toBe(true);
  });

  it("lane 末端释放后可复用", () => {
    // 主干 1→2→3；分支 4（叶）；后续 5 从 #1 再分支 → 复用已释放的 lane
    const t = layoutTree([n(1, null), n(2, 1), n(3, 2), n(4, 2), n(5, 1)]);
    const lane = new Map(t.nodes.map((p) => [p.seq, p.lane]));
    expect(lane.get(4)).toBe(1); // 第一条新枝
    expect(lane.get(5)).toBe(1); // lane1 末端在 #4，#5 复用
  });

  it("叶子链起点（parent=null 非首个）按根处理", () => {
    const t = layoutTree([n(1, null), n(2, 1), n(3, null)]);
    const lane = new Map(t.nodes.map((p) => [p.seq, p.lane]));
    expect(lane.get(3)).toBe(0); // 主干链在 #2 结束 → #3 复用 lane0
    // 无入边：#3 无 parent 边
    expect(t.edges.filter((e) => e.to.x === t.nodes.find((p) => p.seq === 3)!.x && e.to.y === t.nodes.find((p) => p.seq === 3)!.y).length).toBe(0);
  });

  it("空会话与孤儿容错", () => {
    expect(layoutTree([]).nodes).toHaveLength(0);
    const t = layoutTree([n(1, null), n(9, 99)]); // 孤儿按根处理
    expect(t.nodes).toHaveLength(2);
  });

  it("edges 连接 parent→child 且行序单调", () => {
    const t = layoutTree([n(1, null), n(2, 1), n(3, 2)]);
    expect(t.edges).toHaveLength(2);
    for (const e of t.edges) expect(e.to.y).toBeGreaterThan(e.from.y);
  });
});
