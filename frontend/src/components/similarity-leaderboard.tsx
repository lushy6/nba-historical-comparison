"use client";

import { EntityAvatar } from "./entity-avatar";
import type { EntityKind, RankedMatch } from "@/lib/types";


type SimilarityLeaderboardProps = {
  kind: EntityKind;
  selectedId: string;
  matches: RankedMatch[];
  onSelect: (profileId: string) => void;
};

export function SimilarityLeaderboard({ kind, selectedId, matches, onSelect }: SimilarityLeaderboardProps) {
  if (matches.length === 0) return null;

  return (
    <nav aria-label="Top matches leaderboard" className="leaderboard">
      <p className="leaderboard-heading">Top {matches.length} historical matches</p>
      <ol className="leaderboard-list">
        {matches.map((match) => {
          const isActive = match.profile.id === selectedId;
          return (
            <li key={match.profile.id}>
              <button
                type="button"
                className={`leaderboard-row${isActive ? " is-active" : ""}`}
                aria-current={isActive ? "true" : undefined}
                onClick={() => onSelect(match.profile.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(match.profile.id);
                  }
                }}
              >
                <span className="lb-rank" aria-label={`Rank ${match.power_ranking.rank}`}>
                  {match.power_ranking.rank}
                </span>
                <EntityAvatar entity={match.profile} size="small" decorative />
                <span className="lb-info">
                  <span className="lb-name">{match.profile.name}</span>
                  <span className="lb-meta">
                    {match.profile.season}
                    {match.profile.teams.length > 0 && ` · ${match.profile.teams.map(t => t.code).join(", ")}`}
                  </span>
                </span>
                <span className="lb-right">
                  <span className="lb-tier">{match.power_ranking.tier}</span>
                  <span className="lb-score">{match.similarity_score.toFixed(1)}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
