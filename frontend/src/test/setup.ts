import "@testing-library/jest-dom/vitest";
import { cloneElement, createElement, isValidElement, type ReactNode } from "react";
import { vi } from "vitest";

// jsdom has no layout engine, so every element measures 0x0.
class ResizeObserverStub {
  observe(_target: Element) {}
  unobserve(_target: Element) {}
  disconnect() {}
}

(globalThis as any).ResizeObserver = ResizeObserverStub;

// Recharts' ResponsiveContainer reads its size from layout, which jsdom cannot
// provide, so it warns and renders nothing. Tests swap in a fixed-size stand-in
// that keeps the same wrapper class; the app itself stays responsive.
const TEST_CHART_SIZE = { width: 640, height: 320 };

vi.mock("recharts", async (importOriginal) => {
  const recharts = await importOriginal<typeof import("recharts")>();
  function ResponsiveContainer({ children }: { children?: ReactNode }) {
    return createElement(
      "div",
      { className: "recharts-responsive-container", style: TEST_CHART_SIZE },
      isValidElement(children) ? cloneElement(children, TEST_CHART_SIZE) : children,
    );
  }
  return { ...recharts, ResponsiveContainer };
});
