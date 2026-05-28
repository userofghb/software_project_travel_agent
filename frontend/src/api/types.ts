import type { components } from "../types/generated/schema";

export type LoginRequest = components["schemas"]["LoginRequest"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type UserMeResponse = components["schemas"]["UserMeResponse"];
export type UserProfileResponse = components["schemas"]["UserProfileResponse"];
export type UserProfileUpdateRequest = components["schemas"]["UserProfileUpdateRequest"];
export type TripPlanCreateRequest = components["schemas"]["TripPlanCreateRequest"];
export type TripPlanEditRequest = components["schemas"]["TripPlanEditRequest"];
export type TripPlanResponse = components["schemas"]["TripPlanResponse"];
export type TripPlanVersionResponse = components["schemas"]["TripPlanVersionResponse"];
export type PlanTaskCreateResponse = components["schemas"]["PlanTaskCreateResponse"];
export type PlanTaskStatusResponse = components["schemas"]["PlanTaskStatusResponse"];
export type WeatherWarningResponse = components["schemas"]["WeatherWarningResponse"];

export type PlanSummaryResponse = {
  plan_id: number;
  title: string;
  origin: string | null;
  city: string;
  start_date: string;
  end_date: string;
  budget_range: string;
  current_version_id: number;
  current_version_no: number;
  estimated_total: number | null;
  risk_level: string;
  pace: string;
  warning_count: number;
  updated_at: string;
};
