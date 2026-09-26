import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { useState } from "react";

import { ComparisonFilters } from "./comparison-filters";
import type { ComparisonScope, FilterOptions } from "@/lib/types";


const playerOptions: FilterOptions = {
  seasons: [1997, 2015, 2022],
  teams: [
    { code: "LAL", name: "Los Angeles Lakers" },
    { code: "MIA", name: "Miami Heat" },
  ],
  team_filter_available: true,
};

const teamOptions: FilterOptions = {
  seasons: [2015, 2022],
  teams: [],
  team_filter_available: false,
};

it("emits an inclusive player scope with a team", () => {
  const onChange = vi.fn();
  function ControlledFilters() {
    const [scope, setScope] = useState<ComparisonScope>({});
    return <ComparisonFilters kind="player" value={scope} options={playerOptions} onChange={(next) => { onChange(next); setScope(next); }} disabled={false} />;
  }
  render(<ControlledFilters />);
  fireEvent.change(screen.getByLabelText("From season"), { target: { value: "2015" } });
  fireEvent.change(screen.getByLabelText("To season"), { target: { value: "2022" } });
  fireEvent.change(screen.getByLabelText("Team"), { target: { value: "MIA" } });
  expect(onChange).toHaveBeenLastCalledWith({ season_from: 2015, season_to: 2022, team: "MIA" });
});

it("does not render a team selector for team comparisons", () => {
  render(<ComparisonFilters kind="team" value={{}} options={teamOptions} onChange={vi.fn()} disabled={false} />);
  expect(screen.queryByLabelText("Team")).not.toBeInTheDocument();
});

it("converts empty selection to undefined (all history)", () => {
  const onChange = vi.fn();
  render(<ComparisonFilters kind="player" value={{ season_from: 2015 }} options={playerOptions} onChange={onChange} disabled={false} />);
  fireEvent.change(screen.getByLabelText("From season"), { target: { value: "" } });
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ season_from: undefined }));
});

it("disables controls while options are loading", () => {
  render(<ComparisonFilters kind="player" value={{}} options={null} onChange={vi.fn()} disabled={false} />);
  const fieldset = screen.getByRole("group");
  expect(fieldset).toBeDisabled();
});

it("emits the match pool with player wording", () => {
  const onChange = vi.fn();
  render(<ComparisonFilters kind="player" value={{}} options={playerOptions} onChange={onChange} disabled={false} />);
  const pool = screen.getByLabelText("Matches");
  expect(within(pool).getAllByRole("option").map((option) => option.textContent)).toEqual([
    "Any player", "Other players only", "Same player only",
  ]);
  fireEvent.change(pool, { target: { value: "others" } });
  expect(onChange).toHaveBeenLastCalledWith({ pool: "others" });
});

it("offers the match pool for team comparisons with team wording", () => {
  const onChange = vi.fn();
  render(<ComparisonFilters kind="team" value={{}} options={teamOptions} onChange={onChange} disabled={false} />);
  fireEvent.change(screen.getByLabelText("Matches"), { target: { value: "same" } });
  expect(screen.getByRole("option", { name: "Same team only" })).toBeInTheDocument();
  expect(onChange).toHaveBeenLastCalledWith({ pool: "same" });
});
