import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { TooltipIntentProvider, useTooltipIntent } from "./tooltip-intent";


function TooltipHarness() {
  const { requestOpen, isOpen } = useTooltipIntent();
  return (
    <div>
      <button
        type="button"
        aria-label="First mark"
        onPointerEnter={() => requestOpen("first", true)}
        onPointerLeave={() => requestOpen("first", false)}
      >
        First mark
      </button>
      {isOpen("first") && <div>First detail</div>}
      <button
        type="button"
        aria-label="Second mark"
        onPointerEnter={() => requestOpen("second", true)}
        onPointerLeave={() => requestOpen("second", false)}
      >
        Second mark
      </button>
      {isOpen("second") && <div>Second detail</div>}
    </div>
  );
}

it("delays the first tooltip and opens the next graph mark immediately", () => {
  vi.useFakeTimers();
  render(
    <TooltipIntentProvider>
      <TooltipHarness />
    </TooltipIntentProvider>,
  );

  fireEvent.pointerEnter(screen.getByRole("button", { name: "First mark" }));
  expect(screen.queryByText("First detail")).not.toBeInTheDocument();

  act(() => {
    vi.advanceTimersByTime(500);
  });
  expect(screen.getByText("First detail")).toBeInTheDocument();

  // Move to second mark - should show immediately since we already opened once
  act(() => {
    fireEvent.pointerLeave(screen.getByRole("button", { name: "First mark" }));
    fireEvent.pointerEnter(screen.getByRole("button", { name: "Second mark" }));
  });
  expect(screen.getByText("Second detail")).toBeInTheDocument();

  vi.useRealTimers();
});

it("hides tooltip on pointer leave", () => {
  vi.useFakeTimers();
  render(
    <TooltipIntentProvider>
      <TooltipHarness />
    </TooltipIntentProvider>,
  );

  fireEvent.pointerEnter(screen.getByRole("button", { name: "First mark" }));
  act(() => {
    vi.advanceTimersByTime(500);
  });
  expect(screen.getByText("First detail")).toBeInTheDocument();

  fireEvent.pointerLeave(screen.getByRole("button", { name: "First mark" }));
  expect(screen.queryByText("First detail")).not.toBeInTheDocument();

  vi.useRealTimers();
});
