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
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import {
  Tooltip as RadixTooltip,
  TooltipContent as RadixTooltipContent,
  TooltipProvider as RadixTooltipProvider,
  TooltipTrigger as RadixTooltipTrigger,
} from "@radix-ui/react-tooltip";
import { TooltipIntentProvider, useTooltipIntent } from "./tooltip-intent";
import type { Comparison, ComparisonMetric, EntityKind, RankedMatch } from "@/lib/types";


type MetricMode = "basic" | "advanced";

type ComparisonChartsProps = {
  kind: EntityKind;
  selected: Comparison["selected"];
  activeMatch: RankedMatch;
  matches: RankedMatch[];
};

const PLAYER_BASIC_SCATTER: [string, string] = ["points", "assists"];
const PLAYER_ADVANCED_SCATTER: [string, string] = ["bpm", "win_shares"];
const TEAM_BASIC_SCATTER: [string, string] = ["effective_field_goal_pct", "turnover_pct"];
const TEAM_ADVANCED_SCATTER: [string, string] = ["net_rating", "pace"];

function getScatterPair(mode: MetricMode, kind: EntityKind): [string, string] {
  if (kind === "player") {
    return mode === "advanced" ? PLAYER_ADVANCED_SCATTER : PLAYER_BASIC_SCATTER;
  }
  return mode === "advanced" ? TEAM_ADVANCED_SCATTER : TEAM_BASIC_SCATTER;
}

function getDisplayLabel(metrics: ComparisonMetric[], canonicalKey: string): string {
  const found = metrics.find((m) => m.metric === canonicalKey);
  return found?.label ?? canonicalKey;
}

function metricValue(metrics: ComparisonMetric[], canonicalKey: string): number | null {
  const found = metrics.find((m) => m.metric === canonicalKey);
  return found ? found.match_value : null;
}

interface ScatterPoint {
  id: string;
  x: number;
  y: number;
  name: string;
  isActive: boolean;
  xLabel: string;
  yLabel: string;
  isUnavailable: boolean;
}

function buildScatterData(
  matches: RankedMatch[],
  selected: Comparison["selected"],
  mode: MetricMode,
  xKey: string,
  yKey: string,
): ScatterPoint[] {
  const allMetrics = matches.length > 0 ? matches[0].metrics[mode] : [];
  const xLabel = getDisplayLabel(allMetrics, xKey);
  const yLabel = getDisplayLabel(allMetrics, yKey);

  const allProfiles = [selected, ...matches.map((m) => m.profile)];
  const points: ScatterPoint[] = [];

  for (const profile of allProfiles) {
    const match = matches.find((m) => m.profile.id === profile.id);
    const metrics = match ? match.metrics[mode] : [];
    const x = metricValue(metrics, xKey);
    const y = metricValue(metrics, yKey);
    const isUnavailable = x === null || y === null;
    points.push({
      id: profile.id,
      x: x ?? 0,
      y: y ?? 0,
      name: profile.name,
      isActive: profile.id === selected.id,
      xLabel,
      yLabel,
      isUnavailable,
    });
  }

  return points;
}

