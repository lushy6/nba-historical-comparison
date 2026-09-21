"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import type { Comparison, ComparisonMetric, EntityKind, RankedMatch } from "@/lib/types";
import { TooltipIntentProvider } from "./tooltip-intent";


type MetricMode = "basic" | "advanced";

type ComparisonChartsProps = {
  kind: EntityKind;
  selected: Comparison["selected"];
  activeMatch: RankedMatch;
  matches: RankedMatch[];
};

export function ComparisonCharts({ kind, selected, activeMatch, matches }: ComparisonChartsProps) {
  const [mode, setMode] = useState<MetricMode>("basic");
  const metrics = activeMatch.metrics[mode];
  const hasAdvanced = activeMatch.metrics.advanced.length > 0;
  const selectedName = selected.name;
  const matchName = activeMatch.profile.name;

  // Radar data: normalized 0-100 values for radar shape
  const radarData = metrics.map((m) => ({
    label: m.label,
    selected: m.selected_normalized,
    match: m.match_normalized,
    selectedRaw: m.selected_value,
    matchRaw: m.match_value,
  }));

  // Delta bars: match minus selected for each metric (normalized difference)
  const deltaData = metrics.map((m) => ({
    label: m.label,
    delta: m.match_normalized - m.selected_normalized,
  }));

  // Scatter: pick 2 dims based on mode and kind
  const scatterPair = pickScatterPair(metrics, kind, mode);
  const scatterPoints = matches.map((match) => {
    const matchMetrics = match.metrics[mode];
    const x = metricValue(matchMetrics, scatterPair[0]);
    const y = metricValue(matchMetrics, scatterPair[1]);
    if (x == null || y == null) return null;
    return { x, y, name: match.profile.name, isActive: match.profile.id === activeMatch.profile.id };
  }).filter(Boolean);

  const radarLabel = mode === "basic"
    ? `Radar comparison of ${selectedName} and ${matchName} across ${metrics.length} primary statistics`
    : `Radar comparison of ${selectedName} and ${matchName} across advanced metrics`;

  return (
    <TooltipIntentProvider>
      <div className="charts-panel">
        {/* Mode toggle */}
        <div className="metric-mode-toggle" role="group" aria-label="Metric mode">
          <button
            type="button"
            className={`mode-button${mode === "basic" ? " is-active" : ""}`}
            aria-pressed={mode === "basic"}
            onClick={() => setMode("basic")}
          >
            Basic
          </button>
          <button
            type="button"
            className={`mode-button${mode === "advanced" ? " is-active" : ""}`}
            aria-pressed={mode === "advanced"}
            disabled={!hasAdvanced}
            onClick={() => setMode("advanced")}
          >
            Advanced
          </button>
        </div>

        {metrics.length === 0 ? (
          <div className="chart-unavailable">
            <p>No {mode} metrics available for this match.</p>
          </div>
        ) : (
          <div className="charts-grid">
            {/* Radar */}
            <article className="comparison-card radar-card">
              <div className="card-title-row">
                <p className="card-kicker">{mode === "basic" ? "Stat profile" : "Advanced profile"}</p>
                <div className="chart-legend" aria-label="Radar chart legend">
                  <span><i className="legend-selected" />{selectedName}</span>
                  <span><i className="legend-match" />{matchName}</span>
                </div>
              </div>
              <div
                className="radar-wrap"
                role="img"
                aria-label={radarLabel}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData} outerRadius="67%">
                    <PolarGrid stroke="#dedfd9" />
                    <PolarAngleAxis dataKey="label" tick={{ fill: "#6f716c", fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ border: "1px solid #dedfd9", borderRadius: 8, boxShadow: "0 8px 24px rgba(23,24,23,.08)" }}
                      formatter={(value: unknown, key: unknown, item: { payload?: { selectedRaw?: number; matchRaw?: number } }) => [
                        Number(key === "selected" ? item.payload?.selectedRaw : item.payload?.matchRaw).toFixed(1),
                        key === "selected" ? selectedName : matchName,
                      ]}
                    />
                    <Radar dataKey="selected" stroke="#e75024" fill="#e75024" fillOpacity={0.15} strokeWidth={2} isAnimationActive animationDuration={220} />
                    <Radar dataKey="match" stroke="#171817" fill="#171817" fillOpacity={0.05} strokeWidth={1.5} isAnimationActive animationDuration={220} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </article>

            {/* Delta bars */}
            <article className="comparison-card delta-card">
              <p className="card-kicker">Delta vs. {matchName}</p>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={deltaData} layout="vertical" margin={{ left: 40, right: 16, top: 8, bottom: 8 }}>
                    <XAxis type="number" domain={[-100, 100]} tick={{ fontSize: 10, fill: "#6f716c" }} />
                    <YAxis type="category" dataKey="label" width={60} tick={{ fontSize: 10, fill: "#6f716c" }} />
                    <Tooltip
                      formatter={(value: unknown) => [`${Number(value).toFixed(1)} pts`, "Delta"]}
                      contentStyle={{ border: "1px solid #dedfd9", borderRadius: 8 }}
                    />
                    <Bar dataKey="delta" radius={2} isAnimationActive animationDuration={220}>
                      {deltaData.map((entry, index) => (
                        <Cell key={index} fill={entry.delta >= 0 ? "#171817" : "#e75024"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </article>

            {/* Scatter */}
            {scatterPoints.length > 0 && scatterPair[0] && scatterPair[1] ? (
              <article className="comparison-card scatter-card">
                <p className="card-kicker">Pool distribution: {scatterPair[0]} vs {scatterPair[1]}</p>
                <div className="chart-wrap">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                      <XAxis type="number" dataKey="x" name={scatterPair[0]} tick={{ fontSize: 10, fill: "#6f716c" }} />
                      <YAxis type="number" dataKey="y" name={scatterPair[1]} tick={{ fontSize: 10, fill: "#6f716c" }} />
                      <ZAxis range={[40, 40]} />
                      <Tooltip
                        cursor={{ strokeDasharray: "3 3" }}
                        content={({ payload }) => {
                          if (!payload?.length) return null;
                          const point = payload[0]?.payload as { name?: string; x?: number; y?: number } | undefined;
                          if (!point) return null;
                          return (
                            <div style={{ background: "white", border: "1px solid #dedfd9", borderRadius: 8, padding: "6px 10px", fontSize: 12 }}>
                              <p style={{ margin: 0, fontWeight: 600 }}>{point.name}</p>
                              <p style={{ margin: 0 }}>{scatterPair[0]}: {point.x?.toFixed(1)}</p>
                              <p style={{ margin: 0 }}>{scatterPair[1]}: {point.y?.toFixed(1)}</p>
                            </div>
                          );
                        }}
                      />
                      <Scatter
                        data={scatterPoints}
                        fill="#171817"
                        fillOpacity={0.4}
                        shape={({ cx, cy, payload }: { cx?: number; cy?: number; payload?: { isActive?: boolean } }) =>
                          payload?.isActive ? (
                            <circle cx={cx} cy={cy} r={6} fill="#e75024" stroke="white" strokeWidth={1.5} />
                          ) : (
                            <circle cx={cx} cy={cy} r={4} fill="#171817" fillOpacity={0.35} />
                          )
                        }
                      />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </article>
            ) : null}
          </div>
        )}
      </div>
    </TooltipIntentProvider>
  );
}

function pickScatterPair(metrics: ComparisonMetric[], kind: EntityKind, mode: MetricMode): [string, string] {
  if (kind === "player") {
    if (mode === "advanced") return ["BPM", "Win Shares"];
    return ["PTS", "AST"];
  }
  if (mode === "advanced") return ["Net Rating", "Pace"];
  return ["eFG%", "TOV%"];
}

function metricValue(metrics: ComparisonMetric[], label: string): number | null {
  const found = metrics.find((m) => m.label === label);
  return found ? found.match_value : null;
}
