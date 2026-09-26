"use client";

import type { ComparisonScope, EntityKind, FilterOptions, MatchPool } from "@/lib/types";


const POOL_LABELS: Record<EntityKind, Record<MatchPool, string>> = {
  player: { all: "Any player", others: "Other players only", same: "Same player only" },
  team: { all: "Any team", others: "Other teams only", same: "Same team only" },
};


type ComparisonFiltersProps = {
  kind: EntityKind;
  value: ComparisonScope;
  options: FilterOptions | null;
  onChange: (scope: ComparisonScope) => void;
  disabled: boolean;
  error?: string | null;
};

export function ComparisonFilters({ kind, value, options, onChange, disabled, error }: ComparisonFiltersProps) {
  function handleSeasonFrom(event: React.ChangeEvent<HTMLSelectElement>) {
    const raw = event.target.value;
    onChange({ ...value, season_from: raw ? Number(raw) : undefined });
  }

  function handleSeasonTo(event: React.ChangeEvent<HTMLSelectElement>) {
    const raw = event.target.value;
    onChange({ ...value, season_to: raw ? Number(raw) : undefined });
  }

  function handleTeam(event: React.ChangeEvent<HTMLSelectElement>) {
    const raw = event.target.value;
    onChange({ ...value, team: raw || undefined });
  }

  function handlePool(event: React.ChangeEvent<HTMLSelectElement>) {
    onChange({ ...value, pool: event.target.value as MatchPool });
  }

  const seasons = options?.seasons ?? [];
  const teams = options?.teams ?? [];
  const showTeamFilter = kind === "player" && (options?.team_filter_available ?? false);

  return (
    <fieldset className="filter-controls" disabled={disabled || !options} aria-busy={!options && !error}>
      <legend>Comparison pool</legend>

      {!options && !error && <>
        <span role="status" className="filter-status">Loading comparison filters…</span>
        <span className="filter-skeleton" aria-hidden="true" />
        <span className="filter-skeleton" aria-hidden="true" />
      </>}
      {error && <span role="alert" className="filter-error">{error}</span>}

      <div className="filter-row">
        <label htmlFor="filter-season-from" className="filter-label">From season</label>
        <select
          id="filter-season-from"
          className="filter-select"
          value={value.season_from ?? ""}
          onChange={handleSeasonFrom}
        >
          <option value="">All history</option>
          {seasons.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="filter-row">
        <label htmlFor="filter-season-to" className="filter-label">To season</label>
        <select
          id="filter-season-to"
          className="filter-select"
          value={value.season_to ?? ""}
          onChange={handleSeasonTo}
        >
          <option value="">All history</option>
          {seasons.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {showTeamFilter && (
        <div className="filter-row">
          <label htmlFor="filter-team" className="filter-label">Team</label>
          <select
            id="filter-team"
            className="filter-select"
            value={value.team ?? ""}
            onChange={handleTeam}
          >
            <option value="">All teams</option>
            {teams.map((t) => (
              <option key={t.code} value={t.code}>{t.name}</option>
            ))}
          </select>
        </div>
      )}

      <div className="filter-row">
        <label htmlFor="filter-pool" className="filter-label">Matches</label>
        <select
          id="filter-pool"
          className="filter-select"
          value={value.pool ?? "all"}
          onChange={handlePool}
        >
          {(Object.entries(POOL_LABELS[kind]) as [MatchPool, string][]).map(([pool, label]) => (
            <option key={pool} value={pool}>{label}</option>
          ))}
        </select>
      </div>
    </fieldset>
  );
}
