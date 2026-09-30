import { hierarchy, tree } from "d3-hierarchy";

import type { TreeNode } from "./types";

export const NODE_RADIUS = 7;
export const LEVEL_HEIGHT = 130;
export const SIBLING_GAP = 150;
const TOP_MARGIN = 40;

export interface LaidOutNode {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  isActive: boolean;
  x: number;
  y: number;
  /** Has a downline (drawn with a ring, can be folded). */
  hasChildren: boolean;
  expanded: boolean;
}

export interface LaidOutLink {
  id: string;
  path: string;
}

export interface Layout {
  nodes: LaidOutNode[];
  links: LaidOutLink[];
}

/** Everything below the first level starts folded, as on the old page. */
export function initialCollapsed(root: TreeNode): Set<number> {
  const folded = new Set<number>();
  const visit = (node: TreeNode, isRoot: boolean) => {
    if (node.children.length > 0 && !isRoot) folded.add(node.id);
    node.children.forEach((child) => visit(child, false));
  };
  visit(root, true);
  return folded;
}

function linkPath(sx: number, sy: number, tx: number, ty: number): string {
  const midY = (sy + ty) / 2;
  return `M${sx},${sy}C${sx},${midY} ${tx},${midY} ${tx},${ty}`;
}

/** Positions of the visible nodes (folded branches hidden), centred in `width`. */
export function layoutTree(root: TreeNode, collapsed: ReadonlySet<number>, width: number): Layout {
  const h = hierarchy(root, (node) => (collapsed.has(node.id) ? null : node.children));
  tree<TreeNode>().nodeSize([SIBLING_GAP + NODE_RADIUS * 2, LEVEL_HEIGHT])(h);

  const all = h.descendants();
  const xs = all.map((node) => node.x ?? 0);
  const centerOffset = width / 2 - (Math.min(...xs) + Math.max(...xs)) / 2;
  const at = (node: (typeof all)[number]) => ({
    x: (node.x ?? 0) + centerOffset,
    y: node.depth * LEVEL_HEIGHT + TOP_MARGIN,
  });

  return {
    nodes: all.map((node) => ({
      id: node.data.id,
      name: node.data.name,
      email: node.data.email,
      phone: node.data.phone,
      isActive: node.data.is_active,
      ...at(node),
      hasChildren: node.data.children.length > 0,
      expanded: node.data.children.length > 0 && !collapsed.has(node.data.id),
    })),
    links: h.links().map((link) => {
      const source = at(link.source);
      const target = at(link.target);
      return {
        id: `${link.source.data.id}-${link.target.data.id}`,
        path: linkPath(source.x, source.y, target.x, target.y),
      };
    }),
  };
}
