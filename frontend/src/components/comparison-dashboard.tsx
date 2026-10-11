"use client";

import { EntityAvatar } from "./entity-avatar";
import { SimilarityLeaderboard } from "./similarity-leaderboard";
import { ComparisonCharts } from "./comparison-charts";
import type { Comparison, EntityKind, RankedMatch } from "@/lib/types";


type ComparisonDashboardProps = {
  comparison: Comparison;
  kind: EntityKind;
  activeMatchId: string;
  onActiveMatchChange: (profileId: string) => void;
};

export function ComparisonDashboard({ comparison, kind, activeMatchId, onActiveMatchChange }: ComparisonDashboardProps) {
  const activeMatch: RankedMatch = comparison.matches.find(
    (m) => m.profile.id === activeMatchId
  ) ?? comparison.matches[0];

  const scoreTone = activeMatch.similarity_score >= 90
    ? "score-high"
    : activeMatch.similarity_score >= 80
      ? "score-medium"
      : "score-low";

  return (
    <section
      aria-label="Historical comparison result"
      className="comparison-result"
    >
      {/* Heading row */}
      <div className="comparison-heading">
        <div className="comparison-heading-info">
          <div className="avatar-name-row">
            <EntityAvatar entity={activeMatch.profile} size="large" />
            <div>
              <p className="eyebrow">Closest historical {kind} season</p>
              <h2>{activeMatch.profile.name}</h2>
              <p className="comparison-season">
                {activeMatch.profile.season}
                {activeMatch.profile.teams.length > 0 && (
                  <> · {activeMatch.profile.teams.map(t => t.name).join(", ")}</>
                )}
                {" "}— compared with {comparison.selected.name} ({comparison.selected.season})
              </p>
            </div>
          </div>
        </div>
        <div
          className={`score-lockup ${scoreTone}`}
          aria-label={`${activeMatch.similarity_score} out of 100 similarity`}
        >
          <span className="score-value">{activeMatch.similarity_score.toFixed(1)}</span>
          <span className="score-label">Similarity score</span>
        </div>
      </div>

      <div className="comparison-body">
        {/* Leaderboard */}
        <aside className="comparison-sidebar">
          <article className="comparison-card ranking-card">
            <p className="card-kicker">Power ranking</p>
            <p className="tier-name">{activeMatch.power_ranking.tier}</p>
            <p className="card-copy">
              Ranked #{activeMatch.power_ranking.rank} among {comparison.scope.eligible_count} eligible profiles using {comparison.features_used.length} verified measures.
            </p>
            <details className="measure-disclosure">
              <summary>Measures used for this score</summary>
              <ul>
                {comparison.features_used.map((feature) => <li key={feature}><code>{feature}</code></li>)}
              </ul>
              {kind === "team" && (
                <p>The selected season determines which recorded measures and profiles are eligible. Reversing this team comparison can change the score.</p>
              )}
            </details>
            <progress className="tier-progress" value={activeMatch.similarity_score} max={100}>
              {activeMatch.similarity_score}%
            </progress>
            <p className="tier-caption">90+ Mirror · 84+ Strong echo · 75+ Shared shape</p>
          </article>

          <SimilarityLeaderboard
            kind={kind}
            selectedId={activeMatchId}
            matches={comparison.matches}
            onSelect={onActiveMatchChange}
          />
        </aside>

        {/* Charts */}
        <ComparisonCharts
          kind={kind}
          selected={comparison.selected}
          activeMatch={activeMatch}
          matches={comparison.matches}
        />
      </div>
    </section>
  );
}
