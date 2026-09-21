import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";

import { SimilarityLeaderboard } from "./similarity-leaderboard";
import type { RankedMatch } from "@/lib/types";


function makeMatch(id: string, name: string, rank: number, score: number): RankedMatch {
  return {
    profile: {
      id,
      name,
      season: "2022-23",
      teams: [{ code: "BOS", name: "Boston Celtics" }],
      visual: { kind: "player", nba_id: null, image_url: null },
    },
    similarity_score: score,
    power_ranking: { rank, tier: "Mirror" },
    metrics: { basic: [], advanced: [] },
  };
}

const matches: RankedMatch[] = [
  makeMatch("a", "Aster Guard", 1, 97.3),
  makeMatch("b", "Beacon Wing", 2, 91.2),
];

it("renders all leaderboard rows", () => {
  render(<SimilarityLeaderboard kind="player" selectedId="a" matches={matches} onSelect={vi.fn()} />);
  expect(screen.getByText("Aster Guard")).toBeInTheDocument();
  expect(screen.getByText("Beacon Wing")).toBeInTheDocument();
});

it("marks the active row with aria-current", () => {
  render(<SimilarityLeaderboard kind="player" selectedId="a" matches={matches} onSelect={vi.fn()} />);
  const rows = screen.getAllByRole("button");
  expect(rows[0]).toHaveAttribute("aria-current", "true");
  expect(rows[0]).toHaveAttribute("data-active", "true");
  expect(rows[1]).toHaveAttribute("data-active", "false");
  expect(rows[1]).not.toHaveAttribute("aria-current");
});

it("calls onSelect with the profile id when a row is clicked", () => {
  const onSelect = vi.fn();
  render(<SimilarityLeaderboard kind="player" selectedId="a" matches={matches} onSelect={onSelect} />);
  fireEvent.click(screen.getByText("Beacon Wing").closest("button")!);
  expect(onSelect).toHaveBeenCalledWith("b");
});

it("marks the active row and changes it through keyboard activation", () => {
  const onSelect = vi.fn();
  render(<SimilarityLeaderboard kind="player" selectedId="a" matches={matches} onSelect={onSelect} />);
  const secondRow = screen.getAllByRole("button")[1];
  fireEvent.keyDown(secondRow, { key: "Enter" });
  expect(onSelect).toHaveBeenCalledWith("b");
  // First row still has aria-current (parent controls active state)
  expect(screen.getAllByRole("button")[0]).toHaveAttribute("aria-current", "true");
});

it("renders empty without crashing when matches is empty", () => {
  const { container } = render(<SimilarityLeaderboard kind="player" selectedId="a" matches={[]} onSelect={vi.fn()} />);
  expect(container.firstChild).toBeNull();
});

it("caps its rows and count at 15 and cannot activate a hidden match", () => {
  const onSelect = vi.fn();
  const many = Array.from({ length: 17 }, (_, i) => makeMatch(String(i), `Player ${i + 1}`, i + 1, 90));
  render(<SimilarityLeaderboard kind="player" selectedId="0" matches={many} onSelect={onSelect} />);
  expect(screen.getByText("Top 15 historical matches")).toBeInTheDocument();
  expect(screen.getAllByRole("button")).toHaveLength(15);
  expect(screen.queryByText("Player 16")).not.toBeInTheDocument();
  fireEvent.keyDown(screen.getAllByRole("button")[14], { key: " " });
  expect(onSelect).toHaveBeenCalledExactlyOnceWith("14");
});

it("limits chrome transitions to transform/opacity below 300ms and has no entrance animation", () => {
  const css = readFileSync("src/app/globals.css", "utf8");
  const transitions = [...css.matchAll(/\btransition:\s*([^;]+);/g)];
  expect(transitions.length).toBeGreaterThan(0);
  for (const [, declaration] of transitions) {
    for (const transition of declaration.split(",")) {
      expect(transition.trim()).toMatch(/^(none|transform|opacity)\b/);
      for (const [, number, unit] of transition.matchAll(/(\d*\.?\d+)(ms|s)\b/g)) {
        expect(Number(number) * (unit === "s" ? 1000 : 1)).toBeLessThan(300);
      }
    }
  }
  for (const [, animation] of css.matchAll(/\banimation:\s*([^;]+);/g)) {
    expect(animation.trim()).toBe("none");
  }
  // Press transforms exclude keyboard focus; the same selector is overridden in reduced motion.
  for (const name of ["mode-button", "result-option", "leaderboard-row"]) {
    const selector = `.${name}:active:not(:focus-visible)`;
    expect(css.slice(css.indexOf("@media (prefers-reduced-motion: reduce)")).includes(selector)).toBe(true);
  }
});
