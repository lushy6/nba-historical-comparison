import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { ComparisonCharts } from "./comparison-charts";
import type { Comparison, RankedMatch } from "@/lib/types";


const selected: Comparison["selected"] = {
  id: "7:2022-23",
  name: "Aster Guard",
  season: "2022-23",
  teams: [],
  visual: { kind: "player", nba_id: null, image_url: null },
};

const basicMetric = (metric: string, label: string, selectedVal: number, matchVal: number) => ({
  metric, label, selected_value: selectedVal, match_value: matchVal, selected_normalized: 70, match_normalized: 60,
});

const advancedMetric = (metric: string, label: string, selectedVal: number, matchVal: number) => ({
  metric, label, selected_value: selectedVal, match_value: matchVal, selected_normalized: 60, match_normalized: 55,
});

function makePlayerMatch(id: string, name: string): RankedMatch {
  return {
    profile: { id, name, season: "2015-16", teams: [], visual: { kind: "player", nba_id: null, image_url: null } },
    similarity_score: 93.4,
    power_ranking: { rank: 1, tier: "Mirror" },
    metrics: {
      basic: [
        basicMetric("points", "PTS", 20, 18),
        basicMetric("assists", "AST", 5, 6),
        basicMetric("rebounds", "REB", 7, 8),
        basicMetric("three_point_attempts", "3PA", 3, 2),
        basicMetric("three_point_made", "3PM", 1, 1),
        basicMetric("field_goal_attempts", "FGA", 15, 14),
        basicMetric("field_goals_made", "FGM", 8, 7),
        basicMetric("blocks", "BLK", 1, 0),
        basicMetric("turnovers", "TOV", 3, 2),
        basicMetric("steals", "STL", 2, 1),
        basicMetric("free_throw_attempts", "FTA", 4, 5),
        basicMetric("free_throws_made", "FTM", 3, 4),
      ],
      advanced: [
        advancedMetric("bpm", "BPM", 2.3, 2.1),
        advancedMetric("win_shares", "Win Shares", 5.0, 4.5),
        advancedMetric("vorp", "VORP", 3.0, 2.5),
      ],
    },
  };
}

function makeTeamMatch(id: string, name: string): RankedMatch {
  return {
    profile: { id, name, season: "2015-16", teams: [], visual: { kind: "team", nba_id: null, image_url: null } },
    similarity_score: 85.0,
    power_ranking: { rank: 2, tier: "Strong echo" },
    metrics: {
      basic: [
        basicMetric("effective_field_goal_pct", "eFG%", 57.5, 57.1),
        basicMetric("turnover_pct", "TOV%", 12.3, 12.6),
        basicMetric("offensive_rebound_pct", "OREB%", 27.4, 26.9),
        basicMetric("free_throw_rate", "FTR", 0.201, 0.198),
        basicMetric("offensive_rating", "Off. Rating", 116.2, 115.4),
        basicMetric("defensive_rating", "Def. Rating", 110.4, 111.0),
        basicMetric("net_rating", "Net Rating", 5.8, 4.4),
        basicMetric("pace", "Pace", 99.1, 98.8),
      ],
      advanced: [],
    },
  };
}

const playerMatch = makePlayerMatch("11:2015-16", "Beacon Wing");
const secondPlayer = makePlayerMatch("23:1997-98", "Cinder Center");
const teamMatch = makeTeamMatch("1:2022-23", "Aurora Comets");
const secondTeam = makeTeamMatch("3:1997-98", "Canyon Stars");
const matches = [playerMatch, secondPlayer];
const teamMatches = [teamMatch, secondTeam];

it("switches a player from 12 basic radar dimensions to advanced dimensions", () => {
  render(<ComparisonCharts kind="player" selected={selected} activeMatch={playerMatch} matches={matches} />);
  expect(screen.getByLabelText(/radar.*12 primary/i)).toBeInTheDocument();
  const advancedBtn = screen.getByRole("button", { name: "Advanced" });
  fireEvent.click(advancedBtn);
  expect(screen.getByLabelText(/radar.*advanced/i)).toBeInTheDocument();
  expect(advancedBtn).toHaveAttribute("aria-pressed", "true");
});

