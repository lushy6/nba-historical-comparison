"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { ComparisonMetric } from "@/lib/types";


type PlayerRadarProps = {
  metrics: ComparisonMetric[];
  selectedName: string;
  matchName: string;
};

export function PlayerRadar({ metrics, selectedName, matchName }: PlayerRadarProps) {
  if (metrics.length === 0) {
    return (
      <article className="comparison-card radar-card" aria-label="Player stat radar unavailable">
        <p className="card-kicker">Twelve-stat profile</p>
        <p className="card-copy">The selected database release does not expose enough complete player measures for a radar profile.</p>
      </article>
    );
  }

  const data = metrics.map((metric) => ({
    label: metric.label,
    selected: metric.selected_normalized,
    match: metric.match_normalized,
    selectedRaw: metric.selected_value,
    matchRaw: metric.match_value,
  }));

  return (
    <article className="comparison-card radar-card">
      <div className="card-title-row">
        <p className="card-kicker">Twelve-stat profile</p>
        <div className="chart-legend" aria-label="Radar chart legend">
          <span><i className="legend-selected" />{selectedName}</span>
          <span><i className="legend-match" />{matchName}</span>
        </div>
      </div>
      <div className="radar-wrap" role="img" aria-label={`Radar comparison of ${selectedName} and ${matchName} across twelve primary statistics`}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="67%">
            <PolarGrid stroke="#dedfd9" />
            <PolarAngleAxis dataKey="label" tick={{ fill: "#6f716c", fontSize: 10 }} />
            <Tooltip
              contentStyle={{ border: "1px solid #dedfd9", borderRadius: 8, boxShadow: "0 8px 24px rgba(23,24,23,.08)" }}
              formatter={(value, key, item) => [
                Number(key === "selected" ? item.payload.selectedRaw : item.payload.matchRaw).toFixed(1),
                key === "selected" ? selectedName : matchName,
              ]}
            />
            <Radar dataKey="selected" stroke="#e75024" fill="#e75024" fillOpacity={0.15} strokeWidth={2} />
            <Radar dataKey="match" stroke="#171817" fill="#171817" fillOpacity={0.05} strokeWidth={1.5} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </article>
  );
}
