// ── Types ─────────────────────────────────────────────────────────────────────

export type MatchStatus = "scheduled" | "live" | "finished" | "cancelled";
export type PredictedOutcome = "home_win" | "away_win" | "draw";

export interface TeamRead {
  id: number;
  name: string;
  country_code: string;
  group_name: string;
  flag_url: string | null;
  fifa_ranking: number;
  elo_rating: number;
  recent_form_score: number;
  goals_for: number;
  goals_against: number;
  wins: number;
  draws: number;
  losses: number;
  extra_stats: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface MatchRead {
  id: number;
  external_id: string | null;
  home_team_id: number;
  away_team_id: number;
  kickoff_at: string;
  status: MatchStatus;
  stage: string;
  venue: string | null;
  home_score: number | null;
  away_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ModelPrediction {
  match_id: number;
  home_team: TeamRead;
  away_team: TeamRead;
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  predicted_outcome: PredictedOutcome;
  confidence: number;
  explanation: string;
  model_version: string;
}

export interface PredictionSummary {
  match_id: number;
  total_predictions: number;
  home_win_count: number;
  draw_count: number;
  away_win_count: number;
  home_win_percentage: number;
  draw_percentage: number;
  away_win_percentage: number;
}

export interface PredictionSubmitRequest {
  session_id: string;
  predicted_outcome: PredictedOutcome;
  predicted_home_score?: number | null;
  predicted_away_score?: number | null;
}

export interface PredictionRead {
  id: number;
  match_id: number;
  session_id: string;
  predicted_outcome: PredictedOutcome;
  predicted_home_score: number | null;
  predicted_away_score: number | null;
  created_at: string;
}

export interface PredictionSubmitResponse {
  prediction: PredictionRead;
  summary: PredictionSummary;
}

// ── Client ────────────────────────────────────────────────────────────────────

function getBase(): string {
  // API_URL is a server-only env var for Docker internal routing (http://backend:8000).
  // NEXT_PUBLIC_API_URL is used when API_URL is absent (local dev + client components).
  return (
    process.env.API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000"
  );
}

class ApiError extends Error {
  constructor(
    public status: number,
    public path: string,
  ) {
    super(`API ${status}: ${path}`);
  }
}

async function get<T>(
  path: string,
  init?: RequestInit & { next?: { revalidate?: number } },
): Promise<T> {
  const res = await fetch(`${getBase()}${path}`, init);
  if (!res.ok) throw new ApiError(res.status, path);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${getBase()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, path);
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

// ── API surface ───────────────────────────────────────────────────────────────

export const api = {
  teams: {
    list(opts: { limit?: number; offset?: number } = {}): Promise<Page<TeamRead>> {
      return get(`/api/v1/teams${qs(opts)}`, { next: { revalidate: 600 } });
    },
    get(id: number): Promise<TeamRead> {
      return get(`/api/v1/teams/${id}`, { next: { revalidate: 600 } });
    },
  },

  matches: {
    list(
      opts: {
        limit?: number;
        offset?: number;
        status?: MatchStatus;
        stage?: string;
        team_id?: number;
      } = {},
    ): Promise<Page<MatchRead>> {
      return get(`/api/v1/matches${qs(opts)}`, { next: { revalidate: 30 } });
    },
    get(id: number): Promise<MatchRead> {
      return get(`/api/v1/matches/${id}`, { next: { revalidate: 30 } });
    },
    modelPrediction(id: number): Promise<ModelPrediction> {
      return get(`/api/v1/matches/${id}/model-prediction`, {
        next: { revalidate: 300 },
      });
    },
    predictionSummary(id: number): Promise<PredictionSummary> {
      return get(`/api/v1/matches/${id}/prediction-summary`, {
        next: { revalidate: 30 },
      });
    },
    submitPrediction(
      id: number,
      body: PredictionSubmitRequest,
    ): Promise<PredictionSubmitResponse> {
      return post(`/api/v1/matches/${id}/predictions`, body);
    },
  },
};

export { ApiError };
