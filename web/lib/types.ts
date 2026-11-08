// Shapes returned by the FloatChat API (api/main.py).

export type Filters = {
  region?: string;
  month_num?: number;
  year?: number;
  has_oxygen?: boolean;
  has_chlorophyll?: boolean;
  has_nitrate?: boolean;
  has_ph?: boolean;
};

export type Stats = {
  floats: number;
  profiles: number;
  measurements: number;
  bgc_floats: number;
  chlorophyll_floats: number;
  nitrate_floats: number;
  ph_floats: number;
  start_date: string;
  end_date: string;
  max_depth: number;
  last_updated: string;
  regions: { region: string; profiles: number }[];
};

export type FloatPoint = {
  float_id: string;
  last_profile: string;
  lat: number;
  lon: number;
  region: string;
  n_profiles: number;
  surface_temperature: number | null;
  surface_salinity: number | null;
  is_bgc: boolean;
};

export type FloatDetail = {
  float_info: {
    float_id: string;
    wmo_id: number;
    deployment_date: string | null;
    deployment_lat: number | null;
    deployment_lon: number | null;
    last_contact: string | null;
    status: string | null;
  };
  profile_summary: { total_profiles: number; first_profile: string; last_profile: string; active_days: number };
  measurement_summary: {
    total_measurements: number;
    min_depth: number;
    max_depth: number;
    avg_temp: number | null;
    avg_sal: number | null;
  };
};

export type TrackPoint = {
  profile_id: number;
  float_id: string;
  cycle_number: number;
  profile_date: string;
  profile_lat: number;
  profile_lon: number;
  region: string;
  n_levels: number;
  has_oxygen: boolean;
  has_chlorophyll: boolean;
  has_nitrate: boolean;
  has_ph: boolean;
  avg_temp: number | null;
  avg_sal: number | null;
  min_depth: number;
  max_depth: number;
};

export type Measurement = {
  id: number;
  time: string;
  lat: number;
  lon: number;
  depth: number;
  temperature: number | null;
  salinity: number | null;
  oxygen: number | null;
  chlorophyll: number | null;
  nitrate: number | null;
  ph: number | null;
  float_id: string;
  profile_id: number;
  cycle_number: number;
  region: string;
};

export type ProfileMatch = {
  profile_id: number;
  float_id: string;
  cycle_number: number;
  date: string;
  year: number;
  month_num: number;
  lat: number;
  lon: number;
  region: string;
  has_oxygen: boolean;
  has_chlorophyll: boolean;
  has_nitrate: boolean;
  has_ph: boolean;
};

// Step events emitted while an answer is worked out (floatchat/answer.py, sql_agent.py)
export type UnderstoodStep = {
  step: "understood";
  path: "analytical" | "semantic";
  intent: string | null;
  filters: Filters;
  question: string;
  router: "llm" | "keywords";
};
export type SqlStep = {
  step: "sql";
  attempt: number;
  sql: string;
  params?: Record<string, unknown>;
  status: "success" | "empty" | "error";
  rows?: number;
  ms?: number;
};
export type SearchStep = {
  step: "search";
  matches: number;
  filters: Filters;
  fallback_without_filters: boolean;
};
export type AnswerStep = { step: "answer"; llm_used: boolean };
export type Step = UnderstoodStep | SqlStep | SearchStep | AnswerStep;

export type QueryResult = {
  answer: string;
  query_type: "analytical" | "semantic" | "error";
  context_documents: string[];
  retrieved_metadata: Record<string, unknown>[];
  sql_results: Record<string, unknown>[] | null;
  intent: string | null;
  filters: Filters;
  steps: Step[];
};

export type HistoryTurn = { question: string; query_type: string | null; intent: string | null; filters: Filters };

export type Benchmark = {
  ran_at: string;
  summary: {
    cases: number;
    passed: number;
    routing_accuracy: number;
    filter_accuracy: number;
    answer_pass_rate: number;
    median_latency_ms: number | null;
    llm_routed: number;
    llm_wrote_answer: number;
  };
};
