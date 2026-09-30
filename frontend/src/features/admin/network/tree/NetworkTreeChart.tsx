import { select } from "d3-selection";
import { zoom, type D3ZoomEvent } from "d3-zoom";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { initialCollapsed, layoutTree, NODE_RADIUS } from "./layout";
import type { TreeNode } from "./types";

const HEIGHT = 560;
const FALLBACK_WIDTH = 900;
const COLOR_ACTIVE = "#365c80";
const COLOR_INACTIVE = "#c0392b";
const COLOR_LINK = "#b9c6d3";

export function NetworkTreeChart({ root }: { root: TreeNode }) {
  const container = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(FALLBACK_WIDTH);
  const [collapsed, setCollapsed] = useState(() => initialCollapsed(root));
  const [transform, setTransform] = useState("");

  useEffect(() => {
    const measure = () => setWidth(container.current?.clientWidth || FALLBACK_WIDTH);
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  // Wheel zooms, dragging pans. d3-zoom owns the gesture, React owns what is drawn.
  useEffect(() => {
    const element = svg.current;
    if (!element) return;
    const behaviour = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 2.5])
      .on("zoom", (event: D3ZoomEvent<SVGSVGElement, unknown>) =>
        setTransform(event.transform.toString()),
      );
    select(element).call(behaviour);
    return () => {
      select(element).on(".zoom", null);
    };
  }, []);

  const layout = useMemo(() => layoutTree(root, collapsed, width), [root, collapsed, width]);

  function toggle(id: number) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  return (
    <div className="network-tree-chart" ref={container}>
      <svg
        ref={svg}
        width="100%"
        height={HEIGHT}
        viewBox={`0 0 ${width} ${HEIGHT}`}
        role="img"
        aria-label="Дерево сети партнёров"
      >
        <g transform={transform}>
          <g className="network-links">
            {layout.links.map((link) => (
              <path
                key={link.id}
                className="network-link"
                d={link.path}
                fill="none"
                stroke={COLOR_LINK}
                strokeWidth={1.5}
              />
            ))}
          </g>
          <g className="network-nodes">
            {layout.nodes.map((node) => {
              const onKeyDown = (event: KeyboardEvent) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  toggle(node.id);
                }
              };
              return (
                <g
                  key={node.id}
                  className="network-node"
                  transform={`translate(${node.x},${node.y})`}
                  {...(node.hasChildren
                    ? {
                        role: "button",
                        tabIndex: 0,
                        "aria-expanded": node.expanded,
                        onClick: () => toggle(node.id),
                        onKeyDown,
                      }
                    : {})}
                >
                  <title>{[node.name, node.email, node.phone].filter(Boolean).join(" · ")}</title>
                  <circle
                    r={NODE_RADIUS}
                    fill={node.isActive ? COLOR_ACTIVE : COLOR_INACTIVE}
                    stroke="#fff"
                    strokeWidth={2}
                  />
                  <text
                    dy="0.32em"
                    x={node.hasChildren ? -(NODE_RADIUS + 6) : NODE_RADIUS + 6}
                    textAnchor={node.hasChildren ? "end" : "start"}
                    fill="#27374a"
                    fontSize="13px"
                    fontFamily="inherit"
                  >
                    {node.name}
                  </text>
                  {node.hasChildren && (
                    <circle
                      className="network-toggle-ring"
                      r={NODE_RADIUS + 4}
                      fill="none"
                      stroke={COLOR_LINK}
                      strokeWidth={1}
                    />
                  )}
                </g>
              );
            })}
          </g>
        </g>
      </svg>
    </div>
  );
}