function ScatterTooltipContent({ payload, xLabel, yLabel }: { payload?: Array<{ payload?: { x?: number; y?: number; name?: string; isUnavailable?: boolean } }>; xLabel: string; yLabel: string }) {
  if (!payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;
  if (point.isUnavailable) {
    return (
      <div style={{ background: "white", border: "1px solid #dedfd9", borderRadius: 8, padding: "6px 10px", fontSize: 12 }}>
        <p style={{ margin: 0, fontWeight: 600 }}>{point.name}</p>
        <p style={{ margin: 0, color: "#6f716c" }}>Unavailable for this pair</p>
      </div>
    );
  }
  return (
    <div style={{ background: "white", border: "1px solid #dedfd9", borderRadius: 8, padding: "6px 10px", fontSize: 12 }}>
      <p style={{ margin: 0, fontWeight: 600 }}>{point.name}</p>
      <p style={{ margin: 0 }}>{xLabel}: {point.x?.toFixed(1)}</p>
      <p style={{ margin: 0 }}>{yLabel}: {point.y?.toFixed(1)}</p>
    </div>
  );
}

function ScatterMark({ point, intentOpen, intentIsOpen }: { point: ScatterPoint; intentOpen: (key: string, open: boolean) => void; intentIsOpen: (key: string) => boolean }) {
  const isOpen = intentIsOpen(point.id);
  const isUnavailable = point.isUnavailable;
  const commonProps = {
    onPointerEnter: () => intentOpen(point.id, true),
    onPointerLeave: () => intentOpen(point.id, false),
    role: "img" as const,
    "aria-label": isUnavailable
      ? `${point.name}: unavailable for ${point.xLabel} vs ${point.yLabel}`
      : `${point.name}: ${point.xLabel} ${point.x.toFixed(1)}, ${point.yLabel} ${point.y.toFixed(1)}`,
  };

  if (isUnavailable) {
    return (
      <g {...commonProps}>
        <circle cx={point.x} cy={point.y} r={4} fill="#999" fillOpacity={0.3} stroke="#999" strokeWidth={1} strokeDasharray="2 2" />
        {isOpen && (
          <g>
            <circle cx={point.x} cy={point.y} r={20} fill="transparent" />
            <text x={point.x} y={point.y - 10} textAnchor="middle" fontSize={10} fill="#6f716c" fontWeight={600}>Unavailable</text>
          </g>
        )}
      </g>
    );
  }

  return (
    <g {...commonProps}>
      <circle
        cx={point.x} cy={point.y} r={point.isActive ? 6 : 4}
        fill={point.isActive ? "#e75024" : "#171817"}
        fillOpacity={point.isActive ? 0.6 : 0.35}
        stroke={point.isActive ? "#e75024" : "white"}
        strokeWidth={point.isActive ? 1.5 : 0.5}
      />
      {isOpen && (
        <g>
          <circle cx={point.x} cy={point.y} r={20} fill="transparent" />
          <text x={point.x} y={point.y - 10} textAnchor="middle" fontSize={10} fill="#6f716c" fontWeight={600}>{point.name}</text>
        </g>
      )}
    </g>
  );
}

function ComparisonChartsContent({ kind, selected, activeMatch, matches }: ComparisonChartsProps) {
  const [mode, setMode] = useState<MetricMode>("basic");
  const metrics = activeMatch.metrics[mode];
  const hasAdvanced = activeMatch.metrics.advanced.length > 0;
  const selectedName = selected.name;
  const matchName = activeMatch.profile.name;
  const { requestOpen, isOpen } = useTooltipIntent();

  const radarData = metrics.map((m) => ({
    label: m.label,
    selected: m.selected_normalized,
    match: m.match_normalized,
    selectedRaw: m.selected_value,
    matchRaw: m.match_value,
  }));

  const deltaData = metrics.map((m) => ({
    label: m.label,
    delta: m.match_normalized - m.selected_normalized,
  }));

  const [xKey, yKey] = getScatterPair(mode, kind);
  const scatterPoints = buildScatterData(matches, selected, mode, xKey, yKey);
  const allUnavailable = scatterPoints.length > 0 && scatterPoints.every((p) => p.isUnavailable);
  const xLabel = getDisplayLabel(metrics, xKey);
  const yLabel = getDisplayLabel(metrics, yKey);

  const radarLabel = mode === "basic"
    ? `Radar comparison of ${selectedName} and ${matchName} across ${metrics.length} primary statistics`
    : `Radar comparison of ${selectedName} and ${matchName} across advanced metrics`;

  return (
    <div className="charts-panel">
      <RadixTooltip delayDuration={500}>
        <RadixTooltipTrigger asChild>
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
        </RadixTooltipTrigger>
        <RadixTooltipContent>
          <p>Switch between {metrics.length > 0 ? metrics[0].label : "primary"} and advanced metrics</p>
        </RadixTooltipContent>
      </RadixTooltip>

      {metrics.length === 0 ? (
        <div className="chart-unavailable">
          <p>No {mode} metrics available for this match.</p>
        </div>
      ) : (
        <div className="charts-grid">
          <article className="comparison-card radar-card">
            <div className="card-title-row">
              <p className="card-kicker">{mode === "basic" ? "Stat profile" : "Advanced profile"}</p>
              <div className="chart-legend" aria-label="Radar chart legend">
                <span><i className="legend-selected" />{selectedName}</span>
                <span><i className="legend-match" />{matchName}</span>
              </div>
            </div>
            <div className="radar-wrap" role="img" aria-label={radarLabel}>
                <RadarChart data={radarData} outerRadius="67%" width={400} height={384}>
                  <PolarGrid stroke="#dedfd9" />
                  <PolarAngleAxis dataKey="label" tick={{ fill: "#6f716c", fontSize: 10 }} />
                  <Tooltip isAnimationActive={false} contentStyle={{ border: "1px solid #dedfd9", borderRadius: 8, boxShadow: "0 8px 24px rgba(23,24,23,.08)" }} formatter={(value: unknown, key: unknown, item: { payload?: { selectedRaw?: number; matchRaw?: number } }) => [Number(key === "selected" ? item.payload?.selectedRaw : item.payload?.matchRaw).toFixed(1), key === "selected" ? selectedName : matchName]} />
                  <Radar dataKey="selected" stroke="#e75024" fill="#e75024" fillOpacity={0.15} strokeWidth={2} isAnimationActive animationDuration={220} />
                  <Radar dataKey="match" stroke="#171817" fill="#171817" fillOpacity={0.05} strokeWidth={1.5} isAnimationActive animationDuration={220} />
                </RadarChart>
              </div>
          </article>

          <article className="comparison-card delta-card">
            <p className="card-kicker">Delta vs. {matchName}</p>
            <div className="chart-wrap">
                <BarChart data={deltaData} layout="vertical" margin={{ left: 40, right: 16, top: 8, bottom: 8 }} width={400} height={384}>
                  <XAxis type="number" domain={[-100, 100]} tick={{ fontSize: 10, fill: "#6f716c" }} />
                  <YAxis type="category" dataKey="label" width={60} tick={{ fontSize: 10, fill: "#6f716c" }} />
                  <Tooltip isAnimationActive={false} formatter={(value: unknown) => [`${Number(value).toFixed(1)} pts`, "Delta"]} contentStyle={{ border: "1px solid #dedfd9", borderRadius: 8 }} />
                  <Bar dataKey="delta" radius={2} isAnimationActive animationDuration={220}>
                    {deltaData.map((entry, index) => (
                      <Cell key={index} fill={entry.delta >= 0 ? "#171817" : "#e75024"} />
                    ))}
                  </Bar>
                </BarChart>
              </div>
          </article>

          <article className="comparison-card scatter-card">
            <p className="card-kicker">Pool distribution: {xLabel} vs {yLabel}</p>
            <div className="chart-wrap">
                {allUnavailable ? (
                  <div className="chart-unavailable">
                    <p>Neither {selectedName} nor any match has both {xLabel} and {yLabel} values available in {mode} mode.</p>
                    <p style={{ fontSize: "0.75rem", marginTop: "0.5rem", color: "#6f716c" }}>Try Basic mode or adjust the comparison scope to see scatter data.</p>
                  </div>
                ) : (
                  <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 8 }} width={400} height={384}>
                    <XAxis type="number" dataKey="x" name={xLabel} tick={{ fontSize: 10, fill: "#6f716c" }} />
                    <YAxis type="number" dataKey="y" name={yLabel} tick={{ fontSize: 10, fill: "#6f716c" }} />
                    <ZAxis range={[40, 40]} />
                    <Tooltip isAnimationActive={false} cursor={{ strokeDasharray: "3 3" }} content={<ScatterTooltipContent xLabel={xLabel} yLabel={yLabel} />} />
                    <Scatter data={scatterPoints} fill="#171817" fillOpacity={0.4}>
                      {scatterPoints.map((point) => (
                        <ScatterMark key={point.id} point={point} intentOpen={requestOpen} intentIsOpen={isOpen} />
                      ))}
                    </Scatter>
                  </ScatterChart>
                )}
              </div>
          </article>
        </div>
      )}
    </div>
  );
}

export function ComparisonCharts(props: ComparisonChartsProps) {
  return (
    <TooltipIntentProvider>
      <RadixTooltipProvider>
        <ComparisonChartsContent {...props} />
      </RadixTooltipProvider>
    </TooltipIntentProvider>
  );
}
