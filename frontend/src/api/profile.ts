import { apiRequest } from "./client";
import type { UserProfileResponse, UserProfileUpdateRequest } from "./types";

export type InterestTagsResponse = {
  user_id: number;
  interest_tags: string[];
  profile_summary: string;
  updated_at: string;
};

export function fetchMyProfile() {
  return apiRequest<UserProfileResponse>("/api/profile/me");
}

export function updateMyProfile(payload: UserProfileUpdateRequest) {
  return apiRequest<UserProfileResponse>("/api/profile/me", {
    method: "PUT",
    body: payload,
  });
}

export function fetchMyInterestTags() {
  return apiRequest<InterestTagsResponse>("/api/profile/me/interests");
}

export function updateMyInterestTags(payload: { interest_tags: string[] }) {
  return apiRequest<InterestTagsResponse>("/api/profile/me/interests", {
    method: "PUT",
    body: payload,
  });
}
