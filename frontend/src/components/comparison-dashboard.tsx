"use client";

import { motion, useReducedMotion } from "framer-motion";

import type { Comparison, ComparisonMetric, EntityKind } from "@/lib/types";

import { PlayerRadar } from "./player-radar";


type ComparisonDashboardProps = {
  comparison: Comparison;
  kind: EntityKind;
};

function metricsFor(comparison: Comparison): ComparisonMetric[] {
  return "radar" in comparison ? comparison.radar : comparison.metrics;
}

export function ComparisonDashboard({ comparison, kind }: ComparisonDashboardProps) {
  const reducedMotion = useReducedMotion();
  const metrics = metricsFor(comparison);
  const scoreTone = comparison.similarity_score >= 90
    ? "score-high"
    : comparison.similarity_score >= 80
      ? "score-medium"
      : "score-low";

  return (
    <motion.section
      aria-label="Historical comparison result"
      className="comparison-result"
      initial={reducedMotion ? { opacity: 0 } : { opacity: 0, transform: "translateY(12px)" }}
      animate={{ opacity: 1, transform: "translateY(0px)" }}
      transition={{ duration: 0.24, ease: [0.23, 1, 0.32, 1] }}
    >
      <div className="comparison-heading">
        <div>
          <p className="eyebrow">Closest historical {kind} season</p>
          <h2>{comparison.match.name}</h2>
          <p className="comparison-season">{comparison.match.season} · compared with {comparison.selected.name} ({comparison.selected.season})</p>
        </div>
        <div className={`score-lockup ${scoreTone}`} aria-label={`${comparison.similarity_score} out of 100 similarity`}>
          <span className="score-value">{comparison.similarity_score.toFixed(1)}</span>
          <span className="score-label">Similarity score</span>
        </div>
      </div>

      <div className="comparison-grid">
        <article className="comparison-card ranking-card">
          <p className="card-kicker">Power ranking</p>
          <p className="tier-name">{comparison.power_ranking.tier}</p>
          <p className="card-copy">Ranked #{comparison.power_ranking.rank} among eligible historical profiles using {comparison.features_used.length} verified measures.</p>
          <progress className="tier-progress" value={comparison.similarity_score} max={100}>
            {comparison.similarity_score}%
          </progress>
          <p className="tier-caption">90+ Mirror · 84+ Strong echo · 75+ Shared shape</p>
        </article>

        {kind === "player" ? (
          <PlayerRadar metrics={metrics} selectedName={comparison.selected.name} matchName={comparison.match.name} />
        ) : (
          <article className="comparison-card metric-card">
            <p className="card-kicker">Team profile</p>
            <dl className="metric-list">
              {metrics.map((metric) => (
                <div key={metric.metric}>
                  <dt>{metric.label}</dt>
                  <dd>
                    <span>{formatMetric(metric.selected_value, metric.metric)}</span>
                    <span>{formatMetric(metric.match_value, metric.metric)}</span>
                  </dd>
                </div>
              ))}
            </dl>
          </article>
        )}
      </div>
    </motion.section>
  );
}

function formatMetric(value: number, metric: string): string {
  if (metric.endsWith("pct") || metric.endsWith("rate")) return `${(value * 100).toFixed(1)}%`;
  return value.toFixed(1);
}
