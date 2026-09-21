import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

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
