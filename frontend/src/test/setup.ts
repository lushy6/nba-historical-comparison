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
