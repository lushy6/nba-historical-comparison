import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";


describe("HomePage", () => {
  it("introduces the historical comparison search", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Find the season that echoes today.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("searchbox", { name: "Search NBA history" }),
    ).toBeInTheDocument();
  });
});
