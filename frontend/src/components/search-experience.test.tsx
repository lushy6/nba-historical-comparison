import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, within } from "@testing-library/react";

import { SearchExperience } from "./search-experience";
import type { Comparison, Profile, SearchResponse } from "@/lib/types";


const playerSearch: SearchResponse = {
  items: [{ ...makeProfile("7:2022-23", "Aster Guard", "2022-23"), kind: "player" }],
};

function makeProfile(id: string, name: string, season: string): Profile {
  return {
    id,
    name,
    season,
    teams: [{ code: "MIA", name: "Miami Heat" }],
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

const playerComparison: Comparison = {
  selected: makeProfile("7:2022-23", "Aster Guard", "2022-23"),
  match: firstMatch,
  matches: [firstMatch, secondMatch],
  scope: { season_from: null, season_to: null, team: null, eligible_count: 2 },
  features_used: ["points"],
};

const filterOptions = { seasons: [1997, 2015, 2022], teams: [{ code: "MIA", name: "Miami Heat" }], team_filter_available: true };

function deferredResponse() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>((done) => { resolve = done; });
  return { promise, resolve };
}

function mockService(compare?: Promise<Response>, filters?: Promise<Response>) {
  const fetchMock = vi.fn((url: string, _options?: RequestInit): Promise<Response> => {
    if (url.includes("/filters")) return filters ?? Promise.resolve(Response.json(filterOptions));
    if (url.includes("/compare")) return compare ?? Promise.resolve(Response.json(playerComparison));
    return Promise.resolve(Response.json(playerSearch));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function choosePlayer() {
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "aster" } });
  fireEvent.click(await screen.findByRole("button", { name: /Aster Guard/ }));
}

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
    expect(screen.getByRole("heading", { name: "Cinder Center" })).toBeInTheDocument();
    expect(leaderboardButtons[1]).toHaveAttribute("data-active", "true");
  });

  it("keeps a comparison through metadata arrival and unchanged scope, then clears it on a real scope change", async () => {
    const filters = deferredResponse();
    mockService(undefined, filters.promise);
    render(<SearchExperience />);
    await choosePlayer();
    await screen.findByRole("heading", { name: "Beacon Wing" });
    expect(screen.getByRole("status")).toHaveTextContent("Loading comparison filters");
    await act(async () => filters.resolve(Response.json(filterOptions)));
    expect(screen.getByRole("heading", { name: "Beacon Wing" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("From season"), { target: { value: "" } });
    expect(screen.getByRole("heading", { name: "Beacon Wing" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("From season"), { target: { value: "2015" } });
    expect(screen.queryByRole("region", { name: "Historical comparison result" })).not.toBeInTheDocument();
  });

  it("keeps filters and results when the already-active mode is chosen", async () => {
    const fetchMock = mockService();
    render(<SearchExperience />);
    await choosePlayer();
    await screen.findByRole("heading", { name: "Beacon Wing" });
    fireEvent.click(screen.getByRole("button", { name: "Players" }));
    expect(screen.getByLabelText("From season")).toBeEnabled();
    expect(screen.getByRole("heading", { name: "Beacon Wing" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url.includes("/filters"))).toHaveLength(1);
    fireEvent.change(screen.getByLabelText("From season"), { target: { value: "2015" } });
    expect(screen.getByLabelText("From season")).toHaveValue("2015");
  });

  it.each(["scope", "mode"])("aborts comparison on %s change and ignores a response that still resolves", async (change) => {
    const comparison = deferredResponse();
    const fetchMock = mockService(comparison.promise);
    render(<SearchExperience />);
    await choosePlayer();
    const signal = fetchMock.mock.calls.find(([url]) => url.includes("/compare"))![1]!.signal!;
    expect(signal.aborted).toBe(false);
    if (change === "scope") {
      fireEvent.change(screen.getByLabelText("From season"), { target: { value: "2015" } });
    } else {
      fireEvent.click(screen.getByRole("button", { name: "Teams" }));
    }
    expect(signal.aborted).toBe(true);
    await act(async () => comparison.resolve(Response.json(playerComparison)));
    expect(screen.queryByRole("heading", { name: "Beacon Wing" })).not.toBeInTheDocument();
    expect(screen.queryByText("Measuring the historical shape.")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("resets all scope fields when comparison type changes", async () => {
    mockService();
    render(<SearchExperience />);
    await waitFor(() => expect(screen.getByLabelText("From season")).toBeEnabled());
    fireEvent.change(screen.getByLabelText("From season"), { target: { value: "2015" } });
    fireEvent.change(screen.getByLabelText("To season"), { target: { value: "2022" } });
    fireEvent.change(screen.getByLabelText("Team"), { target: { value: "MIA" } });
    fireEvent.click(screen.getByRole("button", { name: "Teams" }));
    await waitFor(() => expect(screen.getByLabelText("From season")).toBeEnabled());
    expect(screen.getByLabelText("From season")).toHaveValue("");
    expect(screen.getByLabelText("To season")).toHaveValue("");
    expect(screen.queryByLabelText("Team")).not.toBeInTheDocument();
  });

  it("shows a loading skeleton followed by an inline metadata error", async () => {
    const filters = deferredResponse();
    mockService(undefined, filters.promise);
    const { container } = render(<SearchExperience />);
    expect(screen.getByRole("group", { name: "Comparison pool" })).toHaveAttribute("aria-busy", "true");
    expect(container.querySelectorAll(".filter-skeleton")).toHaveLength(2);
    await act(async () => filters.resolve(Response.json({ detail: "Unavailable" }, { status: 503 })));
    expect(screen.getByRole("alert")).toHaveTextContent("Comparison filters could not load");
    expect(screen.getByLabelText("From season")).toBeDisabled();
    expect(container.querySelector(".filter-skeleton")).not.toBeInTheDocument();
  });

  it("renders enriched autocomplete and immediate keyboard-triggered loading/results", async () => {
    const comparison = deferredResponse();
    mockService(comparison.promise);
    render(<SearchExperience />);
    const input = screen.getByRole("searchbox");
    fireEvent.keyDown(input, { key: "a" });
    fireEvent.change(input, { target: { value: "aster" } });
    const row = await screen.findByRole("button", { name: /Aster Guard/ });
    expect(within(row).getByText("2022-23 · Miami Heat")).toBeInTheDocument();
    expect(within(row).getByText("AG")).toBeInTheDocument();
    row.focus();
    fireEvent.click(row, { detail: 0 });
    expect(screen.getByRole("status")).toHaveTextContent("Measuring the historical shape.");
    expect(screen.getByRole("status").style.opacity).not.toBe("0");
    expect(screen.getByRole("status").style.transform).toBe("");
    await act(async () => comparison.resolve(Response.json(playerComparison)));
    const result = screen.getByRole("region", { name: "Historical comparison result" });
    expect(result.style.opacity).not.toBe("0");
    expect(result.style.transform).toBe("");
  });

  it("retains only 15 selectable matches even if the service returns more", async () => {
    const matches = Array.from({ length: 17 }, (_, i) => makeMatch(`match-${i}`, `Match ${i + 1}`, i + 1, 90));
    mockService(Promise.resolve(Response.json({ ...playerComparison, matches })));
    render(<SearchExperience />);
    await choosePlayer();
    const leaderboard = await screen.findByRole("navigation", { name: "Top matches leaderboard" });
    expect(within(leaderboard).getAllByRole("button")).toHaveLength(15);
    expect(screen.queryByText("Match 16")).not.toBeInTheDocument();
    fireEvent.click(within(leaderboard).getAllByRole("button")[14]);
    expect(screen.getByRole("heading", { name: "Match 15" })).toBeInTheDocument();
  });
});
