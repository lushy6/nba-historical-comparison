export type EntityKind = "player" | "team";

export type SearchItem = Profile & {
  kind: EntityKind;
};

export type SearchResponse = { items: SearchItem[] };

export type VisualIdentity = {
  kind: EntityKind;
  nba_id: string | null;
  image_url: string | null;
};

export type TeamContext = {
  code: string;
  name: string;
};

export type Profile = {
  id: string;
  name: string;
  season: string;
  teams: TeamContext[];
  visual: VisualIdentity;
};

export type ComparisonMetric = {
  metric: string;
  label: string;
  selected_value: number;
  match_value: number;
  selected_normalized: number;
  match_normalized: number;
};

export type MetricGroups = {
  basic: ComparisonMetric[];
  advanced: ComparisonMetric[];
};

export type PowerRanking = {
  rank: number;
  tier: string;
};

export type RankedMatch = {
  profile: Profile;
  similarity_score: number;
  power_ranking: PowerRanking;
  metrics: MetricGroups;
};

export type ComparisonScope = {
  season_from?: number;
  season_to?: number;
  team?: string;
};

export type AppliedScope = {
  season_from: number | null;
  season_to: number | null;
  team: string | null;
  eligible_count: number;
};

export type FilterOptions = {
  seasons: number[];
  teams: TeamContext[];
  team_filter_available: boolean;
};

export type Comparison = {
  selected: Profile;
  match: RankedMatch;
  matches: RankedMatch[];
  scope: AppliedScope;
  features_used: string[];
};

// Legacy aliases kept for backward compatibility
export type PlayerComparison = Comparison;
export type TeamComparison = Comparison;
