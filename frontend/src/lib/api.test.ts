import { afterEach, expect, it, vi } from "vitest";

import { loadComparison, loadFilterOptions, searchHistory } from "./api";


afterEach(() => vi.unstubAllGlobals());

it("serializes only populated scope fields for search", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [] }))));
  await searchHistory("player", "james", { season_from: 2003, season_to: 2013, team: "MIA" });
  expect(vi.mocked(fetch)).toHaveBeenCalledWith(
    expect.stringContaining("season_from=2003"),
    expect.any(Object),
  );
  expect(vi.mocked(fetch)).toHaveBeenCalledWith(
    expect.stringContaining("season_to=2013"),
    expect.any(Object),
  );
  expect(vi.mocked(fetch)).toHaveBeenCalledWith(
    expect.stringContaining("team=MIA"),
    expect.any(Object),
  );
});

it("omits undefined scope fields from search", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [] }))));
  await searchHistory("player", "james", {});
  const url = vi.mocked(fetch).mock.calls[0][0] as string;
  expect(url).not.toContain("season_from");
  expect(url).not.toContain("season_to");
  expect(url).not.toContain("team");
});

it("serializes scope in compare request", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    selected: { id: "x", name: "X", season: "2023", teams: [], visual: { kind: "player", nba_id: null, image_url: null } },
    match: null,
    matches: [],
    scope: { season_from: 2003, season_to: 2013, team: null, eligible_count: 1 },
    features_used: [],
  }))));
  await loadComparison("player", "7:2022-23", { season_from: 2003 });
  const url = vi.mocked(fetch).mock.calls[0][0] as string;
  expect(url).toContain("season_from=2003");
});

it("loads filter options from the filters endpoint", async () => {
  const mockOptions = { seasons: [2023], teams: [], team_filter_available: false };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(mockOptions))));
  const result = await loadFilterOptions("player");
  const url = vi.mocked(fetch).mock.calls[0][0] as string;
  expect(url).toContain("/api/players/filters");
  expect(result.seasons).toEqual([2023]);
});
