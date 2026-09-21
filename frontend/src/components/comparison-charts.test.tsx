import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { ComparisonCharts } from "./comparison-charts";
import type { Comparison, RankedMatch } from "@/lib/types";


const selected: Comparison["selected"] = {
  id: "7:2022-23",
  name: "Aster Guard",
  season: "2022-23",
  teams: [],
  visual: { kind: "player", nba_id: null, image_url: null },
};

const basicMetric = (metric: string, label: string) => ({
  metric, label, selected_value: 20, match_value: 18, selected_normalized: 70, match_normalized: 60,
});

const advancedMetric = (metric: string, label: string) => ({
  metric, label, selected_value: 2.3, match_value: 2.1, selected_normalized: 60, match_normalized: 55,
});

function makeMatch(id: string, name: string): RankedMatch {
  return {
    profile: { id, name, season: "2015-16", teams: [], visual: { kind: "player", nba_id: null, image_url: null } },
    similarity_score: 93.4,
    power_ranking: { rank: 1, tier: "Mirror" },
    metrics: {
      basic: [
        basicMetric("points", "PTS"), basicMetric("assists", "AST"), basicMetric("rebounds", "REB"),
        basicMetric("three_point_attempts", "3PA"), basicMetric("three_point_made", "3PM"),
        basicMetric("field_goal_attempts", "FGA"), basicMetric("field_goals_made", "FGM"),
        basicMetric("blocks", "BLK"), basicMetric("turnovers", "TOV"), basicMetric("steals", "STL"),
        basicMetric("free_throw_attempts", "FTA"), basicMetric("free_throws_made", "FTM"),
      ],
      advanced: [advancedMetric("bpm", "BPM"), advancedMetric("vorp", "VORP")],
    },
  };
}

const match = makeMatch("11:2015-16", "Beacon Wing");
const second = makeMatch("23:1997-98", "Cinder Center");
const matches = [match, second];

it("switches a player from 12 basic radar dimensions to advanced dimensions", () => {
  render(<ComparisonCharts kind="player" selected={selected} activeMatch={match} matches={matches} />);
  // Basic mode: radar label should contain "12 primary"
  expect(screen.getByLabelText(/radar.*12 primary/i)).toBeInTheDocument();
  // Switch to advanced
  const advancedBtn = screen.getByRole("button", { name: "Advanced" });
  fireEvent.click(advancedBtn);
  // After switching, the radar label should change to advanced
  expect(screen.getByLabelText(/radar.*advanced/i)).toBeInTheDocument();
  // Advanced button should now be pressed
  expect(advancedBtn).toHaveAttribute("aria-pressed", "true");
});

it("updates the active name in every chart when the active match changes", () => {
  const { rerender } = render(<ComparisonCharts kind="team" selected={selected} activeMatch={match} matches={[match, second]} />);
  rerender(<ComparisonCharts kind="team" selected={selected} activeMatch={second} matches={[match, second]} />);
  // The kicker shows the match name
  expect(screen.getByText(`Delta vs. ${second.profile.name}`)).toBeInTheDocument();
});

it("renders both Basic and Advanced mode buttons", () => {
  render(<ComparisonCharts kind="player" selected={selected} activeMatch={match} matches={matches} />);
  expect(screen.getByRole("button", { name: "Basic" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Advanced" })).toBeInTheDocument();
});
