"use client";

import type { ComparisonScope, EntityKind, FilterOptions } from "@/lib/types";


type ComparisonFiltersProps = {
  kind: EntityKind;
  value: ComparisonScope;
  options: FilterOptions | null;
  onChange: (scope: ComparisonScope) => void;
  disabled: boolean;
};

export function ComparisonFilters({ kind, value, options, onChange, disabled }: ComparisonFiltersProps) {
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

  const seasons = options?.seasons ?? [];
  const teams = options?.teams ?? [];
  const showTeamFilter = kind === "player" && (options?.team_filter_available ?? false);

  return (
    <fieldset className="filter-controls" disabled={disabled || !options}>
      <legend>Comparison pool</legend>

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
    </fieldset>
  );
}
