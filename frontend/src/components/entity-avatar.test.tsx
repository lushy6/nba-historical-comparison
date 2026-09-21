import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { EntityAvatar } from "./entity-avatar";
import type { Profile } from "@/lib/types";


const playerWithImage: Profile = {
  id: "2544:2023",
  name: "LeBron James",
  season: "2022-23",
  teams: [{ code: "LAL", name: "Los Angeles Lakers" }],
  visual: { kind: "player", nba_id: "2544", image_url: "https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png" },
};

const playerWithoutImage: Profile = {
  id: "9999:2023",
  name: "Test Player",
  season: "2022-23",
  teams: [],
  visual: { kind: "player", nba_id: null, image_url: null },
};

const teamWithoutImage: Profile = {
  id: "BOS:2023",
  name: "Boston Celtics",
  season: "2022-23",
  teams: [{ code: "BOS", name: "Boston Celtics" }],
  visual: { kind: "team", nba_id: null, image_url: null },
};

it("renders an image when image_url is present", () => {
  render(<EntityAvatar entity={playerWithImage} size="medium" />);
  expect(screen.getByRole("img", { name: /LeBron James/i })).toBeInTheDocument();
});

it("renders monogram fallback when no image_url", () => {
  render(<EntityAvatar entity={playerWithoutImage} size="medium" />);
  expect(screen.getByText("TP")).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});

it("uses a stable monogram after a remote image error", () => {
  render(<EntityAvatar entity={playerWithImage} size="medium" />);
  const img = screen.getByRole("img", { name: /LeBron James/i });
  fireEvent.error(img);
  expect(screen.getByText("LJ")).toBeInTheDocument();
});

it("renders a decorative fallback without an accessible duplicate label", () => {
  render(<EntityAvatar entity={teamWithoutImage} size="small" decorative />);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  // monogram present but aria-hidden since decorative
  const mono = screen.getByText("BC");
  expect(mono.closest("[aria-hidden]")).not.toBeNull();
});

it("maintains fixed geometry on image error - no layout shift", () => {
  const { container } = render(<EntityAvatar entity={playerWithImage} size="medium" />);
  const frame = container.firstChild as HTMLElement;
  const stylesBefore = window.getComputedStyle(frame);
  const widthBefore = stylesBefore.width;
  fireEvent.error(screen.getByRole("img", { name: /LeBron James/i }));
  const stylesAfter = window.getComputedStyle(frame);
  expect(stylesAfter.width).toBe(widthBefore);
});
