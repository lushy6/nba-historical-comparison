import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SearchExperience } from "./search-experience";


const playerSearch = {
  items: [{ id: "7:2022-23", name: "Aster Guard", season: "2022-23", kind: "player" }],
};

function makeProfile(id: string, name: string, season: string) {
  return {
    id,
    name,
    season,
    teams: [],
    visual: { kind: "player", nba_id: null, image_url: null },
  };
}

function makeMatch(id: string, name: string, rank: number, score: number) {
  return {
    profile: makeProfile(id, name, "2015-16"),
    similarity_score: score,
    power_ranking: { rank, tier: "Mirror" },
    metrics: { basic: [], advanced: [] },
  };
}

const firstMatch = makeMatch("11:2015-16", "Beacon Wing", 1, 93.4);
const secondMatch = makeMatch("23:1997-98", "Cinder Center", 2, 87.1);

const playerComparison = {
  selected: makeProfile("7:2022-23", "Aster Guard", "2022-23"),
  match: firstMatch,
  matches: [firstMatch, secondMatch],
  scope: { season_from: null, season_to: null, team: null, eligible_count: 2 },
  features_used: ["points"],
};

const filterOptions = { seasons: [1997, 2015, 2022], teams: [], team_filter_available: false };

afterEach(() => vi.unstubAllGlobals());

describe("SearchExperience", () => {
  it("searches players and reveals a selected comparison with leaderboard", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(filterOptions)))
      .mockResolvedValueOnce(new Response(JSON.stringify(playerSearch)))
      .mockResolvedValueOnce(new Response(JSON.stringify(playerComparison)));
    vi.stubGlobal("fetch", fetchMock);

    render(<SearchExperience />);

    const input = screen.getByRole("searchbox", { name: "Search NBA history" });
    fireEvent.change(input, { target: { value: "aster" } });

    const result = await screen.findByRole("button", { name: /Aster Guard/ });
    fireEvent.click(result);

    await waitFor(() => {
      // Score appears in header and leaderboard - use getAllByText
      expect(screen.getAllByText("93.4").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Beacon Wing").length).toBeGreaterThan(0);
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/players/search?"),
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/players/7%3A2022-23/compare"),
      expect.any(Object),
    );
  });

  it("shows the leaderboard with multiple matches and selecting a row does not re-compare", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(filterOptions)))
      .mockResolvedValueOnce(new Response(JSON.stringify(playerSearch)))
      .mockResolvedValueOnce(new Response(JSON.stringify(playerComparison)));
    vi.stubGlobal("fetch", fetchMock);

    render(<SearchExperience />);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search NBA history" }), { target: { value: "aster" } });
    fireEvent.click(await screen.findByRole("button", { name: /Aster Guard/ }));

    await waitFor(() => {
      expect(screen.getAllByText("Cinder Center").length).toBeGreaterThan(0);
    });

    // Both matches should be in leaderboard
    const leaderboardButtons = screen.getAllByRole("button", { name: /Beacon Wing|Cinder Center/i });
    expect(leaderboardButtons.length).toBeGreaterThanOrEqual(2);

    // No additional compare call when selecting another leaderboard row
    const callsBefore = fetchMock.mock.calls.length;
    fireEvent.click(leaderboardButtons[1]);
    expect(fetchMock.mock.calls.length).toBe(callsBefore);
  });
});
