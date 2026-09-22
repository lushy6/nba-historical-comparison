import "@testing-library/jest-dom/vitest";

// Recharts uses ResizeObserver for ResponsiveContainer - polyfill for jsdom
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

// Suppress Recharts zero-size chart warnings in jsdom
const originalWarn = console.warn;
console.warn = (...args: unknown[]) => {
  const msg = args.join(" ");
  if (
    msg.includes("width(0) and height(0) of chart should be greater than 0") ||
    msg.includes("The width") ||
    msg.includes("please check the style of container")
  ) {
    return;
  }
  originalWarn.apply(console, args);
};
