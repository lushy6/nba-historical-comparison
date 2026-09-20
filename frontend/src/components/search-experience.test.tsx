import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SearchExperience } from "./search-experience";


const playerSearch = {
  items: [{ id: "7:2022-23", name: "Aster Guard", season: "2022-23", kind: "player" }],
};

const playerComparison = {
  selected: { id: "7:2022-23", name: "Aster Guard", season: "2022-23" },
  match: { id: "11:2015-16", name: "Beacon Wing", season: "2015-16" },
  similarity_score: 93.4,
  power_ranking: { rank: 1, tier: "Mirror" },
  features_used: ["points"],
  radar: [],
};

afterEach(() => vi.unstubAllGlobals());

describe("SearchExperience", () => {
  it("searches players and reveals a selected comparison", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(playerSearch)))
      .mockResolvedValueOnce(new Response(JSON.stringify(playerComparison)));
    vi.stubGlobal("fetch", fetchMock);

    render(<SearchExperience />);

    const input = screen.getByRole("searchbox", { name: "Search NBA history" });
    fireEvent.change(input, { target: { value: "aster" } });

    const result = await screen.findByRole("button", { name: /Aster Guard/ });
    fireEvent.click(result);

    await waitFor(() => {
      expect(screen.getByText("93.4")).toBeInTheDocument();
      expect(screen.getByText("Beacon Wing")).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/players/search?q=aster"),
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/players/7%3A2022-23/compare"),
      expect.any(Object),
    );
  });
});
