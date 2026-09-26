import type { Comparison, ComparisonScope, EntityKind, FilterOptions, SearchResponse } from "./types";


const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(body?.detail ?? "The comparison service is unavailable.", response.status);
  }
  return response.json() as Promise<T>;
}

function scopeParams(scope?: ComparisonScope): URLSearchParams {
  const params = new URLSearchParams();
  if (scope?.season_from != null) params.set("season_from", String(scope.season_from));
  if (scope?.season_to != null) params.set("season_to", String(scope.season_to));
  if (scope?.team) params.set("team", scope.team);
  return params;
}

// The match pool narrows comparison candidates only; search ignores it.
function comparisonParams(scope: ComparisonScope): URLSearchParams {
  const params = scopeParams(scope);
  if (scope.pool && scope.pool !== "all") params.set("pool", scope.pool);
  return params;
}

export function loadFilterOptions(kind: EntityKind, signal?: AbortSignal): Promise<FilterOptions> {
  return request<FilterOptions>(`/api/${kind}s/filters`, signal);
}

export function searchHistory(
  kind: EntityKind,
  query: string,
  scope?: ComparisonScope,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const params = scopeParams(scope);
  params.set("q", query);
  return request<SearchResponse>(`/api/${kind}s/search?${params.toString()}`, signal);
}

export function loadComparison(
  kind: EntityKind,
  profileId: string,
  scope: ComparisonScope,
  signal?: AbortSignal,
): Promise<Comparison> {
  const params = comparisonParams(scope);
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<Comparison>(`/api/${kind}s/${encodeURIComponent(profileId)}/compare${query}`, signal);
}
