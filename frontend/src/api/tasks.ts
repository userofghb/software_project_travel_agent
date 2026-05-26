import { apiRequest } from "./client";
import type { PlanTaskStatusResponse, TripPlanVersionResponse } from "./types";

export type TaskLogItem = {
  step: string;
  status: string;
  message: string;
  progress: number;
  timestamp: string;
};

export type TaskLogsResponse = {
  task_id: number;
  status: string;
  progress: number;
  logs: TaskLogItem[];
};

export function getTask(taskId: number) {
  return apiRequest<PlanTaskStatusResponse>(`/api/tasks/${taskId}`);
}

export function getTaskResult(taskId: number) {
  return apiRequest<TripPlanVersionResponse>(`/api/tasks/${taskId}/result`);
}

export function getTaskLogs(taskId: number) {
  return apiRequest<TaskLogsResponse>(`/api/tasks/${taskId}/logs`);
}
