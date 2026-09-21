import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { ComparisonFilters } from "./comparison-filters";
import type { FilterOptions } from "@/lib/types";


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
  // Use controlled state simulation with individual changes
  render(<ComparisonFilters kind="player" value={{}} options={playerOptions} onChange={onChange} disabled={false} />);
  fireEvent.change(screen.getByLabelText("From season"), { target: { value: "2015" } });
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ season_from: 2015 }));

  fireEvent.change(screen.getByLabelText("Team"), { target: { value: "MIA" } });
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ team: "MIA" }));
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
