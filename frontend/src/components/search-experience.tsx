"use client";

import * as Popover from "@radix-ui/react-popover";
import { useEffect, useRef, useState } from "react";

import { ApiError, loadComparison, loadFilterOptions, searchHistory } from "@/lib/api";
import type { Comparison, ComparisonScope, EntityKind, FilterOptions, SearchItem } from "@/lib/types";

import { ComparisonDashboard } from "./comparison-dashboard";
import { ComparisonFilters } from "./comparison-filters";
import { EntityAvatar } from "./entity-avatar";


export function SearchExperience() {
  const [kind, setKind] = useState<EntityKind>("player");
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<ComparisonScope>({});
  const [items, setItems] = useState<SearchItem[]>([]);
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);
  const [filterError, setFilterError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingComparison, setIsLoadingComparison] = useState(false);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [activeMatchId, setActiveMatchId] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<SearchItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const comparisonRequest = useRef<AbortController | null>(null);
  const searchRequest = useRef<AbortController | null>(null);
  const visibleItems = query.trim().length >= 2 ? items.slice(0, 15) : [];

  useEffect(() => () => {
    comparisonRequest.current?.abort();
  }, []);

  // Load filter options whenever kind changes
  useEffect(() => {
    const controller = new AbortController();
    loadFilterOptions(kind, controller.signal)
      .then((opts) => {
        if (!controller.signal.aborted) setFilterOptions(opts);
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted && (err as Error).name !== "AbortError") {
          setFilterError("Comparison filters could not load. Try switching comparison type to retry.");
        }
      });
    return () => controller.abort();
  }, [kind]);

  // Search with debounce, scoped by seasons and team. The match pool only narrows
  // comparison candidates, so changing it must not re-run the search.
  const { season_from: seasonFrom, season_to: seasonTo, team } = scope;
  useEffect(() => {
    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 2) return;

    const controller = new AbortController();
    searchRequest.current = controller;
    const timer = window.setTimeout(() => {
      if (controller.signal.aborted) return;
      setIsSearching(true);
      setError(null);
      searchHistory(kind, trimmedQuery, { season_from: seasonFrom, season_to: seasonTo, team }, controller.signal)
        .then((response) => {
          if (!controller.signal.aborted) setItems(response.items.slice(0, 15));
        })
        .catch((requestError: unknown) => {
          if (!controller.signal.aborted && (requestError as Error).name !== "AbortError") {
            setItems([]);
            setError(messageForError(requestError));
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsSearching(false);
        });
    }, 160);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [kind, query, seasonFrom, seasonTo, team]);

  function cancelRequests() {
    comparisonRequest.current?.abort();
    searchRequest.current?.abort();
    setIsLoadingComparison(false);
    setIsSearching(false);
    setItems([]);
  }

  async function selectItem(item: SearchItem, comparisonScope: ComparisonScope = scope) {
    cancelRequests();
    setSelectedItem(item);
    const controller = new AbortController();
    comparisonRequest.current = controller;
    setError(null);
    setIsLoadingComparison(true);
    try {
      const result = await loadComparison(item.kind, item.id, comparisonScope, controller.signal);
      if (controller.signal.aborted) return;
      setComparison({ ...result, matches: result.matches.slice(0, 15) });
      setActiveMatchId(result.matches[0]?.profile.id ?? null);
    } catch (requestError) {
      if (controller.signal.aborted) return;
      setComparison(null);
      setActiveMatchId(null);
      setError(messageForError(requestError));
    } finally {
      if (!controller.signal.aborted) setIsLoadingComparison(false);
    }
  }

  function switchKind(nextKind: EntityKind) {
    if (nextKind === kind) return;
    cancelRequests();
    setKind(nextKind);
    setScope({});
    setSelectedItem(null);
    setFilterOptions(null);
    setFilterError(null);
    setComparison(null);
    setActiveMatchId(null);
    setQuery("");
    setError(null);
  }

  function handleScopeChange(nextScope: ComparisonScope) {
    const searchScopeUnchanged = nextScope.season_from === scope.season_from && nextScope.season_to === scope.season_to && nextScope.team === scope.team;
    if (searchScopeUnchanged) {
      if ((nextScope.pool ?? "all") === (scope.pool ?? "all")) return;
      // Only the match pool changed: re-rank the same selection in place.
      setScope(nextScope);
      if (selectedItem) void selectItem(selectedItem, nextScope);
      return;
    }
    cancelRequests();
    setScope(nextScope);
    setSelectedItem(null);
    setComparison(null);
    setActiveMatchId(null);
    setError(null);
  }

  return (
    <main className="page-shell">
      <nav aria-label="Primary" className="site-nav">
        <a className="wordmark" href="#search">
          <span aria-hidden="true" className="wordmark-mark">SE</span>
          <span>Season Echoes</span>
        </a>
        <p className="nav-note">NBA historical comparison</p>
      </nav>

      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">A different kind of comparison</p>
        <h1 id="page-title">Find the season that echoes today.</h1>
        <p className="hero-copy">
          Search a player or a team. We trace the statistical shape of their season through NBA history-pace, efficiency, volume, and the details in between.
        </p>

        <div className="mode-switch" role="group" aria-label="Comparison type">
          {(["player", "team"] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={kind === option}
              className={kind === option ? "mode-button is-active" : "mode-button"}
              onClick={() => switchKind(option)}
            >
              {option === "player" ? "Players" : "Teams"}
            </button>
          ))}
        </div>

        <Popover.Root open={visibleItems.length > 0}>
          <Popover.Anchor asChild>
            <form id="search" className="search-frame" role="search" onSubmit={(event) => event.preventDefault()}>
              <label className="sr-only" htmlFor="nba-history-search">Search NBA history</label>
              <svg aria-hidden="true" className="search-icon" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.25 4.25" /></svg>
              <input
                id="nba-history-search"
                className="search-input"
                name="q"
                type="search"
                placeholder={`Search ${kind}s across NBA history`}
                autoComplete="off"
                value={query}
                onChange={(event) => {
                  const nextQuery = event.target.value;
                  setQuery(nextQuery);
                  if (nextQuery.trim().length < 2) {
                    setItems([]);
                    setError(null);
                    setIsSearching(false);
                  }
                }}
              />
              <span className="search-status" aria-live="polite">{isSearching ? "Searching" : kind}</span>
            </form>
          </Popover.Anchor>
          <Popover.Portal>
            <Popover.Content
              className="search-results"
              side="bottom"
              align="start"
              sideOffset={8}
              onOpenAutoFocus={(event) => event.preventDefault()}
            >
              <p className="results-label">Choose a {kind} season</p>
              {visibleItems.map((item) => (
                <button key={item.id} type="button" className="result-option" onClick={() => void selectItem(item)}>
                  <EntityAvatar entity={item} size="small" decorative />
                  <span className="result-context">
                    <span>{item.name}</span>
                    <small>{item.season}{item.teams.length > 0 && ` · ${item.teams.map((team) => team.name).join(", ")}`}</small>
                  </span>
                </button>
              ))}
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>

        <ComparisonFilters
          kind={kind}
          value={scope}
          options={filterOptions}
          onChange={handleScopeChange}
          disabled={false}
          error={filterError}
        />

        <p className="search-caption">Powered by your local NBA historical database. No scores are guessed.</p>

          {isLoadingComparison ? (
            <div className="comparison-loading" role="status">Measuring the historical shape.</div>
          ) : error ? (
            <ErrorResult key="error" message={error} />
          ) : comparison && activeMatchId ? (
            <ComparisonDashboard
              key={comparison.selected.id}
              comparison={comparison}
              kind={kind}
              activeMatchId={activeMatchId}
              onActiveMatchChange={(id) => {
                if (comparison.matches.some((match) => match.profile.id === id)) setActiveMatchId(id);
              }}
            />
          ) : null}
      </section>

      <aside className="method-note" aria-label="Comparison methodology">
        <span className="method-rule" aria-hidden="true" />
        <p><strong>How it works</strong><span>Stat profiles are standardized before we measure the nearest historical shape.</span></p>
      </aside>
    </main>
  );
}

function ErrorResult({ message }: { message: string }) {
  return <div className="comparison-error" role="alert">{message}</div>;
}

function messageForError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "We could not reach the comparison service. Start the FastAPI backend and try again.";
}
