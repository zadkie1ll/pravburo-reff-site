import { describe, expect, it } from "vitest";

import { initialCollapsed, layoutTree, LEVEL_HEIGHT } from "./layout";
import type { TreeNode } from "./types";

const node = (
  id: number,
  children: TreeNode[] = [],
  overrides: Partial<TreeNode> = {},
): TreeNode => ({
  id,
  name: `Партнёр ${id}`,
  email: null,
  phone: null,
  is_active: true,
  children,
  ...overrides,
});

//        1
//      /   \
//     2     3
//    / \
//   4   5
const TREE = node(1, [node(2, [node(4), node(5)]), node(3)]);

const ids = (layout: ReturnType<typeof layoutTree>) => layout.nodes.map((n) => n.id).sort();

describe("initialCollapsed", () => {
  it("folds every branch below the first level, but not the root or leaves", () => {
    expect([...initialCollapsed(TREE)]).toEqual([2]);
  });

  it("folds nothing for a lone partner", () => {
    expect(initialCollapsed(node(1)).size).toBe(0);
  });
});

describe("layoutTree", () => {
  it("shows only the first level while the rest is folded", () => {
    const layout = layoutTree(TREE, initialCollapsed(TREE), 900);

    expect(ids(layout)).toEqual([1, 2, 3]);
    expect(layout.links).toHaveLength(2);
  });

  it("shows a folded branch once it is expanded", () => {
    const layout = layoutTree(TREE, new Set(), 900);

    expect(ids(layout)).toEqual([1, 2, 3, 4, 5]);
    expect(layout.links).toHaveLength(4);
  });

  it("puts each generation on its own row, root at the top", () => {
    const layout = layoutTree(TREE, new Set(), 900);
    const y = Object.fromEntries(layout.nodes.map((n) => [n.id, n.y]));

    expect(y[2]! - y[1]!).toBe(LEVEL_HEIGHT);
    expect(y[2]).toBe(y[3]);
    expect(y[4]! - y[2]!).toBe(LEVEL_HEIGHT);
  });

  it("centres the tree in the given width", () => {
    const layout = layoutTree(TREE, new Set(), 1000);
    const xs = layout.nodes.map((n) => n.x);

    expect((Math.min(...xs) + Math.max(...xs)) / 2).toBeCloseTo(500);
  });

  it("draws a lone partner without crashing (the old script did)", () => {
    const layout = layoutTree(node(1), new Set(), 900);

    expect(layout.nodes).toHaveLength(1);
    expect(layout.nodes[0]).toMatchObject({ x: 450, hasChildren: false, expanded: false });
    expect(layout.links).toEqual([]);
  });

  it("tells whether a node can be folded and whether it is open", () => {
    const layout = layoutTree(TREE, initialCollapsed(TREE), 900);
    const byId = Object.fromEntries(layout.nodes.map((n) => [n.id, n]));

    expect(byId[1]).toMatchObject({ hasChildren: true, expanded: true });
    expect(byId[2]).toMatchObject({ hasChildren: true, expanded: false });
    expect(byId[3]).toMatchObject({ hasChildren: false, expanded: false });
  });

  it("links each child to its parent with a curve", () => {
    const layout = layoutTree(TREE, initialCollapsed(TREE), 900);

    expect(layout.links.map((link) => link.id).sort()).toEqual(["1-2", "1-3"]);
    expect(layout.links[0]?.path).toMatch(/^M[\d.-]+,[\d.-]+C/);
  });

  it("carries the partner's status", () => {
    const layout = layoutTree(node(1, [node(2, [], { is_active: false })]), new Set(), 900);

    expect(layout.nodes.find((n) => n.id === 2)?.isActive).toBe(false);
  });
});
