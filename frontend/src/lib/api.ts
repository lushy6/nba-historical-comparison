import type { Comparison, EntityKind, SearchResponse } from "./types";


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

export function searchHistory(kind: EntityKind, query: string, signal?: AbortSignal) {
  return request<SearchResponse>(`/api/${kind}s/search?q=${encodeURIComponent(query)}`, signal);
}

export function loadComparison(kind: EntityKind, profileId: string, signal?: AbortSignal) {
  return request<Comparison>(`/api/${kind}s/${encodeURIComponent(profileId)}/compare`, signal);
}
