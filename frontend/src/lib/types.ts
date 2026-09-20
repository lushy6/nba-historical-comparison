export type EntityKind = "player" | "team";

export type SearchItem = {
  id: string;
  name: string;
  season: string;
  kind: EntityKind;
};

export type SearchResponse = { items: SearchItem[] };

export type Profile = {
  id: string;
  name: string;
  season: string;
};

export type ComparisonMetric = {
  metric: string;
  label: string;
  selected_value: number;
  match_value: number;
  selected_normalized: number;
  match_normalized: number;
};

type ComparisonBase = {
  selected: Profile;
  match: Profile;
  similarity_score: number;
  power_ranking: { rank: number; tier: string };
  features_used: string[];
};

export type PlayerComparison = ComparisonBase & { radar: ComparisonMetric[] };
export type TeamComparison = ComparisonBase & { metrics: ComparisonMetric[] };
export type Comparison = PlayerComparison | TeamComparison;
