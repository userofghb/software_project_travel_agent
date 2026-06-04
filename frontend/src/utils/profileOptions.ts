import type { UserProfileUpdateRequest } from "../api/types";

export type ProfileOption = {
  label: string;
  value: string;
  weight?: number;
};

export const travelStyleOptions: ProfileOption[] = [
  { label: "休闲放松", value: "leisure", weight: 65 },
  { label: "探索冒险", value: "adventure", weight: 85 },
  { label: "人文体验", value: "culture", weight: 75 },
  { label: "亲子出行", value: "family", weight: 60 },
  { label: "美食优先", value: "foodie", weight: 80 },
  { label: "购物打卡", value: "shopping", weight: 70 },
];

export const budgetLevelOptions: ProfileOption[] = [
  { label: "经济节省", value: "low", weight: 35 },
  { label: "适中预算", value: "medium", weight: 60 },
  { label: "品质舒适", value: "high", weight: 85 },
];

export const transportOptions: ProfileOption[] = [
  { label: "公共交通优先", value: "public_transit", weight: 65 },
  { label: "公交地铁 + 步行", value: "walk_or_nearby", weight: 70 },
  { label: "步行友好", value: "mixed_walk", weight: 55 },
  { label: "打车/专车优先", value: "private_transport", weight: 80 },
];

export const accommodationOptions: ProfileOption[] = [
  { label: "舒适酒店", value: "comfort", weight: 60 },
  { label: "特色民宿", value: "homestay", weight: 70 },
  { label: "酒店含早餐", value: "hotel_with_breakfast", weight: 75 },
  { label: "民宿含早餐", value: "homestay_with_breakfast", weight: 80 },
];

export const paceOptions: ProfileOption[] = [
  { label: "轻松慢游", value: "relaxed", weight: 35 },
  { label: "张弛有度", value: "balanced", weight: 60 },
  { label: "安排充实", value: "intensive", weight: 85 },
];

export const riskOptions: ProfileOption[] = [
  { label: "不太敏感", value: "low", weight: 35 },
  { label: "适度规避", value: "medium", weight: 60 },
  { label: "高度敏感", value: "high", weight: 90 },
];

export const interestOptions: ProfileOption[] = [
  { label: "历史人文", value: "history" },
  { label: "自然风光", value: "nature" },
  { label: "本地美食", value: "food" },
  { label: "城市漫步", value: "citywalk" },
  { label: "摄影打卡", value: "photo" },
  { label: "亲子友好", value: "family" },
  { label: "博物馆", value: "museum" },
  { label: "购物休闲", value: "shopping" },
  { label: "户外运动", value: "outdoor" },
];

export const defaultProfile: UserProfileUpdateRequest = {
  travel_style: "leisure",
  budget_level: "medium",
  interest_tags: ["food", "citywalk"],
  transport_preference: "public_transit",
  accommodation_preference: "comfort",
  risk_sensitivity: "medium",
  pace_preference: "balanced",
};

export function optionLabel(options: ProfileOption[], value: string | undefined | null): string {
  return options.find((item) => item.value === value)?.label ?? value ?? "-";
}

export function optionWeight(options: ProfileOption[], value: string | undefined | null): number {
  return options.find((item) => item.value === value)?.weight ?? 50;
}

export function interestLabel(value: string): string {
  return optionLabel(interestOptions, value);
}
