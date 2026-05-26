import type { TripPlanResponse, TripPlanVersionResponse } from "../api/types";

type PlanContent = {
  title?: string;
  city?: string;
  start_date?: string;
  end_date?: string;
  days?: Array<{
    date: string;
    theme?: string;
    weather_suggestion?: string;
    activities?: Array<{
      time?: string;
      type?: string;
      title?: string;
      reason?: string;
      duration?: string;
      budget?: number;
      tags?: string[];
      transport?: string;
    }>;
  }>;
  map?: {
    points?: Array<{
      id?: string | number | null;
      name?: string | null;
      type?: string | null;
      address?: string | null;
      location?: {
        lng?: number | string | null;
        lat?: number | string | null;
      } | null;
    }>;
    routes?: Array<{
      day?: string | number | null;
      from?: string | null;
      to?: string | null;
      mode?: string | null;
      distance_m?: number | null;
      duration_s?: number | null;
      polyline?: string | null;
      source?: string | null;
    }>;
  };
  budget?: {
    range?: string;
    estimated_total?: number;
    breakdown?: Array<{ key?: string; name: string; value: number }>;
  };
  hotel?: {
    name?: string;
    location?: string;
    price_per_night?: number;
  };
  overall_suggestions?: string[];
};

export function getCurrentVersion(plan: TripPlanResponse): TripPlanVersionResponse | null {
  return plan.current_version ?? null;
}

export function getPlanContent(plan: TripPlanResponse): PlanContent {
  return (plan.current_version?.content_json ?? {}) as PlanContent;
}
