import { afterEach, expect, it, vi } from "vitest";

import { loadComparison, loadFilterOptions, searchHistory } from "./api";
import type { SearchResponse } from "./types";


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

it("preserves enriched search profiles from the accepted API contract", async () => {
  const response: SearchResponse = {
    items: [{
      id: "2544:2023",
      name: "LeBron James",
      season: "2022-23",
      kind: "player",
      teams: [{ code: "LAL", name: "Los Angeles Lakers" }],
      visual: {
        kind: "player",
        nba_id: "2544",
        image_url: "https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png",
      },
    }],
  };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(response))));

  const result = await searchHistory("player", "james", {});

  expect(result.items[0].teams[0].code).toBe("LAL");
  expect(result.items[0].visual.nba_id).toBe("2544");
});

it("sends a non-default match pool to compare but never to search", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ items: [] })))));
  await loadComparison("player", "jokicni01:2024", { pool: "others" });
  await loadComparison("player", "jokicni01:2024", { pool: "all" });
  await searchHistory("player", "jokic", { pool: "same" });
  const urls = vi.mocked(fetch).mock.calls.map((call) => call[0] as string);
  expect(urls[0]).toContain("pool=others");
  expect(urls[1]).not.toContain("pool");
  expect(urls[2]).not.toContain("pool");
});
