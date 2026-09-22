import "@testing-library/jest-dom/vitest";

// Recharts uses ResizeObserver for ResponsiveContainer - polyfill for jsdom.
// jsdom's ResizeObserver doesn't report dimensions, so Recharts gets 0x0.
// We replace it with a stub that reports a default size so charts render.
class ResizeObserverStub {
  observe(_target: Element) {}
  unobserve(_target: Element) {}
  disconnect() {}
}

(globalThis as any).ResizeObserver = ResizeObserverStub;
