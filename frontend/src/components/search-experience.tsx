"use client";

import * as Popover from "@radix-ui/react-popover";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";

import { ApiError, loadComparison, loadFilterOptions, searchHistory } from "@/lib/api";
import type { Comparison, ComparisonScope, EntityKind, FilterOptions, SearchItem } from "@/lib/types";

import { ComparisonDashboard } from "./comparison-dashboard";
import { ComparisonFilters } from "./comparison-filters";


export function SearchExperience() {
  const reducedMotion = useReducedMotion();
  const [kind, setKind] = useState<EntityKind>("player");
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<ComparisonScope>({});
  const [items, setItems] = useState<SearchItem[]>([]);
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingComparison, setIsLoadingComparison] = useState(false);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [activeMatchId, setActiveMatchId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const visibleItems = query.trim().length >= 2 ? items : [];

  // Load filter options whenever kind changes
  useEffect(() => {
    const controller = new AbortController();
    loadFilterOptions(kind, controller.signal)
      .then((opts) => {
        setFilterOptions(opts);
      })
      .catch((err: unknown) => {
        if ((err as Error).name !== "AbortError") {
          setFilterOptions({ seasons: [], teams: [], team_filter_available: false });
        }
      });
    return () => controller.abort();
  }, [kind]);

  // Search with debounce, including scope
  useEffect(() => {
    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 2) return;

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setIsSearching(true);
      setError(null);
      searchHistory(kind, trimmedQuery, scope, controller.signal)
        .then((response) => setItems(response.items))
        .catch((requestError: unknown) => {
          if ((requestError as Error).name !== "AbortError") {
            setItems([]);
            setError(messageForError(requestError));
          }
        })
        .finally(() => setIsSearching(false));
    }, 160);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [kind, query, scope]);

  const selectItem = useCallback(async (item: SearchItem) => {
    setItems([]);
    setError(null);
    setIsLoadingComparison(true);
    try {
      const result = await loadComparison(item.kind, item.id, scope);
      setComparison(result);
      setActiveMatchId(result.matches[0]?.profile.id ?? null);
    } catch (requestError) {
      setComparison(null);
      setActiveMatchId(null);
      setError(messageForError(requestError));
    } finally {
      setIsLoadingComparison(false);
    }
  }, [scope]);

  function switchKind(nextKind: EntityKind) {
    setKind(nextKind);
    setScope({});
    setFilterOptions(null);
    setComparison(null);
    setActiveMatchId(null);
    setItems([]);
    setQuery("");
    setError(null);
  }

  function handleScopeChange(nextScope: ComparisonScope) {
    setScope(nextScope);
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
                  <span>{item.name}</span>
                  <small>{item.season}</small>
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
          disabled={isLoadingComparison}
        />

        <p className="search-caption">Powered by your local NBA historical database. No scores are guessed.</p>

        <AnimatePresence mode="wait">
          {isLoadingComparison ? (
            <LoadingResult key="loading" reducedMotion={Boolean(reducedMotion)} />
          ) : error ? (
            <ErrorResult key="error" message={error} />
          ) : comparison && activeMatchId ? (
            <ComparisonDashboard
              key={comparison.selected.id}
              comparison={comparison}
              kind={kind}
              activeMatchId={activeMatchId}
              onActiveMatchChange={setActiveMatchId}
            />
          ) : null}
        </AnimatePresence>
      </section>

      <aside className="method-note" aria-label="Comparison methodology">
        <span className="method-rule" aria-hidden="true" />
        <p><strong>How it works</strong><span>Stat profiles are standardized before we measure the nearest historical shape.</span></p>
      </aside>
    </main>
  );
}

function LoadingResult({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <motion.div
      aria-live="polite"
      className="comparison-loading"
      initial={reducedMotion ? { opacity: 0 } : { opacity: 0, transform: "translateY(6px)" }}
      animate={{ opacity: 1, transform: "translateY(0px)" }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
    >
      Measuring the historical shape.
    </motion.div>
  );
}

function ErrorResult({ message }: { message: string }) {
  return <div className="comparison-error" role="alert">{message}</div>;
}

function messageForError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "We could not reach the comparison service. Start the FastAPI backend and try again.";
}