import { apiRequest } from "./client";
import type {
  PlanSummaryResponse,
  PlanTaskCreateResponse,
  TripPlanCreateRequest,
  TripPlanEditRequest,
  TripPlanResponse,
  TripPlanVersionResponse,
} from "./types";
import { useAuthStore } from "../store/auth";

export function createPlan(payload: TripPlanCreateRequest) {
  return apiRequest<PlanTaskCreateResponse>("/api/plans", {
    method: "POST",
    body: payload,
  });
}

export function parsePlan(text: string) {
  return apiRequest<TripPlanCreateRequest>("/api/plans/parse", {
    method: "POST",
    body: { text },
    // parsing doesn't require auth in current implementation
    auth: false,
  });
}

export function listPlans(params?: { search?: string; risk_level?: string }) {
  const query = new URLSearchParams();
  if (params?.search) {
    query.set("search", params.search);
  }
  if (params?.risk_level && params.risk_level !== "all") {
    query.set("risk_level", params.risk_level);
  }
  const path = `/api/plans${query.toString() ? `?${query.toString()}` : ""}`;
  return apiRequest<TripPlanResponse[]>(path);
}

export function getPlan(planId: number) {
  return apiRequest<TripPlanResponse>(`/api/plans/${planId}`);
}

export function deletePlan(planId: number) {
  return apiRequest<void>(`/api/plans/${planId}`, {
    method: "DELETE",
  });
}

export function getPlanSummary(planId: number) {
  return apiRequest<PlanSummaryResponse>(`/api/plans/${planId}/summary`);
}

export function listPlanVersions(planId: number) {
  return apiRequest<TripPlanVersionResponse[]>(`/api/plans/${planId}/versions`);
}

export function regeneratePlan(planId: number, versionId: number, payload: TripPlanCreateRequest) {
  return apiRequest<PlanTaskCreateResponse>(`/api/plans/${planId}/versions/${versionId}/regenerate`, {
    method: "POST",
    body: payload,
  });
}

export function editPlanVersion(planId: number, versionId: number, payload: TripPlanEditRequest) {
  return apiRequest<TripPlanVersionResponse>(`/api/plans/${planId}/versions/${versionId}`, {
    method: "PUT",
    body: payload,
  });
}

export function restorePlanVersion(planId: number, versionId: number) {
  return apiRequest<TripPlanVersionResponse>(`/api/plans/${planId}/versions/${versionId}/restore`, {
    method: "POST",
  });
}

export async function downloadPlanVersionPdf(planId: number, versionId: number) {
  const token = useAuthStore.getState().accessToken;
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"}/api/plans/${planId}/versions/${versionId}/export`, {
    method: "GET",
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    let errorMessage = response.statusText;
    try {
      const payload = JSON.parse(text);
      if (payload?.detail) {
        errorMessage = payload.detail;
      }
    } catch {
      if (text) {
        errorMessage = text;
      }
    }
    throw new Error(errorMessage || "PDF 导出失败");
  }

  return await response.blob();
}
