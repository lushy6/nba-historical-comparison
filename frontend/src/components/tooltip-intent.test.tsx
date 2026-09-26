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

function ChartMarkHarness() {
  const { requestOpen, isOpen } = useTooltipIntent();
  return (
    <div>
      <button
        type="button"
        aria-label="Chart point A"
        onPointerEnter={() => requestOpen("chart-a", true)}
        onPointerLeave={() => requestOpen("chart-a", false)}
      >
        Chart A
      </button>
      {isOpen("chart-a") && <div>Chart A detail</div>}
      <button
        type="button"
        aria-label="Chart point B"
        onPointerEnter={() => requestOpen("chart-b", true)}
        onPointerLeave={() => requestOpen("chart-b", false)}
      >
        Chart B
      </button>
      {isOpen("chart-b") && <div>Chart B detail</div>}
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

it("production chart marks call the tooltip intent API with first-hover delay", () => {
  vi.useFakeTimers();
  render(
    <TooltipIntentProvider>
      <ChartMarkHarness />
    </TooltipIntentProvider>,
  );

  fireEvent.pointerEnter(screen.getByRole("button", { name: "Chart point A" }));
  expect(screen.queryByText("Chart A detail")).not.toBeInTheDocument();

  act(() => {
    vi.advanceTimersByTime(500);
  });
  expect(screen.getByText("Chart A detail")).toBeInTheDocument();

  // Sibling chart mark becomes immediate
  act(() => {
    fireEvent.pointerLeave(screen.getByRole("button", { name: "Chart point A" }));
    fireEvent.pointerEnter(screen.getByRole("button", { name: "Chart point B" }));
  });
  expect(screen.getByText("Chart B detail")).toBeInTheDocument();

  vi.useRealTimers();
});

it("pointer leave cancels pending timers", () => {
  vi.useFakeTimers();
  render(
    <TooltipIntentProvider>
      <TooltipHarness />
    </TooltipIntentProvider>,
  );

  fireEvent.pointerEnter(screen.getByRole("button", { name: "First mark" }));
  act(() => {
    fireEvent.pointerLeave(screen.getByRole("button", { name: "First mark" }));
  });
  // Advance past 500ms - tooltip should NOT appear because leave cancelled it
  act(() => {
    vi.advanceTimersByTime(600);
  });
  expect(screen.queryByText("First detail")).not.toBeInTheDocument();

  vi.useRealTimers();
});

it("unmount clears timers", () => {
  vi.useFakeTimers();
  const { unmount } = render(
    <TooltipIntentProvider>
      <TooltipHarness />
    </TooltipIntentProvider>,
  );

  fireEvent.pointerEnter(screen.getByRole("button", { name: "First mark" }));
  unmount();
  // Advance past 500ms after unmount - should not throw and no tooltip visible
  act(() => {
    vi.advanceTimersByTime(600);
  });
  expect(screen.queryByText("First detail")).not.toBeInTheDocument();

  vi.useRealTimers();
});
