import { apiRequest } from "./client";
import type { AccountUpdateRequest, LoginRequest, RegisterRequest, TokenResponse, UserMeResponse } from "./types";

export function login(payload: LoginRequest) {
  return apiRequest<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: payload,
    auth: false,
  });
}

export function register(payload: RegisterRequest) {
  return apiRequest<UserMeResponse>("/api/auth/register", {
    method: "POST",
    body: payload,
    auth: false,
  });
}

export function fetchMe(token?: string) {
  return apiRequest<UserMeResponse>("/api/auth/me", {
    token,
  });
}

export function updateMe(payload: AccountUpdateRequest) {
  return apiRequest<UserMeResponse>("/api/auth/me", {
    method: "PUT",
    body: payload,
  });
}
