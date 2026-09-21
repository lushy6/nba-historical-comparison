import { fireEvent, render, screen } from "@testing-library/react";
import type { ImgHTMLAttributes } from "react";
import { expect, it, vi } from "vitest";

import { EntityAvatar } from "./entity-avatar";
import type { Profile } from "@/lib/types";

vi.mock("next/image", () => ({
  default: ({ fill, ...props }: ImgHTMLAttributes<HTMLImageElement> & { fill?: boolean }) => (
    <img {...props} data-fill={String(fill)} />
  ),
}));

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

const teamWithNbaSvgLogo: Profile = {
  ...teamWithoutImage,
  visual: {
    kind: "team",
    nba_id: "1610612738",
    image_url: "https://cdn.nba.com/logos/nba/1610612738/primary/L/logo.svg",
  },
};

it("renders an image when image_url is present", () => {
  render(<EntityAvatar entity={playerWithImage} size="medium" />);
  const image = screen.getByRole("img", { name: /LeBron James/i });
  expect(image).toHaveAttribute("data-fill", "true");
  expect(image).toHaveAttribute("sizes", "48px");
});

it("renders an allowed NBA SVG logo through next/image", () => {
  render(<EntityAvatar entity={teamWithNbaSvgLogo} size="small" />);

  const image = screen.getByRole("img", { name: /Boston Celtics/i });
  expect(image).toHaveAttribute("src", expect.stringContaining("cdn.nba.com/logos/nba/1610612738"));
  expect(image).toHaveAttribute("data-fill", "true");
});

it.each([
  "https://example.invalid/logo.svg",
  "http://cdn.nba.com/logos/nba/1610612738/primary/L/logo.svg",
])("does not mount an image for an untrusted SVG source: %s", (imageUrl) => {
  render(<EntityAvatar entity={{ ...teamWithNbaSvgLogo, visual: { ...teamWithNbaSvgLogo.visual, image_url: imageUrl } }} size="small" />);

  expect(screen.getByText("BC")).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.queryByTestId("avatar-skeleton")).not.toBeInTheDocument();
});

it("keeps a fixed skeleton until the remote image finishes loading", () => {
  const { container } = render(<EntityAvatar entity={playerWithImage} size="medium" />);
  const frame = container.firstChild as HTMLElement;
  const widthBefore = window.getComputedStyle(frame).width;

  expect(screen.getByTestId("avatar-skeleton")).toBeInTheDocument();
  fireEvent.load(screen.getByRole("img", { name: /LeBron James/i }));
  expect(screen.queryByTestId("avatar-skeleton")).not.toBeInTheDocument();
  expect(window.getComputedStyle(frame).width).toBe(widthBefore);
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

it("retries an image when the entity source changes after an error", () => {
  const { rerender } = render(<EntityAvatar entity={playerWithImage} size="medium" />);
  fireEvent.error(screen.getByRole("img", { name: /LeBron James/i }));
  expect(screen.getByText("LJ")).toBeInTheDocument();

  const nextPlayer: Profile = {
    ...playerWithImage,
    id: "2544:2024",
    season: "2023-24",
    visual: {
      ...playerWithImage.visual,
      image_url: "https://cdn.nba.com/headshots/nba/latest/1040x760/2544-new.png",
    },
  };
  rerender(<EntityAvatar entity={nextPlayer} size="medium" />);

  expect(screen.getByRole("img", { name: /LeBron James/i })).toHaveAttribute(
    "src",
    expect.stringContaining("2544-new.png"),
  );
  expect(screen.getByTestId("avatar-skeleton")).toBeInTheDocument();
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