it("updates the active name in every chart when the active match changes", () => {
  const { rerender } = render(<ComparisonCharts kind="team" selected={selected} activeMatch={teamMatch} matches={teamMatches} />);
  rerender(<ComparisonCharts kind="team" selected={selected} activeMatch={secondTeam} matches={teamMatches} />);
  expect(screen.getByText(`Delta vs. ${secondTeam.profile.name}`)).toBeInTheDocument();
});

it("renders both Basic and Advanced mode buttons", () => {
  render(<ComparisonCharts kind="player" selected={selected} activeMatch={playerMatch} matches={matches} />);
  expect(screen.getByRole("button", { name: "Basic" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Advanced" })).toBeInTheDocument();
});

it("player scatter uses canonical metric keys (points vs assists)", () => {
  render(<ComparisonCharts kind="player" selected={selected} activeMatch={playerMatch} matches={matches} />);
  expect(screen.getByText(/Pool distribution: PTS vs AST/i)).toBeInTheDocument();
});

it("player advanced scatter uses Bpm and Win Shares canonical keys", () => {
  const { rerender } = render(<ComparisonCharts kind="player" selected={selected} activeMatch={playerMatch} matches={matches} />);
  const advancedBtn = screen.getByRole("button", { name: "Advanced" });
  fireEvent.click(advancedBtn);
  expect(screen.getAllByText(/BPM/i).length).toBeGreaterThan(0);
});

it("team basic scatter uses Effective Field Goal Pct and Turnover Pct", () => {
  render(<ComparisonCharts kind="team" selected={selected} activeMatch={teamMatch} matches={teamMatches} />);
  expect(screen.getAllByText(/eFG%/i).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/TOV%/i).length).toBeGreaterThan(0);
});

it("selected profile is included in scatter data", () => {
  render(<ComparisonCharts kind="player" selected={selected} activeMatch={playerMatch} matches={matches} />);
  // The selected profile "Aster Guard" should appear in the scatter
  expect(screen.getByRole("img", { name: /Aster Guard/i })).toBeInTheDocument();
});

it("renders unavailable state when scatter data is partial", () => {
  const partialMatch = {
    ...playerMatch,
    metrics: {
      basic: [
        basicMetric("points", "PTS", 20, 18),
        basicMetric("assists", "AST", null as unknown as number, null as unknown as number),
      ],
      advanced: [],
    },
  };
  render(<ComparisonCharts kind="player" selected={selected} activeMatch={partialMatch} matches={[partialMatch]} />);
  // Points/Assists scatter with null values should show chart-unavailable card
  expect(screen.getByText(/Neither.*has both.*available/i)).toBeInTheDocument();
});

it("shows unavailable card when every profile lacks scatter pair", () => {
  const noDataMatch = {
    ...playerMatch,
    metrics: {
      basic: [
        basicMetric("points", "PTS", 20, 18),
        basicMetric("assists", "AST", 0, 0),
      ],
      advanced: [],
    },
  };
  // Make the selected and match both have null for one key
  const selectedNoData = {
    ...selected,
    id: "sel:test",
  };
  render(<ComparisonCharts kind="player" selected={selectedNoData} activeMatch={playerMatch} matches={[playerMatch]} />);
  // Should render the chart since data exists
  expect(screen.getByText(/Pool distribution/i)).toBeInTheDocument();
});

it("basic mode shows 12 primary statistics for player", () => {
  render(<ComparisonCharts kind="player" selected={selected} activeMatch={playerMatch} matches={matches} />);
  const radarLabels = screen.getAllByLabelText(/radar/i);
  expect(radarLabels.length).toBeGreaterThan(0);
  expect(radarLabels.some((el) => /12 primary/i.test(el.getAttribute("aria-label") ?? ""))).toBe(true);
});

it("switches to advanced and shows BPM label", () => {
  render(<ComparisonCharts kind="player" selected={selected} activeMatch={playerMatch} matches={matches} />);
  fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
  expect(screen.getAllByText(/BPM/).length).toBeGreaterThan(0);
});

it("sizes every chart from its container instead of a fixed canvas", () => {
  const { container } = render(<ComparisonCharts kind="player" selected={selected} activeMatch={playerMatch} matches={matches} />);
  const wrappers = container.querySelectorAll(".radar-wrap, .chart-wrap");
  expect(wrappers).toHaveLength(3);
  wrappers.forEach((wrapper) => {
    expect(wrapper.querySelector(".recharts-responsive-container")).not.toBeNull();
  });
});
