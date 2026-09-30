import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { NetworkTreeChart } from "./NetworkTreeChart";

// Wheel/drag gestures cannot be exercised in jsdom (its synthetic mouse events have no `view`,
// which d3-zoom's mousedown handler needs), so the zoom behaviour is stubbed out here. The
// layout and the click handling, which are ours, are tested for real.
vi.mock("d3-zoom", () => ({
  zoom: () => {
    const behaviour = () => undefined;
    behaviour.scaleExtent = () => behaviour;
    behaviour.on = () => behaviour;
    return behaviour;
  },
}));
import type { TreeNode } from "./types";

const node = (id: number, children: TreeNode[] = [], extra: Partial<TreeNode> = {}): TreeNode => ({
  id,
  name: `Партнёр ${id}`,
  email: `p${id}@example.com`,
  phone: null,
  is_active: true,
  children,
  ...extra,
});

const TREE = node(1, [node(2, [node(4)]), node(3)]);

describe("NetworkTreeChart", () => {
  it("starts with the first level only", () => {
    render(<NetworkTreeChart root={TREE} />);

    expect(screen.getByText("Партнёр 1")).toBeInTheDocument();
    expect(screen.getByText("Партнёр 2")).toBeInTheDocument();
    expect(screen.getByText("Партнёр 3")).toBeInTheDocument();
    expect(screen.queryByText("Партнёр 4")).not.toBeInTheDocument();
  });

  it("expands and folds a branch on click", async () => {
    render(<NetworkTreeChart root={TREE} />);
    const user = userEvent.setup();
    const branch = screen.getByRole("button", { name: /Партнёр 2/ });

    expect(branch).toHaveAttribute("aria-expanded", "false");
    await user.click(branch);
    expect(screen.getByText("Партнёр 4")).toBeInTheDocument();
    expect(branch).toHaveAttribute("aria-expanded", "true");

    await user.click(branch);
    expect(screen.queryByText("Партнёр 4")).not.toBeInTheDocument();
  });

  it("works from the keyboard", async () => {
    render(<NetworkTreeChart root={TREE} />);
    const user = userEvent.setup();

    screen.getByRole("button", { name: /Партнёр 2/ }).focus();
    await user.keyboard("{Enter}");

    expect(screen.getByText("Партнёр 4")).toBeInTheDocument();
  });

  it("makes only nodes with a downline interactive", () => {
    render(<NetworkTreeChart root={TREE} />);

    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual([
      expect.stringContaining("Партнёр 1"),
      expect.stringContaining("Партнёр 2"),
    ]);
    expect(screen.getByText("Партнёр 3").closest("g")).not.toHaveAttribute("role");
  });

  it("colours blocked partners differently", () => {
    const { container } = render(
      <NetworkTreeChart root={node(1, [node(2, [], { is_active: false })])} />,
    );
    const fills = [...container.querySelectorAll("g.network-node > circle:first-of-type")].map(
      (circle) => circle.getAttribute("fill"),
    );

    expect(fills).toEqual(["#365c80", "#c0392b"]);
  });

  it("gives every node a tooltip with name, e-mail and phone", () => {
    render(<NetworkTreeChart root={node(1, [], { phone: "+79990001122" })} />);

    expect(screen.getByText("Партнёр 1 · p1@example.com · +79990001122")).toBeInTheDocument();
  });

  it("draws a partner without a downline", () => {
    render(<NetworkTreeChart root={node(1)} />);

    expect(screen.getByText("Партнёр 1")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("keeps markup safe: names are text, never HTML", () => {
    const { container } = render(
      <NetworkTreeChart root={node(1, [], { name: '<img src=x onerror="alert(1)">' })} />,
    );

    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeInTheDocument();
  });
});
