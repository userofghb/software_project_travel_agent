from __future__ import annotations

import json
import math
import re
from datetime import date, timedelta
from typing import Any

import httpx

from app.core.config import get_settings

AMAP_BASE_URL = "https://restapi.amap.com"


class ProviderConfigurationError(RuntimeError):
    pass


def get_attraction_provider():
    if _should_use_real("amap"):
        return RobustAmapAttractionProvider()
    return MockAttractionProvider()


def get_hotel_provider():
    if _should_use_real("amap"):
        return AmapHotelProvider()
    return MockHotelProvider()


def get_weather_provider():
    if _should_use_real("amap"):
        return RobustAmapWeatherProvider()
    return MockWeatherProvider()


def get_route_provider():
    if _should_use_real("amap"):
        return AmapRouteProvider()
    return MockRouteProvider()


def get_planner_provider():
    if _should_use_real("openai"):
        return OpenAIPlannerProvider()
    return RuleBasedPlannerProvider()


def _should_use_real(provider: str) -> bool:
    settings = get_settings()
    mode = settings.agent_provider_mode.lower()
    if mode == "mock":
        return False
    if provider == "amap":
        has_key = bool(settings.amap_api_key)
        key_name = "AMAP_API_KEY"
    elif provider == "openai":
        has_key = bool(settings.openai_api_key)
        key_name = "OPENAI_API_KEY"
    else:
        raise ValueError(f"Unknown provider: {provider}")

    if mode == "real" and not has_key:
        raise ProviderConfigurationError(f"{key_name} is required when AGENT_PROVIDER_MODE=real")
    return has_key


def _timeout() -> float:
    return get_settings().provider_timeout_seconds


def _openai_responses_url() -> str:
    return f"{get_settings().openai_base_url.rstrip('/')}/responses"


class MockAttractionProvider:
    def search(self, city: str, interests: list[str]) -> list[dict[str, Any]]:
        base_tags = interests or ["city_walk", "food"]
        return [
            {
                "id": f"mock-{city}-museum",
                "name": f"{city} Museum",
                "type": "attraction",
                "tag": base_tags[0],
                "recommended_hours": 3,
                "address": f"{city} city center",
                "location": {"lng": 121.475, "lat": 31.23},
            },
            {
                "id": f"mock-{city}-park",
                "name": f"{city} Central Park",
                "type": "attraction",
                "tag": base_tags[-1],
                "recommended_hours": 2,
                "address": f"{city} city center",
                "location": {"lng": 121.485, "lat": 31.235},
            },
            {
                "id": f"mock-{city}-old-town",
                "name": f"{city} Old Town",
                "type": "attraction",
                "tag": "must_see",
                "recommended_hours": 3,
                "address": f"{city} historic area",
                "location": {"lng": 121.49, "lat": 31.24},
            },
        ]


class MockHotelProvider:
    def search(self, city: str, budget_range: str, accommodation_preference: str) -> dict[str, Any]:
        price_map = {"low": 180, "medium": 320, "high": 680, "budget": 180}
        budget = price_map.get(budget_range, 320)
        return {
            "id": f"mock-{city}-hotel",
            "name": f"{city} {accommodation_preference} Hotel",
            "price_per_night": budget,
            "location_name": f"{city} city center",
            "address": f"{city} city center",
            "rating": 4.5,
            "location": {"lng": 121.47, "lat": 31.228},
        }


class MockWeatherProvider:
    def forecast(self, start_date: date, end_date: date, city: str) -> list[dict[str, Any]]:
        conditions = ["sunny", "cloudy", "light_rain", "moderate_rain"]
        current = start_date
        items: list[dict[str, Any]] = []
        index = 0
        while current <= end_date:
            condition = conditions[index % len(conditions)]
            items.append(
                {
                    "date": current.isoformat(),
                    "city": city,
                    "condition": condition,
                    "high": 26 + index,
                    "low": 18 + index,
                    "risk_score": self._risk_score(condition),
                }
            )
            current += timedelta(days=1)
            index += 1
        return items

    @staticmethod
    def _risk_score(condition: str) -> int:
        mapping = {"sunny": 2, "cloudy": 1, "light_rain": -1, "moderate_rain": -3, "heavy_rain": -5}
        return mapping.get(condition, 0)


class MockRouteProvider:
    def build_routes(
        self,
        days: list[dict[str, Any]],
        hotel: dict[str, Any],
        attractions: list[dict[str, Any]],
        transport_preference: str,
        city: str,
    ) -> dict[str, Any]:
        points = build_map_points(hotel, attractions, days)
        routes = []
        for day in days:
            day_points = _points_for_day(day, points)
            if len(day_points) < 2:
                continue
            for origin, destination in zip(day_points, day_points[1:]):
                routes.append(_mock_route(day.get("date"), origin, destination, transport_preference))
        return {"points": points, "routes": routes}


class RuleBasedPlannerProvider:
    def generate_plan(
        self,
        request: dict[str, Any],
        user_profile: dict[str, Any],
        attractions: list[dict[str, Any]],
        weather_info: list[dict[str, Any]],
        hotel: dict[str, Any],
        profile_summary: str = "",
    ) -> dict[str, Any]:
        start = _parse_date(request["start_date"])
        end = _parse_date(request["end_date"])
        days = _build_rule_based_days(request, user_profile, attractions, weather_info, start, end)
        budget = _build_budget(days, request, hotel)
        overall_suggestions = [
            "每天按上午、午餐、下午、晚间分段安排，避免只堆一个景点。",
            "同一时段可串联相邻景点，但保留用餐、转场和休息时间。",
            "雨天或高温时优先把室内项目放到下午，并保留可替换活动。",
            "预算按住宿、餐饮、交通、门票和弹性预留拆分，便于前端展示。",
        ]
        origin = request.get("origin")
        if origin:
            overall_suggestions.insert(
                0,
                f"出发地为 {origin}，目的地为 {request['city']}，行程应从出发地出发并围绕目的地安排。",
            )

        return {
            "title": request["title"],
            "origin": origin,
            "city": request["city"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": days,
            "attractions": attractions,
            "hotel": hotel,
            "meals": _extract_meals(days),
            "weather_info": weather_info,
            "budget": budget,
            "warnings": [],
            "overall_suggestions": overall_suggestions,
            "map": {
                "points": build_map_points(hotel, attractions, days),
            },
        }


def _build_rule_based_days(
    request: dict[str, Any],
    user_profile: dict[str, Any],
    attractions: list[dict[str, Any]],
    weather_info: list[dict[str, Any]],
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    total_days = (end - start).days + 1
    days = []
    for index in range(total_days):
        travel_date = start + timedelta(days=index)
        weather = weather_info[index] if index < len(weather_info) else {}
        day_attractions = _choose_day_attractions(attractions, index, weather, user_profile)
        activities = _build_day_activities(request, user_profile, day_attractions, weather)
        days.append(
            {
                "date": travel_date.isoformat(),
                "day_number": index + 1,
                "theme": _day_theme(index, day_attractions, weather),
                "weather": weather,
                "weather_suggestion": _weather_suggestion(weather, user_profile),
                "activities": activities,
            }
        )
    return days


def _choose_day_attractions(
    attractions: list[dict[str, Any]],
    day_index: int,
    weather: dict[str, Any],
    user_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not attractions:
        return []

    ordered = sorted(list(attractions), key=lambda item: _attraction_profile_score(item, user_profile), reverse=True)
    if _is_weather_risky(weather, user_profile):
        ordered = sorted(ordered, key=lambda item: not _is_indoor_attraction(item))

    per_day = min(_profile_activity_count(user_profile), len(ordered))
    start_index = (day_index * per_day) % len(ordered)
    return [ordered[(start_index + offset) % len(ordered)] for offset in range(per_day)]


def _profile_activity_count(user_profile: dict[str, Any] | None) -> int:
    pace = str((user_profile or {}).get("pace_preference") or "").lower()
    style = str((user_profile or {}).get("travel_style") or "").lower()
    if pace == "relaxed" or style in {"leisure", "family"}:
        return 2
    if pace == "intensive" or style in {"adventure", "shopping"}:
        return 4
    return 3


def _profile_activity_slots(user_profile: dict[str, Any] | None) -> list[tuple[str, str, str]]:
    count = _profile_activity_count(user_profile)
    if count <= 2:
        return [("09:30", "morning", "2小时"), ("15:00", "afternoon", "2小时")]
    if count >= 4:
        return [
            ("09:00", "morning", "1.5小时"),
            ("10:45", "morning", "1.25小时"),
            ("14:30", "afternoon", "1.75小时"),
            ("16:30", "afternoon", "1.5小时"),
        ]
    return [("09:00", "morning", "2小时"), ("11:00", "morning", "1小时"), ("14:30", "afternoon", "2.5小时")]


def _attraction_profile_score(attraction: dict[str, Any], user_profile: dict[str, Any] | None) -> int:
    if not user_profile:
        return 0
    text = " ".join(str(attraction.get(key) or "").lower() for key in ("name", "category", "tag", "typecode", "address"))
    tags = [str(tag).lower() for tag in user_profile.get("interest_tags") or []]
    style = str(user_profile.get("travel_style") or "").lower()
    score = 0
    for tag in tags:
        if tag and tag in text:
            score += 5
    style_keywords = {
        "culture": ("museum", "history", "博物馆", "历史", "文化", "纪念馆", "美术馆"),
        "foodie": ("food", "餐", "美食", "小吃", "市场"),
        "shopping": ("shopping", "mall", "商场", "购物", "步行街"),
        "family": ("park", "公园", "乐园", "亲子", "动物园", "科技馆"),
        "adventure": ("outdoor", "山", "徒步", "户外", "自然"),
        "leisure": ("公园", "街", "广场", "citywalk", "休闲"),
    }
    score += sum(3 for keyword in style_keywords.get(style, ()) if keyword in text)
    return score


def _build_day_activities(
    request: dict[str, Any],
    user_profile: dict[str, Any],
    attractions: list[dict[str, Any]],
    weather: dict[str, Any],
) -> list[dict[str, Any]]:
    city = request["city"]
    transport = request.get("transport_preference", "public_transit")
    budget_range = request.get("budget_range", "medium")
    slots = _profile_activity_slots(user_profile)
    activities: list[dict[str, Any]] = [
        _build_meal_activity("08:00", "morning", city, budget_range),
    ]
    lunch_added = False
    for slot_index, (time, period, duration) in enumerate(slots):
        if period == "afternoon" and not lunch_added:
            activities.append(_build_meal_activity("12:30", "lunch", city, budget_range))
            lunch_added = True
        activities.append(
            _build_attraction_activity(
                attractions[slot_index] if len(attractions) > slot_index else None,
                time=time,
                period=period,
                duration=duration,
                city=city,
                transport=transport,
                budget_range=budget_range,
                weather=weather,
            )
        )
    if not lunch_added:
        activities.append(_build_meal_activity("12:30", "lunch", city, budget_range))
    activities.append(_build_meal_activity("18:30", "evening", city, budget_range))
    return activities


def _build_attraction_activity(
    attraction: dict[str, Any] | None,
    *,
    time: str,
    period: str,
    duration: str,
    city: str,
    transport: str,
    budget_range: str,
    weather: dict[str, Any],
) -> dict[str, Any]:
    if not attraction:
        return {
            "time": time,
            "period": period,
            "title": f"{city}自由探索与休整",
            "type": "free_time",
            "poi_id": None,
            "location": None,
            "transport": transport,
            "reason": "为转场、排队和临时兴趣保留弹性时间",
            "duration": duration,
            "budget": 0,
            "tags": ["自由活动", "弹性"],
        }

    reason = "上午体力和光线更好，适合连续游览相邻重点景点"
    if period == "afternoon":
        reason = "下午安排节奏更舒缓的项目，给午餐后转场留出余量"
    if _is_weather_risky(weather):
        reason = "结合当天天气风险，优先安排可控、可替换的游览点"

    return {
        "time": time,
        "period": period,
        "title": attraction.get("name") or "精选景点",
        "type": "attraction",
        "poi_id": attraction.get("id"),
        "location": attraction.get("location"),
        "address": attraction.get("address"),
        "transport": transport,
        "reason": reason,
        "duration": duration,
        "budget": _activity_ticket_budget(attraction, budget_range),
        "tags": _activity_tags(attraction, weather),
    }


def _build_meal_activity(time: str, period: str, city: str, budget_range: str) -> dict[str, Any]:
    profile = _budget_profile(budget_range)
    meal_kind = _meal_kind({"period": period, "time": time})
    labels = {
        "breakfast": ("早餐与出发准备", "45分钟", profile["breakfast"], ["餐饮", "早餐"]),
        "lunch": ("午餐与休息", "1.5小时", profile["lunch"], ["餐饮", "休息"]),
        "dinner": ("晚餐与自由活动", "2小时", profile["dinner"], ["餐饮", "自由活动"]),
    }
    title, duration, budget, tags = labels[meal_kind]
    return {
        "time": time,
        "period": period,
        "meal_kind": meal_kind,
        "title": title,
        "type": "food",
        "poi_id": None,
        "location": None,
        "transport": "walk_or_nearby",
        "reason": "按行程动线就近选择本地特色餐厅，避免餐饮和景点相互挤压",
        "duration": duration,
        "budget": budget,
        "tags": tags,
    }


def _day_theme(day_index: int, attractions: list[dict[str, Any]], weather: dict[str, Any]) -> str:
    if _is_weather_risky(weather):
        return f"Day {day_index + 1}: 天气友好型城市体验"
    if attractions:
        first_name = attractions[0].get("name") or "城市地标"
        return f"Day {day_index + 1}: {first_name}周边深度游"
    return f"Day {day_index + 1}: 轻松城市探索"


def _weather_suggestion(weather: dict[str, Any], user_profile: dict[str, Any] | None = None) -> str:
    if _is_weather_risky(weather, user_profile):
        risk = str((user_profile or {}).get("risk_sensitivity") or "").lower()
        if risk == "high":
            return "当天存在天气风险，建议减少户外停留，优先室内、短距离和可取消项目。"
        return "当天存在天气风险，下午优先安排室内、短距离或可替换活动。"
    return "天气条件较适合户外游览，上午可安排多个相邻景点。"


def _is_weather_risky(weather: dict[str, Any], user_profile: dict[str, Any] | None = None) -> bool:
    condition = str(weather.get("condition") or "").lower()
    risk_score = weather.get("risk_score")
    sensitivity = str((user_profile or {}).get("risk_sensitivity") or "").lower()
    threshold = -1 if sensitivity == "high" else -3 if sensitivity == "low" else -2
    if isinstance(risk_score, (int, float)) and risk_score <= threshold:
        return True
    risky_keywords = ("rain", "storm", "snow", "wind", "雨", "雪", "风", "高温", "雷")
    if sensitivity == "low":
        strong_keywords = ("storm", "heavy", "暴雨", "雷暴", "台风", "大雪")
        return any(keyword in condition for keyword in strong_keywords)
    return any(keyword in condition for keyword in risky_keywords)


def _is_indoor_attraction(attraction: dict[str, Any]) -> bool:
    text = " ".join(
        str(attraction.get(key) or "")
        for key in ("name", "category", "tag", "typecode", "address")
    ).lower()
    indoor_keywords = ("museum", "gallery", "mall", "博物馆", "纪念馆", "美术馆", "展览", "商场", "书店", "剧院", "馆")
    return any(keyword in text for keyword in indoor_keywords)


def _activity_tags(attraction: dict[str, Any], weather: dict[str, Any]) -> list[str]:
    tags = []
    category = attraction.get("category")
    if isinstance(category, str):
        tags.extend(part for part in category.split(";") if part)
    if attraction.get("tag"):
        tags.append(str(attraction["tag"]))
    if _is_indoor_attraction(attraction):
        tags.append("室内友好")
    if _is_weather_risky(weather):
        tags.append("天气备选")
    return tags[:4] or ["精选景点"]


def _activity_ticket_budget(attraction: dict[str, Any], budget_range: str) -> int:
    text = " ".join(str(attraction.get(key) or "") for key in ("name", "category", "address"))
    if any(keyword in text for keyword in ("公园", "广场", "街", "外滩", "步行街")):
        return 0
    profile = _budget_profile(budget_range)
    if any(keyword in text for keyword in ("塔", "乐园", "主题")):
        return profile["premium_ticket"]
    if any(keyword in text for keyword in ("博物馆", "纪念馆", "美术馆")):
        return profile["museum_ticket"]
    return profile["ticket"]


def _budget_profile(budget_range: str) -> dict[str, Any]:
    value = str(budget_range or "").lower()
    if any(token in value for token in ("low", "budget", "经济", "低")):
        return {"breakfast": 25, "lunch": 45, "dinner": 65, "ticket": 30, "museum_ticket": 0, "premium_ticket": 100, "transport_day": 45, "buffer_rate": 0.08}
    if any(token in value for token in ("high", "luxury", "高")):
        return {"breakfast": 70, "lunch": 120, "dinner": 180, "ticket": 100, "museum_ticket": 50, "premium_ticket": 260, "transport_day": 160, "buffer_rate": 0.15}
    return {"breakfast": 40, "lunch": 70, "dinner": 110, "ticket": 60, "museum_ticket": 20, "premium_ticket": 180, "transport_day": 80, "buffer_rate": 0.12}


def _build_budget(days: list[dict[str, Any]], request: dict[str, Any], hotel: dict[str, Any]) -> dict[str, Any]:
    profile = _budget_profile(request.get("budget_range", "medium"))
    total_days = max(len(days), 1)
    nights = max(total_days - 1, 1 if total_days > 1 and hotel else 0)
    lodging_total = (hotel.get("price_per_night") or 0) * nights
    meal_total = _sum_activity_budget(days, {"food"})
    ticket_total = _sum_activity_budget(days, {"attraction"})
    transport_activity_total = _sum_activity_budget(days, {"transport"})
    intercity_total = _sum_activity_budget(days, {"intercity_transport"})
    transport_total = transport_activity_total if transport_activity_total > 0 else profile["transport_day"] * total_days
    subtotal = lodging_total + meal_total + ticket_total + transport_total + intercity_total
    buffer = _round_to_ten(subtotal * profile["buffer_rate"])

    per_day = []
    for index, day in enumerate(days):
        daily_meals = sum(_safe_int(activity.get("budget")) or 0 for activity in day.get("activities", []) if activity.get("type") == "food")
        daily_tickets = sum(_safe_int(activity.get("budget")) or 0 for activity in day.get("activities", []) if activity.get("type") == "attraction")
        daily_transport_activities = sum(_safe_int(activity.get("budget")) or 0 for activity in day.get("activities", []) if activity.get("type") == "transport")
        daily_intercity = sum(_safe_int(activity.get("budget")) or 0 for activity in day.get("activities", []) if activity.get("type") == "intercity_transport")
        daily_lodging = (hotel.get("price_per_night") or 0) if index < nights else 0
        daily_transport = daily_transport_activities if transport_activity_total > 0 else profile["transport_day"]
        per_day.append(
            {
                "date": day.get("date"),
                "lodging": daily_lodging,
                "meals": daily_meals,
                "transport": daily_transport,
                "intercity": daily_intercity,
                "tickets": daily_tickets,
                "subtotal": daily_lodging + daily_meals + daily_transport + daily_intercity + daily_tickets,
            }
        )

    breakdown = [
        {"key": "lodging", "name": "住宿", "value": int(lodging_total)},
        {"key": "meals", "name": "餐饮", "value": int(meal_total)},
        {"key": "transport", "name": "市内交通", "value": int(transport_total)},
    ]
    if intercity_total > 0:
        breakdown.append({"key": "intercity", "name": "往返大交通", "value": int(intercity_total)})
    breakdown.extend(
        [
            {"key": "tickets", "name": "门票", "value": int(ticket_total)},
            {"key": "buffer", "name": "弹性预留", "value": int(buffer)},
        ]
    )

    return {
        "range": request.get("budget_range", "medium"),
        "estimated_total": int(subtotal + buffer),
        "breakdown": breakdown,
        "per_day": per_day,
        "assumptions": [
            "住宿按行程晚数估算。",
            "餐饮优先按真实餐馆 POI 附近用餐估算。",
            "交通优先按已生成的转场方案估算；没有路线明细时按每日城市内交通估算。",
            "往返大交通按出发地与目的地距离、预算倾向和常见高铁/飞机方案估算。",
        ],
    }


def _sum_activity_budget(days: list[dict[str, Any]], activity_types: set[str]) -> int:
    total = 0
    for day in days:
        rows = day.get("nodes") if isinstance(day.get("nodes"), list) else day.get("activities", [])
        for activity in rows:
            if activity.get("type") in activity_types:
                total += _safe_int(activity.get("budget")) or 0
    return total


def _round_to_ten(value: float) -> int:
    return int(round(value / 10) * 10)


def _extract_meals(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    meals = []
    for day in days:
        for activity in day.get("activities", []):
            if activity.get("type") == "food":
                meals.append(
                    {
                        "date": day.get("date"),
                        "time": activity.get("time"),
                        "meal_kind": _meal_kind(activity),
                        "suggestion": activity.get("title"),
                        "budget": activity.get("budget"),
                        "tags": activity.get("tags", []),
                    }
                )
    return meals


class AmapAttractionProvider:
    def search(self, city: str, interests: list[str]) -> list[dict[str, Any]]:
        keywords = " ".join(interests) if interests else "景点"
        pois = _amap_place_text(city=city, keywords=f"{city} {keywords}", types="110000", offset=12)
        return [_normalize_poi(poi, fallback_type="attraction") for poi in pois]


class AmapHotelProvider:
    def search(self, city: str, budget_range: str, accommodation_preference: str) -> dict[str, Any]:
        keywords = f"{city} {accommodation_preference} 酒店"
        pois = _amap_place_text(city=city, keywords=keywords, types="100000", offset=5)
        if not pois:
            raise RuntimeError("Amap hotel search returned no POIs")
        hotel = _normalize_poi(pois[0], fallback_type="hotel")
        price_map = {"low": 180, "medium": 320, "high": 680, "budget": 180}
        hotel["price_per_night"] = price_map.get(budget_range, 320)
        return hotel


class AmapWeatherProvider:
    def forecast(self, start_date: date, end_date: date, city: str) -> list[dict[str, Any]]:
        adcode = _resolve_city_adcode(city)
        data = _amap_get(
            "/v3/weather/weatherInfo",
            {"city": adcode, "extensions": "all", "output": "JSON"},
        )
        forecasts = data.get("forecasts") or []
        if not forecasts:
            raise RuntimeError("Amap weather search returned no forecasts")

        casts = forecasts[0].get("casts") or []
        by_date = {item.get("date"): item for item in casts}
        items: list[dict[str, Any]] = []
        current = start_date
        while current <= end_date:
            raw = by_date.get(current.isoformat()) or (casts[min(len(items), len(casts) - 1)] if casts else {})
            condition = raw.get("dayweather") or raw.get("nightweather") or "unknown"
            items.append(
                {
                    "date": current.isoformat(),
                    "city": city,
                    "condition": condition,
                    "high": _safe_int(raw.get("daytemp")),
                    "low": _safe_int(raw.get("nighttemp")),
                    "wind": raw.get("daywind") or raw.get("nightwind"),
                    "risk_score": _weather_risk_score(condition),
                    "source": "amap",
                }
            )
            current += timedelta(days=1)
        return items


class RobustAmapAttractionProvider:
    def search(self, city: str, interests: list[str]) -> list[dict[str, Any]]:
        search_specs: list[tuple[str, str, int]] = [
            (f"{city} 景点", "110000", 8),
            (f"{city} 博物馆", "140000", 4),
            (f"{city} 公园", "110000|110100|110200", 4),
        ]
        for interest in interests[:4]:
            text = str(interest).strip()
            if text:
                search_specs.append((f"{city} {text}", "", 4))

        seen: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for keywords, types, offset in search_specs:
            pois = _amap_place_text(city=city, keywords=keywords, types=types, offset=offset)
            for poi in pois:
                item = _normalize_poi(poi, fallback_type="attraction")
                key = str(item.get("id") or item.get("name") or "")
                if not key or key in seen or not item.get("location"):
                    continue
                seen.add(key)
                normalized.append(item)
                if len(normalized) >= 12:
                    return normalized
        return normalized


class RobustAmapWeatherProvider:
    def forecast(self, start_date: date, end_date: date, city: str) -> list[dict[str, Any]]:
        lookup_values: list[str] = []
        try:
            adcode = _resolve_city_adcode(city)
            if adcode:
                lookup_values.append(adcode)
        except Exception:
            pass
        lookup_values.append(city)

        data: dict[str, Any] | None = None
        last_error: Exception | None = None
        for lookup_city in dict.fromkeys(lookup_values):
            try:
                candidate = _amap_get(
                    "/v3/weather/weatherInfo",
                    {"city": lookup_city, "extensions": "all", "output": "JSON"},
                )
                if candidate.get("forecasts"):
                    data = candidate
                    break
            except Exception as exc:
                last_error = exc
        if data is None:
            raise RuntimeError(f"Amap weather search failed: {last_error}")

        forecasts = data.get("forecasts") or []
        casts = forecasts[0].get("casts") or []
        if not casts:
            raise RuntimeError("Amap weather search returned no casts")

        by_date = {item.get("date"): item for item in casts}
        items: list[dict[str, Any]] = []
        current = start_date
        while current <= end_date:
            raw = by_date.get(current.isoformat()) or casts[min(len(items), len(casts) - 1)]
            condition = raw.get("dayweather") or raw.get("nightweather") or "unknown"
            items.append(
                {
                    "date": current.isoformat(),
                    "city": city,
                    "condition": condition,
                    "high": _safe_int(raw.get("daytemp")),
                    "low": _safe_int(raw.get("nighttemp")),
                    "wind": raw.get("daywind") or raw.get("nightwind"),
                    "risk_score": _weather_risk_score(condition),
                    "source": "amap",
                }
            )
            current += timedelta(days=1)
        return items


class AmapRouteProvider:
    def build_routes(
        self,
        days: list[dict[str, Any]],
        hotel: dict[str, Any],
        attractions: list[dict[str, Any]],
        transport_preference: str,
        city: str,
    ) -> dict[str, Any]:
        points = build_map_points(hotel, attractions, days)
        routes = []
        mode = _route_mode(transport_preference)

        for day in days:
            day_points = _points_for_day(day, points)
            if len(day_points) < 2:
                continue
            for origin, destination in zip(day_points, day_points[1:]):
                routes.append(self._route(day.get("date"), origin, destination, mode, city))

        return {"points": points, "routes": routes}

    def _route(self, day: str | None, origin: dict[str, Any], destination: dict[str, Any], mode: str, city: str) -> dict[str, Any]:
        origin_text = _location_text(origin)
        destination_text = _location_text(destination)
        if mode == "transit":
            data = _amap_get(
                "/v3/direction/transit/integrated",
                {
                    "origin": origin_text,
                    "destination": destination_text,
                    "city": city,
                    "cityd": city,
                    "strategy": "0",
                    "output": "JSON",
                },
            )
            return _normalize_transit_route(day, origin, destination, data)

        endpoint = "/v3/direction/walking" if mode == "walking" else "/v3/direction/driving"
        data = _amap_get(
            endpoint,
            {
                "origin": origin_text,
                "destination": destination_text,
                "strategy": "0",
                "output": "JSON",
            },
        )
        return _normalize_path_route(day, origin, destination, mode, data)


class OpenAIPlannerProvider:
    def generate_plan(
        self,
        request: dict[str, Any],
        user_profile: dict[str, Any],
        attractions: list[dict[str, Any]],
        weather_info: list[dict[str, Any]],
        hotel: dict[str, Any],
        profile_summary: str = "",
    ) -> dict[str, Any]:
        settings = get_settings()
        context = {
            "request": request,
            "user_profile": user_profile,
            "profile_summary": profile_summary,
            "attractions": attractions,
            "weather_info": weather_info,
            "hotel": hotel,
            "planning_rules": {
                "daily_structure": "完整全天行程通常覆盖早餐、上午游览、午餐、下午游览、晚餐/晚间安排；但抵达日晚、返程早或用户明确交通时间压缩时，只安排落在可用时间窗口内的餐次。",
                "time_realism": "先推理当天抵达/返程时间窗口，再安排餐饮、景点和住宿节点；景点之间要考虑转场、排队、用餐和休息。",
                "weather": "雨天、高温或高风险天气下，下午优先安排室内、短距离或可替换活动。",
                "budget": "预算必须拆分住宿、餐饮、交通、门票和弹性预留，并给出每日 subtotal。",
                "activity_fields": "每个 activity 必须包含 time、period、type、title、reason、duration、budget、tags；景点和餐饮都要作为独立节点思考，景点类活动要带 poi_id/location/transport，餐饮如果没有真实餐馆坐标可先留空，后续会就近匹配餐馆。",
                "route_agent": "不要把从酒店出发、景点之间转场、公交地铁怎么走写成景点 activity；Route Agent 会在后续调用高德路线 API 并插入 type=transport 的转场方案。map 只需要 points，不要输出 routes、polyline 或 steps。",
                "hotel_display": "不要省略酒店住宿；住宿会在后续归一化为前一晚 evening 的 type=hotel 活动。",
                "meal_copy": "不要机械强制三餐。只有当天时间窗口覆盖对应时段时才安排该餐：早餐通常在 07:00-09:30，午餐在 11:30-13:30，晚餐在 17:30-19:30；例如第一天火车 12:00 才到，就不应再安排早餐，午餐也可简化为抵达后顺路用餐，避免两个晚餐。",
                "origin_handling": "如果 request 中包含 origin，则 origin 代表出发地，city 代表目的地；计划应保留 origin 字段并在建议中区分出发地与目的地。",
                "regeneration": "如果 request.previous_content 存在，说明用户是在优化现有方案；请优先保留合理的日期、住宿、三餐、重点景点和动线，只针对 notes 中的优化目标调整。",
            },
            "required_keys": [
                "title",
                "city",
                "start_date",
                "end_date",
                "days",
                "attractions",
                "hotel",
                "meals",
                "weather_info",
                "budget",
                "warnings",
                "overall_suggestions",
                "map",
            ],
        }
        payload = {
            "model": settings.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "你是智能旅行助手的 Planner Agent。只输出一个 JSON 对象，字段名保持英文，正文内容使用中文。"
                        "你要生成像前端详情页 mock 一样完整、可展示、可执行的旅行方案，而不是每天只列一个景点。"
                        "先根据 origin、city、notes、previous_content 和用户描述推理每天的可用时间窗口；完整全天才安排早餐、午餐、晚餐，"
                        "抵达日晚、返程早或用户交通时间导致窗口不足时，不要机械补齐三餐，尤其避免同一天出现两个晚餐。"
                        "按 morning、lunch、afternoon、evening 编排；上午可以安排 1-2 个相邻景点，"
                        "下午和晚上要考虑体力、转场、用餐、排队、营业时间常识和天气风险。"
                        "activity 要包含 time、period、type、title、reason、duration、budget、tags；"
                        "景点和餐饮都要作为节点化活动来思考：景点活动只能从输入 attractions 中选择，并保留 poi_id/location/transport，不要虚构经纬度；餐饮可写具体餐厅建议或餐次节点，后续会用真实餐馆 POI 补齐。"
                        "不要把交通转场写成景点；高德路线 API 会在 Route Agent 阶段生成独立 type=transport 活动。"
                        "地图只展示地点点位，map 只输出 points，不要输出 routes、polyline 或 steps。"
                        "餐饮标题不要使用“城市名 + 本地早餐/午餐/晚餐”的占位文案。"
                        "餐饮和休息活动可以作为无坐标建议，但不要冒充 POI。"
                        "如果用户提供了 previous_content，要把它当作当前方案上下文，按 notes 的目标优化，不要无理由推翻整个方案。"
                        "budget 必须包含 estimated_total、breakdown、per_day 和 assumptions，"
                        "breakdown 至少覆盖 lodging、meals、transport、tickets、buffer。"
                        "如果天气有雨、高温、大风或 risk_score 较低，给 day.weather_suggestion，并把室内或短距离活动放到更合适的时段。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "travel_plan",
                    "schema": TRAVEL_PLAN_SCHEMA,
                    "strict": False,
                }
            },
        }
        response = httpx.post(
            _openai_responses_url(),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_timeout(),
        )
        response.raise_for_status()
        data = response.json()
        text = _extract_openai_text(data)
        plan = json.loads(text)
        return _ensure_plan_defaults(plan, request, attractions, weather_info, hotel, user_profile)


def _amap_place_text(city: str, keywords: str, types: str, offset: int) -> list[dict[str, Any]]:
    data = _amap_get(
        "/v3/place/text",
        {
            "keywords": keywords,
            "types": types,
            "city": city,
            "citylimit": "true",
            "children": "0",
            "offset": str(offset),
            "page": "1",
            "extensions": "all",
            "output": "JSON",
        },
    )
    return data.get("pois") or []


def _amap_place_around(
    city: str,
    location: dict[str, float] | None,
    keywords: str,
    types: str,
    offset: int,
) -> list[dict[str, Any]]:
    if location is None:
        return _amap_place_text(city=city, keywords=keywords, types=types, offset=offset)

    data = _amap_get(
        "/v3/place/around",
        {
            "location": f"{location['lng']},{location['lat']}",
            "keywords": keywords,
            "types": types,
            "city": city,
            "radius": "1800",
            "sortrule": "distance",
            "children": "0",
            "offset": str(offset),
            "page": "1",
            "extensions": "all",
            "output": "JSON",
        },
    )
    return data.get("pois") or []


def _amap_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    response = httpx.get(
        f"{AMAP_BASE_URL}{path}",
        params={"key": settings.amap_api_key, **params},
        timeout=_timeout(),
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "1":
        message = data.get("info") or "Amap API request failed"
        raise RuntimeError(message)
    return data


def _resolve_city_adcode(city: str) -> str:
    data = _amap_get("/v3/geocode/geo", {"address": city, "output": "JSON"})
    geocodes = data.get("geocodes") or []
    if not geocodes:
        return city
    return geocodes[0].get("adcode") or city


def _amap_geocode_location(address: str) -> dict[str, float] | None:
    data = _amap_get("/v3/geocode/geo", {"address": address, "output": "JSON"})
    geocodes = data.get("geocodes") or []
    if not geocodes:
        return None
    lng, lat = _parse_location(geocodes[0].get("location"))
    if lng is None or lat is None:
        return None
    return {"lng": lng, "lat": lat}


def _haversine_km(origin: dict[str, float], destination: dict[str, float]) -> float:
    radius = 6371.0
    lat1 = math.radians(origin["lat"])
    lat2 = math.radians(destination["lat"])
    delta_lat = math.radians(destination["lat"] - origin["lat"])
    delta_lng = math.radians(destination["lng"] - origin["lng"])
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _normalize_poi(poi: dict[str, Any], fallback_type: str) -> dict[str, Any]:
    lng, lat = _parse_location(poi.get("location"))
    photos = poi.get("photos") if isinstance(poi.get("photos"), list) else []
    return {
        "id": poi.get("id") or poi.get("name"),
        "name": poi.get("name"),
        "type": fallback_type,
        "typecode": poi.get("typecode"),
        "category": poi.get("type"),
        "address": _first_text(poi.get("address")),
        "location": {"lng": lng, "lat": lat} if lng is not None and lat is not None else None,
        "rating": _first_text(poi.get("biz_ext", {}).get("rating")) if isinstance(poi.get("biz_ext"), dict) else None,
        "photos": [photo.get("url") for photo in photos if isinstance(photo, dict) and photo.get("url")],
        "source": "amap",
    }


def build_map_points(
    hotel: dict[str, Any],
    attractions: list[dict[str, Any]],
    days: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    points = []
    seen: set[str] = set()

    def add_point(
        source: dict[str, Any],
        point_type: str,
        fallback_id: str | None = None,
        day: str | None = None,
        order: int | None = None,
    ) -> None:
        location = _normalize_location(source.get("location"))
        if location is None:
            return

        point_id = source.get("id") or source.get("poi_id") or fallback_id or source.get("name") or source.get("title")
        name = source.get("name") or source.get("title") or str(point_id or "")
        key_base = str(point_id or f"{location['lng']},{location['lat']}")
        key = f"{key_base}:{day}" if day else key_base
        if key in seen:
            return

        seen.add(key)
        points.append(
            {
                "id": point_id,
                "name": name,
                "type": point_type,
                "address": source.get("address") or source.get("location_name"),
                "location": location,
                "day": day,
                "order": order,
            }
        )

    add_point(hotel, "hotel", "hotel")
    has_day_points = False
    for day in days or []:
        if not isinstance(day, dict):
            continue
        point_order = 1
        for activity in day.get("activities") or []:
            if not isinstance(activity, dict):
                continue
            activity_type = str(activity.get("type") or "activity")
            if activity_type in {"transport", "intercity_transport"}:
                continue
            point_type = activity_type if activity_type in {"attraction", "food", "hotel"} else "activity"
            before = len(points)
            add_point(activity, point_type, day=str(day.get("date") or "") or None, order=point_order)
            if len(points) > before:
                has_day_points = True
                point_order += 1

    if not has_day_points:
        for attraction in attractions:
            if isinstance(attraction, dict):
                add_point(attraction, "attraction")
    return points


def _points_for_day(day: dict[str, Any], points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    day_key = str(day.get("date") or "")
    available_points = [
        point
        for point in points
        if point.get("type") == "hotel" or not point.get("day") or str(point.get("day")) == day_key
    ]
    hotel = next((point for point in available_points if point.get("type") == "hotel"), None)
    activities = day.get("activities") or []
    starts_after_intercity_arrival = any(
        activity.get("type") == "intercity_transport" and activity.get("direction") == "outbound"
        for activity in activities
        if isinstance(activity, dict)
    )
    sequence = [] if starts_after_intercity_arrival else ([hotel] if hotel else [])
    for activity in activities:
        matched = _match_point(activity, available_points)
        if not matched:
            continue
        if activity.get("type") == "hotel":
            if not sequence or sequence[-1] != matched:
                sequence.append(matched)
            continue
        if matched not in sequence:
            sequence.append(matched)
    return [point for point in sequence if point]


def _match_point(activity: dict[str, Any], points: list[dict[str, Any]]) -> dict[str, Any] | None:
    poi_id = activity.get("poi_id")
    title = activity.get("title") or ""
    if poi_id:
        for point in points:
            if point.get("id") == poi_id:
                return point
    for point in points:
        name = point.get("name") or ""
        if name and (name in title or title in name):
            return point
    return None


def _mock_route(day: str | None, origin: dict[str, Any], destination: dict[str, Any], mode: str) -> dict[str, Any]:
    return {
        "day": day,
        "from": origin.get("name"),
        "to": destination.get("name"),
        "from_id": origin.get("id"),
        "to_id": destination.get("id"),
        "mode": _route_mode(mode),
        "distance_m": 2000,
        "duration_s": 1200,
        "source": "mock",
    }


def _normalize_path_route(day: str | None, origin: dict[str, Any], destination: dict[str, Any], mode: str, data: dict[str, Any]) -> dict[str, Any]:
    paths = data.get("route", {}).get("paths") or []
    path = paths[0] if paths else {}
    return {
        "day": day,
        "from": origin.get("name"),
        "to": destination.get("name"),
        "from_id": origin.get("id"),
        "to_id": destination.get("id"),
        "mode": mode,
        "distance_m": _safe_int(path.get("distance")),
        "duration_s": _safe_int(path.get("duration")),
        "source": "amap",
    }


def _normalize_transit_route(day: str | None, origin: dict[str, Any], destination: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    transits = data.get("route", {}).get("transits") or []
    transit = transits[0] if transits else {}
    return {
        "day": day,
        "from": origin.get("name"),
        "to": destination.get("name"),
        "from_id": origin.get("id"),
        "to_id": destination.get("id"),
        "mode": "transit",
        "distance_m": _safe_int(transit.get("distance")),
        "duration_s": _safe_int(transit.get("duration")),
        "source": "amap",
    }


def _route_mode(transport_preference: str) -> str:
    value = (transport_preference or "").lower()
    if value in {"walk", "walking", "步行"}:
        return "walking"
    if value in {"drive", "driving", "taxi", "car", "打车", "自驾"}:
        return "driving"
    if get_settings().amap_route_mode.lower() in {"walking", "driving", "transit"}:
        return get_settings().amap_route_mode.lower()
    return "transit"


def _location_text(point: dict[str, Any]) -> str:
    location = point.get("location") or {}
    return f"{location.get('lng')},{location.get('lat')}"


def _normalize_location(value: Any) -> dict[str, float] | None:
    if isinstance(value, dict):
        lng = _safe_float(value.get("lng"))
        lat = _safe_float(value.get("lat"))
    elif isinstance(value, str):
        lng, lat = _parse_location(value)
    else:
        return None
    if lng is None or lat is None:
        return None
    return {"lng": lng, "lat": lat}


def _parse_location(value: Any) -> tuple[float | None, float | None]:
    if not isinstance(value, str) or "," not in value:
        return None, None
    lng, lat = value.split(",", 1)
    return float(lng), float(lat)


def _parse_date(value: str | date) -> date:
    return date.fromisoformat(value) if isinstance(value, str) else value


def _first_text(value: Any) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    if value in (None, ""):
        return None
    return str(value)


def _safe_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _weather_risk_score(condition: str) -> int:
    text = condition or ""
    if any(keyword in text for keyword in ("暴雨", "大暴雨", "雷暴", "台风", "大雪")):
        return -5
    if any(keyword in text for keyword in ("雨", "雪", "大风", "高温")):
        return -3
    if "阴" in text or "云" in text:
        return 1
    return 2


def _extract_openai_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return data["output_text"]
    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text") or content.get("output_text")
            if text:
                chunks.append(text)
    if not chunks:
        raise RuntimeError("OpenAI response did not include text output")
    return "".join(chunks)


def _ensure_plan_defaults(
    plan: dict[str, Any],
    request: dict[str, Any],
    attractions: list[dict[str, Any]],
    weather_info: list[dict[str, Any]],
    hotel: dict[str, Any],
    user_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fallback = RuleBasedPlannerProvider().generate_plan(request, user_profile or {}, attractions, weather_info, hotel)
    for key, value in fallback.items():
        plan.setdefault(key, value)
    plan["origin"] = plan.get("origin") or request.get("origin")
    plan["attractions"] = plan.get("attractions") or attractions
    plan["hotel"] = plan.get("hotel") or hotel
    plan["weather_info"] = plan.get("weather_info") or weather_info
    plan["days"] = _complete_days(
        plan.get("days") or [],
        fallback.get("days") or [],
        request,
        plan["attractions"],
        plan["weather_info"],
    )
    plan["meals"] = plan.get("meals") or _extract_meals(plan["days"])
    plan["budget"] = _normalize_budget(plan.get("budget"), plan["days"], request, plan["hotel"])
    existing_map = plan.get("map") if isinstance(plan.get("map"), dict) else {}
    points = existing_map.get("points") if isinstance(existing_map.get("points"), list) else build_map_points(hotel, attractions, plan["days"])
    plan["map"] = {"points": points}
    return plan


def _complete_days(
    plan_days: list[dict[str, Any]],
    fallback_days: list[dict[str, Any]],
    request: dict[str, Any],
    attractions: list[dict[str, Any]],
    weather_info: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    completed = []
    by_date = {
        day.get("date"): day
        for day in plan_days
        if isinstance(day, dict) and day.get("date")
    }
    for index, fallback_day in enumerate(fallback_days):
        day = dict(by_date.get(fallback_day.get("date")) or (plan_days[index] if index < len(plan_days) and isinstance(plan_days[index], dict) else {}))
        weather = day.get("weather") or (weather_info[index] if index < len(weather_info) else fallback_day.get("weather", {}))
        day["date"] = day.get("date") or fallback_day.get("date")
        day["day_number"] = day.get("day_number") or fallback_day.get("day_number") or index + 1
        day["theme"] = day.get("theme") or fallback_day.get("theme") or f"Day {index + 1}"
        day["weather"] = weather
        day["weather_suggestion"] = day.get("weather_suggestion") or _weather_suggestion(weather)
        day["activities"] = _complete_activities(
            day.get("activities") or [],
            fallback_day.get("activities") or [],
            request,
            attractions,
            weather,
        )
        completed.append(day)
    return completed


def _complete_activities(
    activities: list[dict[str, Any]],
    fallback_activities: list[dict[str, Any]],
    request: dict[str, Any],
    attractions: list[dict[str, Any]],
    weather: dict[str, Any],
) -> list[dict[str, Any]]:
    normalized = [
        _normalize_activity(activity, request, attractions, weather)
        for activity in activities
        if isinstance(activity, dict) and activity.get("title")
    ]

    if _needs_activity_completion(normalized):
        seen = {_activity_signature(activity) for activity in normalized}
        for fallback in fallback_activities:
            if _is_duplicate_fallback_activity(fallback, normalized):
                continue
            signature = _activity_signature(fallback)
            if signature in seen:
                continue
            normalized.append(dict(fallback))
            seen.add(signature)
            if not _needs_activity_completion(normalized):
                break

    if _needs_activity_completion(normalized):
        normalized = [dict(activity) for activity in fallback_activities]

    return sorted(normalized, key=_activity_sort_key)


def _normalize_activity(
    activity: dict[str, Any],
    request: dict[str, Any],
    attractions: list[dict[str, Any]],
    weather: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(activity)
    normalized["period"] = normalized.get("period") or _period_from_time(normalized.get("time"))
    normalized["type"] = _normalize_activity_type(normalized.get("type"), normalized.get("title"), normalized.get("reason"))
    if normalized["type"] == "food":
        normalized["title"] = _clean_meal_title(normalized.get("title"), request.get("city"))
    matched = _find_activity_attraction(normalized, attractions)
    if matched and normalized["type"] not in {"food", "meal", "rest", "transport", "hotel"}:
        normalized["type"] = "attraction"
        normalized.setdefault("poi_id", matched.get("id"))
        normalized.setdefault("location", matched.get("location"))
        normalized.setdefault("address", matched.get("address"))
        normalized.setdefault("transport", request.get("transport_preference", "public_transit"))
    normalized.setdefault("duration", _default_duration(normalized["period"], normalized["type"]))
    if normalized.get("budget") is None:
        if normalized["type"] == "food":
            profile = _budget_profile(request.get("budget_range", "medium"))
            normalized["budget"] = profile[_meal_kind(normalized)]
        elif matched:
            normalized["budget"] = _activity_ticket_budget(matched, request.get("budget_range", "medium"))
        else:
            normalized["budget"] = 0
    if not isinstance(normalized.get("tags"), list):
        normalized["tags"] = [str(normalized["tags"])] if normalized.get("tags") else []
    normalized["tags"] = _clean_activity_tags(normalized["tags"], normalized["type"])
    if matched:
        for tag in _activity_tags(matched, weather):
            if tag not in normalized["tags"]:
                normalized["tags"].append(tag)
    normalized.setdefault("reason", "结合时间、天气、预算和动线安排")
    return normalized


def _normalize_activity_type(raw_type: Any, title: Any, reason: Any) -> str:
    value = str(raw_type or "").strip().lower()
    text = f"{title or ''} {reason or ''}".lower()
    if any(token in value for token in ("intercity", "flight", "rail", "train", "高铁", "飞机", "往返")):
        return "intercity_transport"
    if any(token in value for token in ("food", "meal", "breakfast", "lunch", "dinner", "餐")):
        return "food"
    if value in {"hotel", "lodging", "stay", "住宿", "酒店"}:
        return "hotel"
    if any(token in value for token in ("transport", "transit", "drive", "walking", "route", "交通", "转场")):
        return "transport"
    if _looks_like_transport_text(text):
        return "transport"
    if value in {"rest", "free_time", "activity"}:
        return value
    return value or "activity"


def _looks_like_transport_text(text: str) -> bool:
    if not text:
        return False
    transport_tokens = ("前往", "出发", "抵达", "转场", "公交", "地铁", "打车", "步行", "公共交通", "路线")
    return any(token in text for token in transport_tokens) and any(token in text for token in ("→", "到", "酒店", "景点", "广场", "博物馆", "公园"))


def _clean_meal_title(title: Any, city: Any) -> str:
    text = str(title or "").strip()
    city_text = str(city or "").strip()
    if not text:
        return "用餐与休息"
    if city_text:
        text = text.replace(city_text, "").strip()
    if text in {"本地早餐", "当地早餐", "特色早餐", "早餐"}:
        return "早餐与出发准备"
    if text in {"本地午餐", "当地午餐", "特色午餐", "午餐"}:
        return "午餐与休息"
    if text in {"本地晚餐", "当地晚餐", "特色晚餐", "晚餐"}:
        return "晚餐与自由活动"
    return text


def _clean_activity_tags(tags: list[Any], activity_type: str) -> list[str]:
    cleaned = []
    for tag in tags:
        text = str(tag).strip()
        if not text:
            continue
        if activity_type == "food" and text in {"本地特色", "当地特色"}:
            continue
        if text not in cleaned:
            cleaned.append(text)
    return cleaned


def _needs_activity_completion(activities: list[dict[str, Any]]) -> bool:
    core_activities = [activity for activity in activities if activity.get("type") != "transport"]
    periods = {activity.get("period") for activity in core_activities}
    expected_meals = set(_expected_meal_kinds_for_activities(core_activities))
    has_expected_meals = _meal_kinds(core_activities) >= expected_meals
    return len(core_activities) < 4 or not {"afternoon", "evening"}.intersection(periods) or not has_expected_meals


def _is_duplicate_fallback_activity(fallback: dict[str, Any], activities: list[dict[str, Any]]) -> bool:
    fallback_type = fallback.get("type")
    fallback_period = fallback.get("period")
    if fallback_type == "food":
        return any(activity.get("type") == "food" and activity.get("period") == fallback_period for activity in activities)
    return False


def _find_activity_attraction(activity: dict[str, Any], attractions: list[dict[str, Any]]) -> dict[str, Any] | None:
    poi_id = activity.get("poi_id")
    if poi_id:
        for attraction in attractions:
            if attraction.get("id") == poi_id:
                return attraction
    title = activity.get("title") or ""
    for attraction in attractions:
        name = attraction.get("name") or ""
        if name and (name in title or title in name):
            return attraction
    return None


def _period_from_time(time_text: Any) -> str:
    minutes = _time_start_minutes(time_text)
    if minutes is None:
        return "morning"
    hour = minutes // 60
    if hour < 12:
        return "morning"
    if hour < 14:
        return "lunch"
    if hour < 18:
        return "afternoon"
    return "evening"


def _default_duration(period: str, activity_type: str) -> str:
    if activity_type == "food":
        meal_kind = _meal_kind({"period": period})
        if meal_kind == "breakfast":
            return "45分钟"
        return "1.5小时" if meal_kind == "lunch" else "2小时"
    if period == "morning":
        return "2小时"
    if period == "afternoon":
        return "2.5小时"
    return "1.5小时"


def _meal_kind(activity: dict[str, Any]) -> str:
    explicit = str(activity.get("meal_kind") or "").lower()
    if explicit in {"breakfast", "lunch", "dinner"}:
        return explicit
    period = str(activity.get("period") or "").lower()
    title = str(activity.get("title") or activity.get("name") or "")
    tags = " ".join(str(tag) for tag in activity.get("tags", []) if tag) if isinstance(activity.get("tags"), list) else ""
    text = f"{title} {tags}"
    start = _time_start_minutes(activity.get("start_time") or activity.get("time"))
    if "早餐" in text or "breakfast" in text.lower() or (period == "morning" and (start is None or start < 10 * 60)):
        return "breakfast"
    if "午餐" in text or "lunch" in text.lower() or period == "lunch" or (start is not None and 10 * 60 <= start < 15 * 60):
        return "lunch"
    return "dinner"


def _meal_kinds(activities: list[dict[str, Any]]) -> set[str]:
    return {_meal_kind(activity) for activity in activities if activity.get("type") == "food"}


def _activity_signature(activity: dict[str, Any]) -> str:
    return str(activity.get("poi_id") or activity.get("title") or "").strip().lower()


def _activity_sort_key(activity: dict[str, Any]) -> tuple[int, str]:
    time_text = str(activity.get("time") or "")
    minutes = _time_start_minutes(time_text)
    if minutes is None:
        return (24 * 60, "")
    return (minutes, time_text)


def _normalize_budget(
    budget: Any,
    days: list[dict[str, Any]],
    request: dict[str, Any],
    hotel: dict[str, Any],
) -> dict[str, Any]:
    computed = _build_budget(days, request, hotel)
    if isinstance(budget, dict):
        for key, value in budget.items():
            if key not in {"range", "estimated_total", "breakdown", "per_day", "assumptions"}:
                computed[key] = value
    return computed


def normalize_plan_budget(
    budget: Any,
    days: list[dict[str, Any]],
    request: dict[str, Any],
    hotel: dict[str, Any],
) -> dict[str, Any]:
    return _normalize_budget(budget, days, request, hotel)


def enrich_meals_with_restaurants(
    days: list[dict[str, Any]],
    city: str,
    budget_range: str,
    accommodation_preference: str = "",
) -> list[dict[str, Any]]:
    if not days:
        return days

    enriched: list[dict[str, Any]] = []
    for day in days:
        if not isinstance(day, dict):
            enriched.append(day)
            continue

        activities = _ensure_daily_meal_activities(
            [dict(activity) for activity in day.get("activities", []) if isinstance(activity, dict)],
            city,
            budget_range,
            accommodation_preference,
        )
        next_activities: list[dict[str, Any]] = []
        for index, activity in enumerate(activities):
            if activity.get("type") == "food" and _meal_kind(activity) == "breakfast" and _accommodation_includes_breakfast(accommodation_preference):
                activity = {
                    **activity,
                    "title": "酒店早餐",
                    "poi_id": None,
                    "location": None,
                    "address": None,
                    "budget": 0,
                    "tags": ["餐饮", "含早"],
                    "reason": "住宿偏好包含早餐，早餐安排在酒店内完成，减少清晨额外转场。",
                }
                next_activities.append(activity)
                continue
            if activity.get("type") == "food" and not _normalize_location(activity.get("location")):
                restaurant = _find_restaurant_for_meal(city, activities, index)
                activity = _meal_activity_from_restaurant(activity, restaurant, budget_range)
            next_activities.append(activity)

        day_copy = dict(day)
        day_copy["activities"] = sorted(next_activities, key=_activity_sort_key)
        enriched.append(day_copy)

    return enriched


def _ensure_daily_meal_activities(
    activities: list[dict[str, Any]],
    city: str,
    budget_range: str,
    accommodation_preference: str = "",
) -> list[dict[str, Any]]:
    existing = _meal_kinds(activities)
    expected = _expected_meal_kinds_for_activities(activities)
    missing = [kind for kind in expected if kind not in existing]
    if not missing:
        return activities

    by_kind = {
        "breakfast": ("08:00", "morning"),
        "lunch": ("12:30", "lunch"),
        "dinner": ("18:30", "evening"),
    }
    added = []
    for kind in missing:
        time, period = by_kind[kind]
        meal = _build_meal_activity(time, period, city, budget_range)
        if kind == "breakfast" and _accommodation_includes_breakfast(accommodation_preference):
            meal.update(
                {
                    "title": "酒店早餐",
                    "poi_id": None,
                    "location": None,
                    "address": None,
                    "budget": 0,
                    "tags": ["餐饮", "含早"],
                    "reason": "住宿偏好包含早餐，早餐安排在酒店内完成，减少清晨额外转场。",
                }
            )
        added.append(meal)
    return sorted(_dedupe_meal_activities([*activities, *added]), key=_activity_sort_key)


def _expected_meal_kinds_for_activities(activities: list[dict[str, Any]]) -> list[str]:
    nodes = [_activity_as_time_node(activity) for activity in activities]
    return _expected_meal_kinds_for_nodes(nodes, 0)


def _activity_as_time_node(activity: dict[str, Any]) -> dict[str, Any]:
    node = dict(activity)
    node["start_time"] = node.get("start_time") or _time_start_text(str(node.get("time") or ""))
    node["end_time"] = node.get("end_time") or _time_end_text(str(node.get("time") or ""))
    return node


def _dedupe_meal_activities(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes = _dedupe_meal_nodes([_activity_as_time_node(activity) for activity in activities])
    for node in nodes:
        node.pop("start_time", None)
        node.pop("end_time", None)
    return nodes


def ensure_intercity_transfer_activities(
    days: list[dict[str, Any]],
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    origin = str(request.get("origin") or "").strip()
    city = str(request.get("city") or "").strip()
    if not days or not origin or not city or origin == city:
        return days

    trip = _build_intercity_trip(origin, city, request.get("budget_range", "medium"))
    enriched: list[dict[str, Any]] = []
    last_index = len(days) - 1

    for index, day in enumerate(days):
        if not isinstance(day, dict):
            enriched.append(day)
            continue

        activities = [dict(activity) for activity in day.get("activities", []) if isinstance(activity, dict)]
        if index == 0 and not _has_intercity_activity(activities, "outbound"):
            activities.insert(0, _build_intercity_activity(trip, "outbound"))
        if index == last_index and not _has_intercity_activity(activities, "return"):
            activities.append(_build_intercity_activity(trip, "return"))

        day_copy = dict(day)
        day_copy["activities"] = sorted(activities, key=_activity_sort_key)
        enriched.append(day_copy)

    return enriched


def _find_restaurant_for_meal(city: str, activities: list[dict[str, Any]], index: int) -> dict[str, Any]:
    meal_kind = _meal_kind(activities[index])
    anchor = _meal_anchor_activity(activities, index)
    anchor_location = _normalize_location(anchor.get("location")) if anchor else None

    try:
        use_real_amap = _should_use_real("amap")
    except Exception:
        use_real_amap = False

    if use_real_amap:
        try:
            pois = _amap_place_around(
                city=city,
                location=anchor_location,
                keywords=_meal_search_keywords(city, meal_kind),
                types="050000",
                offset=8,
            )
            if pois:
                return _normalize_poi(pois[0], fallback_type="food")
        except Exception:
            pass

    return _mock_restaurant(city, anchor_location, index, meal_kind)


def _meal_search_keywords(city: str, meal_kind: str) -> str:
    if meal_kind == "breakfast":
        return f"{city} 早餐 早点"
    if meal_kind == "lunch":
        return f"{city} 午餐 餐厅 美食"
    return f"{city} 晚餐 餐厅 美食"


def _meal_anchor_activity(activities: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    for activity in reversed(activities[:index]):
        if _normalize_location(activity.get("location")) and activity.get("type") in {"attraction", "hotel"}:
            return activity
    for activity in activities[index + 1:]:
        if _normalize_location(activity.get("location")) and activity.get("type") in {"attraction", "hotel"}:
            return activity
    return None


def _meal_activity_from_restaurant(
    activity: dict[str, Any],
    restaurant: dict[str, Any],
    budget_range: str,
) -> dict[str, Any]:
    profile = _budget_profile(budget_range)
    meal_kind = _meal_kind(activity)
    title = restaurant.get("name") or {"breakfast": "早餐餐馆", "lunch": "午餐餐馆", "dinner": "晚餐餐馆"}[meal_kind]
    return {
        **activity,
        "title": title,
        "type": "food",
        "meal_kind": meal_kind,
        "poi_id": restaurant.get("id") or restaurant.get("poi_id"),
        "location": restaurant.get("location"),
        "address": restaurant.get("address"),
        "reason": "按当天动线选择附近真实餐馆，方便从上一站前往并继续衔接下一站。",
        "budget": activity.get("budget") if activity.get("budget") is not None else profile[meal_kind],
        "tags": _restaurant_tags(restaurant, meal_kind),
    }


def _restaurant_tags(restaurant: dict[str, Any], meal_kind: str) -> list[str]:
    tags = [{"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}[meal_kind], "餐馆"]
    category = restaurant.get("category")
    if isinstance(category, str):
        tags.extend(part for part in category.replace(";", "|").split("|") if part and part not in tags)
    rating = restaurant.get("rating")
    if rating:
        tags.append(f"评分 {rating}")
    return tags[:5]


def _mock_restaurant(city: str, anchor_location: dict[str, float] | None, index: int, meal_kind: str = "lunch") -> dict[str, Any]:
    base_lng = anchor_location.get("lng") if anchor_location else 121.48
    base_lat = anchor_location.get("lat") if anchor_location else 31.23
    offset = 0.002 + index * 0.0003
    names = {
        "breakfast": "顺路早餐铺",
        "lunch": "本地家常菜馆",
        "dinner": "城市晚餐小馆",
    }
    name = names.get(meal_kind, "街区简餐店")
    return {
        "id": f"mock-{city}-restaurant-{index}",
        "name": f"{city}{name}",
        "type": "food",
        "category": "餐饮服务|中餐厅",
        "address": f"{city}景区周边",
        "location": {"lng": base_lng + offset, "lat": base_lat + offset},
        "rating": 4.6,
        "source": "mock",
    }


def _has_intercity_activity(activities: list[dict[str, Any]], direction: str) -> bool:
    return any(activity.get("type") == "intercity_transport" and activity.get("direction") == direction for activity in activities)


def _build_intercity_trip(origin: str, city: str, budget_range: str) -> dict[str, Any]:
    distance_km = _intercity_distance_km(origin, city)
    mode = _intercity_mode(distance_km)
    duration_minutes = _intercity_duration_minutes(distance_km, mode)
    return {
        "origin": origin,
        "city": city,
        "mode": mode,
        "mode_label": _intercity_mode_label(mode),
        "duration_minutes": duration_minutes,
        "budget": _intercity_budget(mode, budget_range),
        "distance_km": distance_km,
    }


def _build_intercity_activity(trip: dict[str, Any], direction: str) -> dict[str, Any]:
    is_outbound = direction == "outbound"
    start = 6 * 60 + 30 if is_outbound else 19 * 60
    end = start + int(trip["duration_minutes"])
    origin = trip["origin"] if is_outbound else trip["city"]
    destination = trip["city"] if is_outbound else trip["origin"]
    action = "抵达" if is_outbound else "返程"
    return {
        "time": f"{_format_minutes(start)}-{_format_minutes(end)}",
        "period": "morning" if is_outbound else "evening",
        "title": f"{origin} → {destination} {trip['mode_label']}{action}",
        "type": "intercity_transport",
        "direction": direction,
        "mode": trip["mode"],
        "reason": "根据出发地和目的地距离估算往返大交通，方便把抵达和返程时间纳入整体行程。",
        "duration": _format_duration_minutes(int(trip["duration_minutes"])),
        "budget": trip["budget"],
        "tags": [trip["mode_label"], "往返大交通"],
    }


def _intercity_distance_km(origin: str, city: str) -> float | None:
    try:
        if not _should_use_real("amap"):
            return None
        origin_location = _amap_geocode_location(origin)
        city_location = _amap_geocode_location(city)
        if origin_location and city_location:
            return _haversine_km(origin_location, city_location)
    except Exception:
        return None
    return None


def _intercity_mode(distance_km: float | None) -> str:
    if distance_km is None:
        return "rail_or_flight"
    if distance_km >= 1000:
        return "flight"
    return "rail"


def _intercity_mode_label(mode: str) -> str:
    if mode == "flight":
        return "飞机"
    if mode == "rail":
        return "高铁"
    return "高铁/飞机"


def _intercity_duration_minutes(distance_km: float | None, mode: str) -> int:
    if mode == "flight":
        return 210
    if mode == "rail":
        if distance_km is None:
            return 150
        return int(max(90, min(360, distance_km / 250 * 60 + 45)))
    return 150


def _intercity_budget(mode: str, budget_range: str) -> int:
    profile = str(budget_range or "").lower()
    if mode == "flight":
        if any(token in profile for token in ("low", "经济", "低")):
            return 650
        if any(token in profile for token in ("high", "高", "品质")):
            return 1200
        return 850
    if any(token in profile for token in ("low", "经济", "低")):
        return 280
    if any(token in profile for token in ("high", "高", "品质")):
        return 650
    return 420


def ensure_hotel_evening_activities(
    days: list[dict[str, Any]],
    hotel: dict[str, Any],
) -> list[dict[str, Any]]:
    if not days or not isinstance(hotel, dict) or not hotel.get("name"):
        return days

    nights = max(len(days) - 1, 0)
    if nights <= 0:
        return days

    enriched: list[dict[str, Any]] = []
    for index, day in enumerate(days):
        if not isinstance(day, dict):
            enriched.append(day)
            continue

        day_copy = dict(day)
        activities = [dict(activity) for activity in day.get("activities", []) if isinstance(activity, dict)]
        if index < nights and not _has_hotel_activity(activities, hotel):
            activities.append(_build_hotel_activity(activities, hotel))
        day_copy["activities"] = sorted(activities, key=_activity_sort_key)
        enriched.append(day_copy)

    return enriched


def _has_hotel_activity(activities: list[dict[str, Any]], hotel: dict[str, Any]) -> bool:
    hotel_id = str(hotel.get("id") or "")
    for activity in activities:
        if activity.get("type") == "hotel":
            return True
        poi_id = str(activity.get("poi_id") or "")
        if hotel_id and poi_id == hotel_id:
            return True
    return False


def _build_hotel_activity(activities: list[dict[str, Any]], hotel: dict[str, Any]) -> dict[str, Any]:
    start = _hotel_start_time(activities)
    end = min(start + 30, 23 * 60)
    return {
        "time": f"{_format_minutes(start)}-{_format_minutes(end)}",
        "period": "evening",
        "title": f"入住/返回 {hotel.get('name')}",
        "type": "hotel",
        "poi_id": hotel.get("id"),
        "location": hotel.get("location"),
        "address": hotel.get("address") or hotel.get("location_name"),
        "reason": "把住宿安排放在前一晚，方便第二天从酒店出发并衔接后续路线。",
        "duration": "30分钟",
        "budget": _safe_int(hotel.get("price_per_night")) or 0,
        "tags": ["住宿", "酒店"],
    }


def _hotel_start_time(activities: list[dict[str, Any]]) -> int:
    latest_end = max((_time_end_minutes(activity.get("time")) or 0 for activity in activities), default=0)
    return max(20 * 60 + 30, min(latest_end + 30, 22 * 60 + 30))


def enrich_days_with_routes(
    days: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    transport_preference: str,
    budget_range: str,
) -> list[dict[str, Any]]:
    if not days or not routes:
        return days

    routes_by_day: dict[str, list[dict[str, Any]]] = {}
    for route in routes:
        if not isinstance(route, dict):
            continue
        day_key = str(route.get("day") or "")
        routes_by_day.setdefault(day_key, []).append(route)

    enriched = []
    for day in days:
        if not isinstance(day, dict):
            enriched.append(day)
            continue

        day_copy = dict(day)
        activities = [dict(activity) for activity in day.get("activities", []) if isinstance(activity, dict)]
        activities = [
            activity
            for activity in activities
            if activity.get("type") != "transport" and not _looks_like_transport_activity(activity)
        ]
        day_routes = routes_by_day.get(str(day.get("date") or ""), [])
        day_copy["activities"] = _insert_transport_activities(
            activities,
            day_routes,
            transport_preference,
            budget_range,
        )
        enriched.append(day_copy)

    return enriched


def _insert_transport_activities(
    activities: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    transport_preference: str,
    budget_range: str,
) -> list[dict[str, Any]]:
    if not activities or not routes:
        return activities

    remaining_routes = list(routes)
    result: list[dict[str, Any]] = []
    previous_activity: dict[str, Any] | None = None
    for activity in sorted(activities, key=_activity_sort_key):
        activity = dict(activity)
        if activity.get("type") == "intercity_transport" and previous_activity:
            previous_end = _time_end_minutes(previous_activity.get("time"))
            if previous_end is not None:
                activity = _shift_activity_to_start(activity, previous_end + 30)
        route = _pop_route_to_activity(activity, remaining_routes) if _is_route_destination_activity(activity) else None
        if route:
            duration_minutes = _route_duration_minutes(route)
            route_time = _route_time_range(previous_activity, activity, duration_minutes)
            route_end = _time_end_minutes(route_time)
            if route_end is not None:
                activity = _shift_activity_to_start(activity, route_end + 5)
            result.append(
                _route_to_activity(
                    route,
                    activity,
                    previous_activity,
                    transport_preference,
                    budget_range,
                    time_text=route_time,
                    duration_minutes=duration_minutes,
                )
            )
        result.append(activity)
        if activity.get("type") in {"attraction", "hotel", "food", "intercity_transport"}:
            previous_activity = activity
    return sorted(result, key=_activity_sort_key)


def _is_route_destination_activity(activity: dict[str, Any]) -> bool:
    if activity.get("type") == "food" and not _normalize_location(activity.get("location")):
        return False
    return activity.get("type") in {"attraction", "hotel", "food"} and bool(activity.get("title") or activity.get("poi_id"))


def _looks_like_transport_activity(activity: dict[str, Any]) -> bool:
    if activity.get("type") == "transport":
        return True
    if activity.get("type") in {"food", "hotel", "intercity_transport"}:
        return False
    return _looks_like_transport_text(f"{activity.get('title') or ''} {activity.get('reason') or ''}".lower())


def _pop_route_to_activity(activity: dict[str, Any], routes: list[dict[str, Any]]) -> dict[str, Any] | None:
    title = str(activity.get("title") or "")
    poi_id = str(activity.get("poi_id") or "")
    for index, route in enumerate(routes):
        destination = str(route.get("to") or "")
        destination_id = str(route.get("to_id") or "")
        if (poi_id and destination_id == poi_id) or (destination and title and (destination in title or title in destination)):
            return routes.pop(index)
    if activity.get("type") == "attraction" and routes:
        return routes.pop(0)
    return None


def _route_to_activity(
    route: dict[str, Any],
    next_activity: dict[str, Any],
    previous_activity: dict[str, Any] | None,
    transport_preference: str,
    budget_range: str,
    *,
    time_text: str | None = None,
    duration_minutes: int | None = None,
) -> dict[str, Any]:
    mode = route.get("mode") or _route_mode(transport_preference)
    duration_minutes = duration_minutes or _route_duration_minutes(route)
    arrival_time = next_activity.get("time") if isinstance(next_activity.get("time"), str) else ""
    return {
        "time": time_text or _route_time_range(previous_activity, next_activity, duration_minutes),
        "period": next_activity.get("period") or _period_from_time(arrival_time),
        "title": f"{route.get('from') or '上一站'} → {route.get('to') or next_activity.get('title') or '下一站'}",
        "type": "transport",
        "source": "route",
        "mode": mode,
        "reason": _route_reason(route, mode),
        "duration": f"{duration_minutes}分钟",
        "budget": _route_budget(route, mode, budget_range),
        "tags": [_route_mode_label(mode), "转场方案"],
    }


def _route_duration_minutes(route: dict[str, Any]) -> int:
    return max(5, round((_safe_int(route.get("duration_s")) or 900) / 60))


def _route_time_range(
    previous_activity: dict[str, Any] | None,
    next_activity: dict[str, Any],
    duration_minutes: int,
) -> str:
    next_start = _time_start_minutes(next_activity.get("time"))
    previous_end = _time_end_minutes(previous_activity.get("time")) if previous_activity else None
    buffer = 5

    if next_start is not None:
        start = max(0, next_start - duration_minutes)
        if previous_end is not None and start < previous_end + buffer:
            start = previous_end + buffer
        return f"{_format_minutes(start)}-{_format_minutes(start + duration_minutes)}"

    if previous_end is not None:
        start = previous_end + buffer
        return f"{_format_minutes(start)}-{_format_minutes(start + duration_minutes)}"

    return "--:--"


def _shift_activity_to_start(activity: dict[str, Any], min_start: int) -> dict[str, Any]:
    current_start = _time_start_minutes(activity.get("time"))
    if current_start is not None and current_start >= min_start:
        return activity

    duration = _activity_duration_minutes(activity)
    shifted = dict(activity)
    shifted["time"] = f"{_format_minutes(min_start)}-{_format_minutes(min_start + duration)}"
    shifted["period"] = _period_from_time(shifted["time"])
    return shifted


def _activity_duration_minutes(activity: dict[str, Any]) -> int:
    start = _time_start_minutes(activity.get("time"))
    end = _time_end_minutes(activity.get("time"))
    if start is not None and end is not None and end > start:
        return end - start

    duration_text = str(activity.get("duration") or "")
    duration_from_text = _duration_text_minutes(duration_text)
    if duration_from_text:
        return duration_from_text

    activity_type = str(activity.get("type") or "")
    if activity_type == "food":
        return 60
    if activity_type == "hotel":
        return 30
    if activity_type == "intercity_transport":
        return 150
    return 90


def _duration_text_minutes(text: str) -> int | None:
    if not text:
        return None
    hours = 0
    minutes = 0
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:小时|h)", text, re.IGNORECASE)
    minute_match = re.search(r"(\d+)\s*(?:分钟|min)", text, re.IGNORECASE)
    if hour_match:
        hours = int(float(hour_match.group(1)) * 60)
    if minute_match:
        minutes = int(minute_match.group(1))
    total = hours + minutes
    return total or None


def _route_reason(route: dict[str, Any], mode: str) -> str:
    distance = _safe_int(route.get("distance_m"))
    distance_text = f"约 {distance / 1000:.1f} 公里，" if distance else ""
    return f"{distance_text}建议{_route_mode_label(mode)}前往，给下一站预留稳定转场时间。"


def _route_budget(route: dict[str, Any], mode: str, budget_range: str) -> int:
    distance_km = max((_safe_int(route.get("distance_m")) or 0) / 1000, 0)
    if mode == "walking":
        return 0
    if mode == "driving":
        base = 14 if "low" not in str(budget_range).lower() else 12
        return int(round(base + distance_km * 2.6))
    if distance_km <= 6:
        return 4
    if distance_km <= 12:
        return 6
    return 8


def _route_mode_label(mode: str) -> str:
    if mode == "walking":
        return "步行"
    if mode == "driving":
        return "打车"
    return "公交地铁"


def _time_start_minutes(time_text: Any) -> int | None:
    if not isinstance(time_text, str) or ":" not in time_text:
        return None
    first_part = time_text.split("-", 1)[0].strip()
    if ":" not in first_part:
        return None
    hour_text, minute_text = first_part.split(":", 1)
    hour = _safe_int(hour_text)
    minute = _safe_int(minute_text[:2])
    if hour is None or minute is None:
        return None
    return hour * 60 + minute


def _time_end_minutes(time_text: Any) -> int | None:
    if not isinstance(time_text, str) or ":" not in time_text:
        return None
    if "-" not in time_text:
        return _time_start_minutes(time_text)
    second_part = time_text.split("-", 1)[1].strip()
    if ":" not in second_part:
        return _time_start_minutes(time_text)
    hour_text, minute_text = second_part.split(":", 1)
    hour = _safe_int(hour_text)
    minute = _safe_int(minute_text[:2])
    if hour is None or minute is None:
        return _time_start_minutes(time_text)
    return hour * 60 + minute


def _format_minutes(total: int) -> str:
    total = max(0, total)
    return f"{total // 60:02d}:{total % 60:02d}"


def _format_duration_minutes(total: int) -> str:
    if total < 60:
        return f"{total}分钟"
    hours = total // 60
    minutes = total % 60
    return f"{hours}小时{minutes}分钟" if minutes else f"{hours}小时"


PLACE_NODE_TYPES = {"attraction", "food", "hotel", "rest", "intercity_transport"}
NON_TRANSPORT_PLACE_TYPES = {"attraction", "food", "hotel", "rest", "intercity_transport"}
FOOD_PLACEHOLDER_TOKENS = (
    "本地早餐",
    "当地早餐",
    "特色早餐",
    "早餐与出发准备",
    "早餐",
    "本地午餐",
    "当地午餐",
    "特色午餐",
    "午餐与休息",
    "午餐",
    "本地晚餐",
    "当地晚餐",
    "晚餐与自由活动",
    "晚餐",
)


def validate_and_repair_plan(
    plan: dict[str, Any],
    request: dict[str, Any],
    hotel: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    repaired = dict(plan)
    warnings: list[str] = []
    days = repaired.get("days") if isinstance(repaired.get("days"), list) else []
    normalized_days: list[dict[str, Any]] = []
    for day_index, day in enumerate(days):
        if not isinstance(day, dict):
            continue
        day_copy = dict(day)
        nodes = _nodes_from_day(day_copy, day_index)
        nodes = _remove_legacy_transport_nodes(nodes)
        nodes = _add_intercity_nodes(nodes, request, hotel, day_index, len(days), warnings)
        nodes = _remove_unrealistic_hotel_nodes(nodes, day_index, len(days))
        nodes = _remove_unexpected_meal_nodes(nodes, day_index, len(days))
        nodes = _ensure_daily_meal_nodes(nodes, request, day_index, len(days))
        nodes = _dedupe_meal_nodes(nodes)
        nodes = _repair_food_nodes(nodes, request, warnings)
        nodes = _repair_node_times(nodes, day_index, len(days))
        nodes = _insert_node_transports(nodes, request)
        nodes = _repair_node_times(nodes, day_index, len(days), lock_existing_order=True)
        nodes = _ensure_required_return_node(nodes, request, hotel, day_index, len(days), warnings)
        nodes = [_normalize_node(node, index + 1) for index, node in enumerate(nodes)]
        day_copy["nodes"] = nodes
        day_copy["activities"] = [_node_to_activity(node) for node in nodes]
        normalized_days.append(day_copy)

    repaired["days"] = normalized_days
    repaired["meals"] = _extract_meals(normalized_days)
    repaired["map"] = {"points": build_map_points_from_nodes(normalized_days)}
    repaired["budget"] = _build_node_budget(normalized_days, request)
    if warnings:
        existing = repaired.get("validator_warnings") if isinstance(repaired.get("validator_warnings"), list) else []
        repaired["validator_warnings"] = [*existing, *warnings]
    return repaired, warnings


def _nodes_from_day(day: dict[str, Any], day_index: int) -> list[dict[str, Any]]:
    raw_nodes = day.get("nodes") if isinstance(day.get("nodes"), list) else day.get("activities", [])
    nodes = []
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            continue
        node = dict(raw)
        node_type = _canonical_node_type(node.get("type"), node)
        node["type"] = node_type
        time_text = str(node.get("time") or "")
        start = node.get("start_time") or _time_start_text(time_text)
        end = node.get("end_time") or _time_end_text(time_text)
        if not start:
            start = _format_minutes(9 * 60 + index * 90)
        if not end:
            end = _format_minutes(_time_text_minutes(start) + _activity_duration_minutes(node))
        node["start_time"] = start
        node["end_time"] = end
        node["id"] = node.get("id") or node.get("poi_id") or f"day{day_index + 1}-node{index + 1}"
        node["source_id"] = node.get("source_id") or node.get("poi_id") or node.get("id")
        node["title"] = node.get("title") or node.get("name") or "行程节点"
        node["location"] = _normalize_location(node.get("location"))
        node["tags"] = [str(tag) for tag in node.get("tags", []) if tag] if isinstance(node.get("tags"), list) else []
        node["reason"] = node.get("reason") or "结合动线、预算和时间安排。"
        node["budget"] = _safe_int(node.get("budget")) or 0
        nodes.append(node)
    return sorted(nodes, key=lambda item: _time_text_minutes(str(item.get("start_time") or "23:59")))


def _canonical_node_type(value: Any, node: dict[str, Any]) -> str:
    raw = str(value or "").lower()
    title = str(node.get("title") or node.get("name") or "").lower()
    text = f"{raw} {title}"
    if "intercity" in text or "flight" in text or "rail" in text or "高铁" in text or "飞机" in text or "往返" in text:
        return "intercity_transport"
    if "transport" in text or "transit" in text or "drive" in text or "交通" in text or "转场" in text:
        return "transport"
    if "hotel" in text or "住宿" in text or "酒店" in text:
        return "hotel"
    if "food" in text or "meal" in text or "餐" in text:
        return "food"
    if "rest" in text or "休息" in text or "自由" in text:
        return "rest"
    return "attraction"


def _remove_legacy_transport_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [node for node in nodes if node.get("type") != "transport"]


def _repair_food_nodes(nodes: list[dict[str, Any]], request: dict[str, Any], warnings: list[str]) -> list[dict[str, Any]]:
    used_ids: set[str] = set()
    repaired = []
    for index, node in enumerate(nodes):
        node = dict(node)
        if node.get("type") == "food":
            title = str(node.get("title") or "")
            if _meal_kind(node) == "breakfast" and _accommodation_includes_breakfast(str(request.get("accommodation_preference") or "")):
                node.update(
                    {
                        "title": "酒店早餐",
                        "poi_id": None,
                        "source_id": node.get("source_id") or node.get("id"),
                        "location": None,
                        "address": None,
                        "budget": 0,
                        "tags": ["餐饮", "含早"],
                        "reason": "住宿偏好包含早餐，早餐安排在酒店内完成，减少清晨额外转场。",
                    }
                )
                repaired.append(node)
                continue
            if _is_placeholder_meal(title) or not _normalize_location(node.get("location")):
                restaurant = _find_restaurant_between_nodes(str(request.get("city") or ""), nodes, index, used_ids)
                if restaurant:
                    node = _meal_activity_from_restaurant(node, restaurant, str(request.get("budget_range") or "medium"))
                    node["type"] = "food"
                    node["start_time"] = node.get("start_time") or _time_start_text(str(node.get("time") or ""))
                    node["end_time"] = node.get("end_time") or _time_end_text(str(node.get("time") or ""))
                else:
                    node["type"] = "rest"
                    node["title"] = "用餐与休息"
                    node["budget"] = 0
                    node["tags"] = ["休息"]
                    warnings.append("餐饮 POI 不足，已降级为休息节点。")
            poi_id = str(node.get("poi_id") or node.get("id") or "")
            if poi_id:
                used_ids.add(poi_id)
        repaired.append(node)
    return repaired


def _ensure_daily_meal_nodes(nodes: list[dict[str, Any]], request: dict[str, Any], day_index: int, total_days: int | None = None) -> list[dict[str, Any]]:
    existing = _meal_kinds(nodes)
    expected = _expected_meal_kinds_for_nodes(nodes, day_index, total_days)
    missing = [kind for kind in expected if kind not in existing]
    if not missing:
        return nodes

    window_start, window_end = _available_day_window(nodes, day_index)
    city = str(request.get("city") or "")
    budget_range = str(request.get("budget_range") or "medium")
    added = []
    for kind in missing:
        start, end, period = _meal_slot_for_window(kind, window_start, window_end)
        activity = _build_meal_activity(start, period, city, budget_range)
        if kind == "breakfast" and _accommodation_includes_breakfast(str(request.get("accommodation_preference") or "")):
            activity.update(
                {
                    "title": "酒店早餐",
                    "poi_id": None,
                    "location": None,
                    "address": None,
                    "budget": 0,
                    "tags": ["餐饮", "含早"],
                    "reason": "住宿偏好包含早餐，早餐安排在酒店内完成，减少清晨额外转场。",
                }
            )
        node = {
            **activity,
            "id": f"day{day_index + 1}-{kind}",
            "source_id": f"day{day_index + 1}-{kind}",
            "start_time": start,
            "end_time": end,
            "time": f"{start}-{end}",
        }
        added.append(node)
    return sorted([*nodes, *added], key=lambda item: _time_text_minutes(str(item.get("start_time") or item.get("time") or "23:59")))


def _meal_slot_for_window(kind: str, window_start: int, window_end: int) -> tuple[str, str, str]:
    defaults = {
        "breakfast": (8 * 60, 45, "morning"),
        "lunch": (11 * 60 + 30, 60, "lunch"),
        "dinner": (18 * 60 + 30, 60, "evening"),
    }
    preferred, duration, period = defaults[kind]
    start = max(preferred, window_start)
    if kind == "lunch" and 10 * 60 + 30 <= window_start <= 13 * 60 + 30:
        start = window_start
    if kind == "dinner" and start < 17 * 60 + 30:
        start = 18 * 60 + 30
    end = min(start + duration, window_end)
    if end - start < 30:
        end = start + duration
    return _format_minutes(start), _format_minutes(end), period


def _dedupe_meal_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_kind: dict[str, dict[str, Any]] = {}
    other_nodes: list[dict[str, Any]] = []
    for node in sorted(nodes, key=lambda item: _time_text_minutes(str(item.get("start_time") or item.get("time") or "23:59"))):
        if node.get("type") != "food":
            other_nodes.append(node)
            continue
        kind = _meal_kind(node)
        current = best_by_kind.get(kind)
        if current is None or _meal_node_score(node) > _meal_node_score(current):
            best_by_kind[kind] = node
    return sorted([*other_nodes, *best_by_kind.values()], key=lambda item: _time_text_minutes(str(item.get("start_time") or item.get("time") or "23:59")))


def _remove_unexpected_meal_nodes(nodes: list[dict[str, Any]], day_index: int, total_days: int | None = None) -> list[dict[str, Any]]:
    expected = set(_expected_meal_kinds_for_nodes(nodes, day_index, total_days))
    if not expected:
        return [node for node in nodes if node.get("type") != "food"]
    return [node for node in nodes if node.get("type") != "food" or _meal_kind(node) in expected]


def _remove_unrealistic_hotel_nodes(nodes: list[dict[str, Any]], day_index: int, total_days: int) -> list[dict[str, Any]]:
    cleaned = []
    for node in nodes:
        if node.get("type") != "hotel":
            cleaned.append(node)
            continue
        start = _time_text_minutes(str(node.get("start_time") or node.get("time") or ""))
        if day_index >= total_days - 1:
            continue
        if start < 17 * 60:
            node = _shift_node_to_start(node, 20 * 60 + 30)
        cleaned.append(node)
    return cleaned


def _meal_node_score(node: dict[str, Any]) -> tuple[int, int]:
    has_location = 1 if _normalize_location(node.get("location")) else 0
    is_placeholder = 0 if _is_placeholder_meal(str(node.get("title") or "")) else 1
    return has_location, is_placeholder


def _expected_meal_kinds_for_nodes(nodes: list[dict[str, Any]], day_index: int, total_days: int | None = None) -> list[str]:
    start, end = _available_day_window(nodes, day_index)
    expected: list[str] = []
    if start <= 9 * 60 + 30 and end >= 7 * 60 + 30:
        expected.append("breakfast")
    if start <= 13 * 60 + 30 and end >= 11 * 60 + 30:
        expected.append("lunch")
    if start <= 19 * 60 + 30 and end >= 17 * 60 + 30:
        expected.append("dinner")
    has_return = any(node.get("type") == "intercity_transport" and node.get("direction") == "return" for node in nodes)
    if total_days is not None and day_index == total_days - 1 and has_return:
        expected = [kind for kind in expected if kind != "dinner"]
    return expected


def _available_day_window(nodes: list[dict[str, Any]], day_index: int) -> tuple[int, int]:
    start = 8 * 60 if day_index == 0 else 8 * 60 + 30
    end = 21 * 60 + 30
    outbound = next(
        (node for node in nodes if node.get("type") == "intercity_transport" and node.get("direction") == "outbound"),
        None,
    )
    return_node = next(
        (node for node in nodes if node.get("type") == "intercity_transport" and node.get("direction") == "return"),
        None,
    )
    if outbound:
        start = max(start, _time_text_minutes(str(outbound.get("end_time") or outbound.get("time") or "")) + 30)
    if return_node:
        end = min(end, max(0, _time_text_minutes(str(return_node.get("start_time") or return_node.get("time") or "")) - 45))
    return start, end


def _accommodation_includes_breakfast(accommodation_preference: str) -> bool:
    value = str(accommodation_preference or "").lower()
    return "breakfast" in value or "含早" in value or "早餐" in value


def _is_placeholder_meal(title: str) -> bool:
    text = title.strip()
    return not text or any(token in text for token in FOOD_PLACEHOLDER_TOKENS)


def _find_restaurant_between_nodes(city: str, nodes: list[dict[str, Any]], index: int, used_ids: set[str]) -> dict[str, Any] | None:
    meal_kind = _meal_kind(nodes[index])
    previous_location = _nearest_location(nodes[:index], reverse=True)
    next_location = _nearest_location(nodes[index + 1 :], reverse=False)
    anchor = _midpoint_location(previous_location, next_location) or previous_location or next_location
    try:
        use_real_amap = _should_use_real("amap")
    except Exception:
        use_real_amap = False
    if use_real_amap:
        try:
            pois = _amap_place_around(city=city, location=anchor, keywords=_meal_search_keywords(city, meal_kind), types="050000", offset=12)
            ranked = sorted(
                (_normalize_poi(poi, fallback_type="food") for poi in pois),
                key=lambda poi: (
                    str(poi.get("id") or poi.get("poi_id") or "") in used_ids,
                    -(_safe_float(poi.get("rating")) or 0),
                    _distance_to_anchor(poi, anchor),
                ),
            )
            for poi in ranked:
                poi_id = str(poi.get("id") or poi.get("poi_id") or "")
                if poi.get("location") and poi_id not in used_ids and not _looks_like_lodging_poi(poi):
                    return poi
        except Exception:
            pass
    return _mock_restaurant(city, anchor, index, meal_kind)


def _nearest_location(nodes: list[dict[str, Any]], reverse: bool) -> dict[str, float] | None:
    iterable = reversed(nodes) if reverse else iter(nodes)
    for node in iterable:
        if node.get("type") in {"transport"}:
            continue
        location = _normalize_location(node.get("location"))
        if location:
            return location
    return None


def _midpoint_location(first: dict[str, float] | None, second: dict[str, float] | None) -> dict[str, float] | None:
    if first and second:
        return {"lng": (first["lng"] + second["lng"]) / 2, "lat": (first["lat"] + second["lat"]) / 2}
    return first or second


def _distance_to_anchor(poi: dict[str, Any], anchor: dict[str, float] | None) -> float:
    location = _normalize_location(poi.get("location"))
    if not location or not anchor:
        return 9999.0
    return _haversine_km(location, anchor)


def _looks_like_lodging_poi(poi: dict[str, Any]) -> bool:
    text = " ".join(str(poi.get(key) or "") for key in ("name", "category", "type", "address")).lower()
    return any(token in text for token in ("酒店", "宾馆", "旅馆", "住宿", "hotel", "inn", "lodging"))


def _add_intercity_nodes(
    nodes: list[dict[str, Any]],
    request: dict[str, Any],
    hotel: dict[str, Any],
    day_index: int,
    total_days: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    origin = str(request.get("origin") or "").strip()
    city = str(request.get("city") or "").strip()
    if not origin or not city or origin == city:
        return nodes
    cleaned = [node for node in nodes if node.get("type") != "intercity_transport"]
    existing_outbound = next(
        (
            node
            for node in nodes
            if node.get("type") == "intercity_transport" and str(node.get("direction") or "outbound") != "return"
        ),
        None,
    )
    existing_return = next(
        (
            node
            for node in nodes
            if node.get("type") == "intercity_transport" and str(node.get("direction") or "return") != "outbound"
        ),
        None,
    )
    trip = _build_intercity_trip(origin, city, str(request.get("budget_range") or "medium"))
    outbound_terminal = _terminal_poi(city, trip["mode"], destination=True, warnings=warnings)
    return_terminal = _terminal_poi(city, trip["mode"], destination=True, warnings=warnings)
    if day_index == 0:
        target = _first_location_node(cleaned) or _hotel_as_node(hotel)
        if existing_outbound:
            intercity = _normalize_intercity_node(existing_outbound, trip, "outbound", outbound_terminal)
            arrival_end = _time_text_minutes(str(intercity.get("end_time") or intercity.get("time") or ""))
        else:
            arrival_start = 8 * 60
            arrival_end = arrival_start + int(trip["duration_minutes"])
            intercity = _intercity_node(trip, "outbound", outbound_terminal, arrival_start, arrival_end)
        cleaned.insert(0, intercity)
        if target:
            min_next_start = arrival_end + 30
            cleaned = _ensure_first_visit_after(cleaned, min_next_start)
    if day_index == total_days - 1:
        departure_end = 21 * 60 + 30
        departure_start = max(18 * 60, departure_end - int(trip["duration_minutes"]))
        intercity = (
            _normalize_intercity_node(existing_return, trip, "return", return_terminal)
            if existing_return
            else _intercity_node(trip, "return", return_terminal, departure_start, departure_end)
        )
        cleaned.append(intercity)
    return cleaned


def _ensure_required_return_node(
    nodes: list[dict[str, Any]],
    request: dict[str, Any],
    hotel: dict[str, Any],
    day_index: int,
    total_days: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    if day_index != total_days - 1:
        return nodes
    origin = str(request.get("origin") or "").strip()
    city = str(request.get("city") or "").strip()
    if not origin or not city or origin == city:
        return nodes
    if any(node.get("type") == "intercity_transport" and node.get("direction") == "return" for node in nodes):
        return nodes
    trip = _build_intercity_trip(origin, city, str(request.get("budget_range") or "medium"))
    return_terminal = _terminal_poi(city, trip["mode"], destination=True, warnings=warnings)
    departure_end = 21 * 60 + 30
    departure_start = max(18 * 60, departure_end - int(trip["duration_minutes"]))
    nodes = [node for node in nodes if _time_text_minutes(str(node.get("start_time") or node.get("time") or "")) < departure_start - 30]
    nodes.append(_intercity_node(trip, "return", return_terminal, departure_start, departure_end))
    return sorted(nodes, key=lambda item: _time_text_minutes(str(item.get("start_time") or item.get("time") or "23:59")))


def _normalize_intercity_node(node: dict[str, Any], trip: dict[str, Any], direction: str, terminal: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(node)
    start = normalized.get("start_time") or _time_start_text(str(normalized.get("time") or ""))
    end = normalized.get("end_time") or _time_end_text(str(normalized.get("time") or ""))
    if not start:
        start = "08:00" if direction == "outbound" else _format_minutes(max(18 * 60, 21 * 60 + 30 - int(trip["duration_minutes"])))
    if not end:
        end = _format_minutes(_time_text_minutes(str(start)) + int(trip["duration_minutes"]))
    if direction == "return":
        start, end = _clamp_return_time(start, end, int(trip["duration_minutes"]))
    normalized.update(
        {
            "id": normalized.get("id") or f"intercity-{direction}",
            "source_id": normalized.get("source_id") or terminal.get("id"),
            "type": "intercity_transport",
            "direction": direction,
            "mode": normalized.get("mode") or trip["mode"],
            "start_time": start,
            "end_time": end,
            "time": f"{start}-{end}",
            "location": _normalize_location(normalized.get("location")) or terminal.get("location"),
            "address": normalized.get("address") or terminal.get("address"),
            "duration": normalized.get("duration") or _format_duration_minutes(max(_time_text_minutes(str(end)) - _time_text_minutes(str(start)), 0)),
            "budget": _safe_int(normalized.get("budget")) or trip["budget"],
            "tags": normalized.get("tags") if isinstance(normalized.get("tags"), list) else [trip["mode_label"], "往返大交通"],
        }
    )
    if not normalized.get("title"):
        origin = trip["origin"] if direction == "outbound" else trip["city"]
        destination = trip["city"] if direction == "outbound" else trip["origin"]
        action = "抵达" if direction == "outbound" else "返程"
        normalized["title"] = f"{origin} → {destination} {trip['mode_label']}{action}"
    normalized["reason"] = normalized.get("reason") or "按用户出发/返程时间约束安排大交通，并把可用游玩窗口留给餐饮和景点。"
    return normalized


def _clamp_return_time(start_text: str, end_text: str, fallback_duration: int) -> tuple[str, str]:
    start = _time_text_minutes(start_text)
    end = _time_text_minutes(end_text)
    duration = end - start if end > start else fallback_duration
    duration = max(45, min(duration, 6 * 60))
    latest_arrival = 23 * 60 + 30
    if end > latest_arrival:
        end = latest_arrival
        start = max(18 * 60, end - duration)
    return _format_minutes(start), _format_minutes(end)


def _terminal_poi(city: str, mode: str, destination: bool, warnings: list[str]) -> dict[str, Any]:
    keyword = f"{city}机场" if mode == "flight" else f"{city}高铁站"
    try:
        if _should_use_real("amap"):
            pois = _amap_place_text(city=city, keywords=keyword, types="150100|150200", offset=5)
            for poi in pois:
                normalized = _normalize_poi(poi, fallback_type="terminal")
                if normalized.get("location"):
                    return normalized
    except Exception:
        pass
    warnings.append(f"{city}车站/机场未匹配到真实 POI，已使用城市中心兜底。")
    use_real_geocode = False
    try:
        use_real_geocode = _should_use_real("amap")
    except Exception:
        use_real_geocode = False
    try:
        location = _amap_geocode_location(city) if use_real_geocode else None
    except Exception:
        location = None
    return {"id": f"terminal-{city}-{mode}", "name": keyword, "type": "terminal", "location": location, "address": city}


def _first_location_node(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((node for node in nodes if node.get("type") in NON_TRANSPORT_PLACE_TYPES and _normalize_location(node.get("location"))), None)


def _hotel_as_node(hotel: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(hotel, dict) or not _normalize_location(hotel.get("location")):
        return None
    return {"type": "hotel", "title": hotel.get("name"), "location": hotel.get("location"), "budget": hotel.get("price_per_night") or 0}


def _intercity_node(trip: dict[str, Any], direction: str, terminal: dict[str, Any], start: int, end: int) -> dict[str, Any]:
    is_outbound = direction == "outbound"
    origin = trip["origin"] if is_outbound else trip["city"]
    destination = trip["city"] if is_outbound else trip["origin"]
    action = "抵达" if is_outbound else "返程"
    return {
        "id": f"intercity-{direction}",
        "source_id": terminal.get("id"),
        "type": "intercity_transport",
        "direction": direction,
        "mode": trip["mode"],
        "title": f"{origin} → {destination} {trip['mode_label']}{action}",
        "start_time": _format_minutes(start),
        "end_time": _format_minutes(end),
        "location": terminal.get("location"),
        "address": terminal.get("address"),
        "reason": "按出发地与目的地距离估算大交通，并把抵达/返程时间纳入行程。",
        "duration": _format_duration_minutes(max(end - start, 0)),
        "budget": trip["budget"],
        "tags": [trip["mode_label"], "往返大交通"],
    }


def _ensure_first_visit_after(nodes: list[dict[str, Any]], min_start: int) -> list[dict[str, Any]]:
    shifted = []
    first_visit_shifted = False
    for node in nodes:
        if not first_visit_shifted and node.get("type") in {"attraction", "food", "hotel", "rest"}:
            node = _shift_node_to_start(node, min_start)
            first_visit_shifted = True
        shifted.append(node)
    return shifted


def _insert_node_transports(nodes: list[dict[str, Any]], request: dict[str, Any]) -> list[dict[str, Any]]:
    if not nodes:
        return nodes
    result: list[dict[str, Any]] = []
    previous_place: dict[str, Any] | None = None
    for node in sorted(nodes, key=lambda item: _time_text_minutes(str(item.get("start_time") or "23:59"))):
        if previous_place and _node_has_location(previous_place) and _node_has_location(node):
            if _same_node_place(previous_place, node):
                result.append(node)
                if node.get("type") in NON_TRANSPORT_PLACE_TYPES and _node_has_location(node):
                    previous_place = node
                continue
            route_node = _transport_node_between(previous_place, node, request)
            route_end = _time_text_minutes(str(route_node.get("end_time") or ""))
            node_start = _time_text_minutes(str(node.get("start_time") or ""))
            if node.get("type") == "intercity_transport" and node.get("direction") == "return":
                route_duration = _node_duration_minutes(route_node)
                route_end = max(node_start - 5, 0)
                route_start = max(route_end - route_duration, 0)
                route_node["start_time"] = _format_minutes(route_start)
                route_node["end_time"] = _format_minutes(route_end)
                route_node["time"] = f"{route_node['start_time']}-{route_node['end_time']}"
            elif node_start < route_end + 5:
                node = _shift_node_to_start(node, route_end + 5)
            result.append(route_node)
        result.append(node)
        if node.get("type") in NON_TRANSPORT_PLACE_TYPES and _node_has_location(node):
            previous_place = node
    return result


def _same_node_place(first: dict[str, Any], second: dict[str, Any]) -> bool:
    first_id = str(first.get("source_id") or first.get("poi_id") or first.get("id") or "")
    second_id = str(second.get("source_id") or second.get("poi_id") or second.get("id") or "")
    if first_id and second_id and first_id == second_id:
        return True
    first_location = _normalize_location(first.get("location"))
    second_location = _normalize_location(second.get("location"))
    if first_location and second_location and _haversine_km(first_location, second_location) < 0.05:
        return True
    first_title = str(first.get("title") or "")
    second_title = str(second.get("title") or "")
    return bool(first_title and second_title and first_title == second_title)


def _transport_node_between(previous: dict[str, Any], next_node: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    previous_location = _normalize_location(previous.get("location")) or {"lng": 0, "lat": 0}
    next_location = _normalize_location(next_node.get("location")) or previous_location
    distance_km = _haversine_km(previous_location, next_location)
    mode = _route_mode(str(request.get("transport_preference") or "public_transit"))
    duration_minutes = min(90, max(8, int(distance_km / (28 if mode == "driving" else 18) * 60) + 8))
    start = max(_time_text_minutes(str(previous.get("end_time") or previous.get("start_time") or "09:00")) + 5, 0)
    end = start + duration_minutes
    route = {
        "from": previous.get("title"),
        "to": next_node.get("title"),
        "from_id": previous.get("source_id") or previous.get("id"),
        "to_id": next_node.get("source_id") or next_node.get("id"),
        "distance_m": int(distance_km * 1000),
        "duration_s": duration_minutes * 60,
        "mode": mode,
    }
    return {
        "id": f"transport-{route['from_id']}-{route['to_id']}",
        "type": "transport",
        "title": f"{_node_display_name_for_route(previous)} → {_node_display_name_for_route(next_node)}",
        "start_time": _format_minutes(start),
        "end_time": _format_minutes(end),
        "location": next_location,
        "budget": _route_budget(route, mode, str(request.get("budget_range") or "medium")),
        "source_id": route["to_id"],
        "reason": _route_reason(route, mode),
        "duration": _format_duration_minutes(duration_minutes),
        "tags": [_route_mode_label(mode), "转场方案"],
    }


def _node_display_name_for_route(node: dict[str, Any]) -> str:
    if node.get("type") == "intercity_transport":
        address = str(node.get("address") or "").strip()
        mode = str(node.get("mode") or "")
        if address:
            return address
        if mode == "flight":
            return "机场"
        if mode in {"rail", "rail_or_flight"}:
            return "高铁站"
        return "交通枢纽"
    return str(node.get("title") or "下一站")


def _repair_node_times(
    nodes: list[dict[str, Any]],
    day_index: int,
    total_days: int,
    lock_existing_order: bool = False,
) -> list[dict[str, Any]]:
    min_start = 8 * 60 if day_index == 0 else 8 * 60 + 30
    latest_end = 21 * 60 + 30 if day_index == total_days - 1 else 22 * 60 + 30
    available_start, available_end = _available_day_window(nodes, day_index)
    min_start = max(min_start, available_start)
    return_node = next(
        (
            node
            for node in nodes
            if node.get("type") == "intercity_transport" and node.get("direction") == "return"
        ),
        None,
    )
    return_duration = _node_duration_minutes(return_node) if return_node else 0
    return_start = (
        _time_text_minutes(str(return_node.get("start_time") or return_node.get("time") or ""))
        if return_node
        else latest_end
    )
    if not return_node:
        latest_end = min(latest_end, max(available_end, min_start + 60))
    hotel_node = next((node for node in nodes if node.get("type") == "hotel"), None)
    hotel_duration = _node_duration_minutes(hotel_node) if hotel_node else 0
    hotel_start_deadline = latest_end - hotel_duration if hotel_node else latest_end
    dinner_node = next((node for node in nodes if _is_dinner_node(node)), None)
    dinner_start_deadline = 19 * 60 + 30
    regular_latest_end = max(min_start + 60, return_start - 45) if return_node else latest_end
    if dinner_node:
        regular_latest_end = min(regular_latest_end, max(min_start + 60, dinner_start_deadline - 45))
    if hotel_node and not return_node:
        regular_latest_end = min(regular_latest_end, max(min_start + 60, hotel_start_deadline - 10))
    repaired = []
    cursor = min_start
    sort_key = (
        (lambda item: _time_text_minutes(str(item.get("start_time") or item.get("time") or "23:59")))
        if lock_existing_order
        else (lambda item: _node_schedule_sort_key(item, min_start, return_start))
    )
    for node in sorted(nodes, key=sort_key):
        duration = _node_duration_minutes(node)
        meal_kind = _meal_kind(node) if node.get("type") == "food" else ""
        if meal_kind == "dinner":
            duration = min(duration, 90)
        current_start = (
            _time_text_minutes(str(node.get("start_time") or node.get("time") or ""))
            if lock_existing_order
            else _preferred_node_start(node, min_start, return_start)
        )
        start = max(current_start, cursor)
        if node.get("type") == "intercity_transport" and node.get("direction") == "outbound":
            start = current_start
        elif node.get("type") == "intercity_transport" and node.get("direction") == "return":
            start = return_start
        elif meal_kind in {"breakfast", "lunch", "dinner"}:
            latest_meal_start = _meal_latest_start(meal_kind)
            if cursor > latest_meal_start:
                continue
            start = max(cursor, min(current_start, latest_meal_start))
            if start > latest_meal_start:
                continue
        elif _is_dinner_node(node):
            if cursor > dinner_start_deadline:
                start = dinner_start_deadline
            else:
                start = max(cursor, min(current_start, dinner_start_deadline))
        elif node.get("type") == "hotel" and not return_node:
            if cursor > hotel_start_deadline:
                continue
            start = max(cursor, min(current_start, hotel_start_deadline))
        end = start + duration
        if node.get("type") not in {"intercity_transport", "hotel"} and meal_kind != "dinner" and not _is_dinner_node(node) and start >= regular_latest_end:
            continue
        if node.get("type") not in {"intercity_transport", "hotel"} and meal_kind != "dinner" and not _is_dinner_node(node) and end > regular_latest_end:
            duration = max(30, regular_latest_end - start)
            end = start + duration
        if meal_kind == "dinner" and start > dinner_start_deadline:
            continue
        if meal_kind == "dinner" and return_node and end > return_start - 10:
            duration = return_start - 10 - start
            if duration < 30:
                continue
            end = start + duration
        if end > latest_end and node.get("type") != "intercity_transport":
            duration = max(15, latest_end - start)
            if duration <= 0:
                continue
            end = start + duration
        if node.get("type") != "intercity_transport" and (start >= latest_end or end > latest_end + 1):
            continue
        node = dict(node)
        node["start_time"] = _format_minutes(start)
        node["end_time"] = _format_minutes(end)
        node["time"] = f"{node['start_time']}-{node['end_time']}"
        node["duration"] = _format_duration_minutes(duration)
        node["period"] = _period_from_time(node["start_time"])
        repaired.append(node)
        cursor = end + 5
    return repaired


def _node_schedule_sort_key(node: dict[str, Any], min_start: int, return_start: int) -> tuple[int, int]:
    node_type = node.get("type")
    if node_type == "intercity_transport" and node.get("direction") == "outbound":
        return (_time_text_minutes(str(node.get("start_time") or node.get("time") or "")), 0)
    if node_type == "food":
        kind = _meal_kind(node)
        priority = {"breakfast": 1, "lunch": 2, "dinner": 8}.get(kind, 5)
        return (_preferred_meal_start(kind, min_start), priority)
    if node_type == "hotel":
        return (20 * 60 + 30, 9)
    if node_type == "intercity_transport" and node.get("direction") == "return":
        return (return_start, 10)
    current = _time_text_minutes(str(node.get("start_time") or node.get("time") or "23:59"))
    if 10 * 60 + 30 <= min_start <= 13 * 60 + 30 and current < 13 * 60:
        return (13 * 60, 5)
    return (current, 5)


def _preferred_node_start(node: dict[str, Any], min_start: int, return_start: int) -> int:
    if node.get("type") == "food":
        return _preferred_meal_start(_meal_kind(node), min_start)
    if node.get("type") == "hotel":
        current = _time_text_minutes(str(node.get("start_time") or node.get("time") or ""))
        return max(current, 20 * 60 + 30)
    if node.get("type") == "intercity_transport" and node.get("direction") == "return":
        return return_start
    return _time_text_minutes(str(node.get("start_time") or node.get("time") or ""))


def _preferred_meal_start(kind: str, min_start: int) -> int:
    if kind == "breakfast":
        return max(min_start, 8 * 60)
    if kind == "lunch":
        return max(min_start, 11 * 60 + 30)
    if kind == "dinner":
        return max(min_start, 18 * 60 + 30)
    return min_start


def _meal_latest_start(kind: str) -> int:
    if kind == "breakfast":
        return 9 * 60 + 45
    if kind == "lunch":
        return 14 * 60
    if kind == "dinner":
        return 19 * 60 + 30
    return 21 * 60


def _normalize_node(node: dict[str, Any], order: int) -> dict[str, Any]:
    normalized = dict(node)
    normalized["location"] = _normalize_location(normalized.get("location"))
    normalized["order"] = order
    normalized["time"] = f"{normalized.get('start_time')}-{normalized.get('end_time')}"
    normalized["duration"] = normalized.get("duration") or _format_duration_minutes(_node_duration_minutes(normalized))
    return normalized


def _node_to_activity(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "time": node.get("time") or f"{node.get('start_time')}-{node.get('end_time')}",
        "period": node.get("period") or _period_from_time(node.get("start_time")),
        "type": node.get("type"),
        "meal_kind": node.get("meal_kind"),
        "title": node.get("title"),
        "poi_id": node.get("source_id") or node.get("id"),
        "location": node.get("location"),
        "address": node.get("address"),
        "reason": node.get("reason") or "",
        "duration": node.get("duration") or "",
        "budget": _safe_int(node.get("budget")) or 0,
        "tags": node.get("tags") if isinstance(node.get("tags"), list) else [],
        "mode": node.get("mode"),
        "direction": node.get("direction"),
    }


def build_map_points_from_nodes(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    seen: set[str] = set()
    for day in days:
        day_key = str(day.get("date") or "")
        order = 1
        for node in day.get("nodes", []):
            if not isinstance(node, dict) or node.get("type") in {"transport"}:
                continue
            location = _normalize_location(node.get("location"))
            if not location:
                continue
            point_type = node.get("type")
            if point_type not in {"attraction", "food", "hotel", "intercity_transport", "rest"}:
                continue
            point_id = node.get("source_id") or node.get("id") or node.get("title")
            key = f"{day_key}:{point_id}:{location['lng']},{location['lat']}"
            if key in seen:
                continue
            seen.add(key)
            points.append(
                {
                    "id": point_id,
                    "node_id": node.get("id"),
                    "name": node.get("title"),
                    "type": "transport_hub" if point_type == "intercity_transport" else point_type,
                    "address": node.get("address"),
                    "location": location,
                    "day": day_key,
                    "order": order,
                }
            )
            order += 1
    return points


def _build_node_budget(days: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "lodging": ("住宿", {"hotel"}),
        "meals": ("餐饮", {"food"}),
        "transport": ("市内交通", {"transport"}),
        "intercity": ("往返大交通", {"intercity_transport"}),
        "tickets": ("门票", {"attraction"}),
    }
    totals: dict[str, int] = {}
    per_day = []
    for day in days:
        daily: dict[str, int] = {key: 0 for key in keys}
        for node in day.get("nodes", []):
            node_type = node.get("type")
            for key, (_, types) in keys.items():
                if node_type in types:
                    daily[key] += _safe_int(node.get("budget")) or 0
        for key, value in daily.items():
            totals[key] = totals.get(key, 0) + value
        subtotal = sum(daily.values())
        per_day.append({"date": day.get("date"), **daily, "subtotal": subtotal})
    breakdown = [{"key": key, "name": name, "value": int(totals.get(key, 0))} for key, (name, _) in keys.items() if totals.get(key, 0) > 0]
    estimated_total = sum(item["value"] for item in breakdown)
    return {
        "range": request.get("budget_range", "medium"),
        "estimated_total": estimated_total,
        "breakdown": breakdown,
        "per_day": per_day,
        "assumptions": [
            "预算由最终节点序列重新汇总，合计等于各项拆解之和。",
            "大交通按距离、方式和预算档位估算；车站/机场优先使用高德地点坐标。",
        ],
    }


def _shift_node_to_start(node: dict[str, Any], min_start: int) -> dict[str, Any]:
    duration = _node_duration_minutes(node)
    shifted = dict(node)
    shifted["start_time"] = _format_minutes(min_start)
    shifted["end_time"] = _format_minutes(min_start + duration)
    shifted["time"] = f"{shifted['start_time']}-{shifted['end_time']}"
    shifted["period"] = _period_from_time(shifted["start_time"])
    return shifted


def _node_duration_minutes(node: dict[str, Any]) -> int:
    start = _time_text_minutes(str(node.get("start_time") or ""))
    end = _time_text_minutes(str(node.get("end_time") or ""))
    if end > start:
        return end - start
    return _activity_duration_minutes(node)


def _is_dinner_node(node: dict[str, Any] | None) -> bool:
    if not isinstance(node, dict) or node.get("type") != "food":
        return False
    period = str(node.get("period") or "").lower()
    title = str(node.get("title") or "")
    start = _time_text_minutes(str(node.get("start_time") or node.get("time") or ""))
    return period == "evening" or "晚餐" in title or start >= 17 * 60


def _node_has_location(node: dict[str, Any]) -> bool:
    return bool(_normalize_location(node.get("location")))


def _time_start_text(time_text: str) -> str | None:
    minutes = _time_start_minutes(time_text)
    return _format_minutes(minutes) if minutes is not None else None


def _time_end_text(time_text: str) -> str | None:
    minutes = _time_end_minutes(time_text)
    return _format_minutes(minutes) if minutes is not None else None


def _time_text_minutes(time_text: str) -> int:
    parsed = _time_start_minutes(time_text)
    return parsed if parsed is not None else 0


def _budget_profile(budget_range: str) -> dict[str, Any]:
    value = str(budget_range or "").lower()
    if any(token in value for token in ("low", "budget", "经济", "低", "省钱", "实惠")):
        return {
            "breakfast": 25,
            "lunch": 45,
            "dinner": 65,
            "ticket": 30,
            "museum_ticket": 0,
            "premium_ticket": 100,
            "transport_day": 45,
            "buffer_rate": 0.08,
        }
    if any(token in value for token in ("high", "luxury", "高", "品质", "豪华")):
        return {
            "breakfast": 70,
            "lunch": 120,
            "dinner": 180,
            "ticket": 100,
            "museum_ticket": 50,
            "premium_ticket": 260,
            "transport_day": 160,
            "buffer_rate": 0.15,
        }
    return {
        "breakfast": 40,
        "lunch": 70,
        "dinner": 110,
        "ticket": 60,
        "museum_ticket": 20,
        "premium_ticket": 180,
        "transport_day": 80,
        "buffer_rate": 0.12,
    }


def _weather_risk_score(condition: str) -> int:
    text = condition or ""
    if any(keyword in text for keyword in ("暴雨", "大暴雨", "雷暴", "台风", "大雪")):
        return -5
    if any(keyword in text for keyword in ("雨", "雪", "大风", "高温", "霾")):
        return -3
    if any(keyword in text for keyword in ("晴", "云")):
        return 1
    return 2


def _is_weather_risky(weather: dict[str, Any], user_profile: dict[str, Any] | None = None) -> bool:
    condition = str(weather.get("condition") or "").lower()
    risk_score = weather.get("risk_score")
    sensitivity = str((user_profile or {}).get("risk_sensitivity") or "").lower()
    threshold = -1 if sensitivity == "high" else -3 if sensitivity == "low" else -2
    if isinstance(risk_score, (int, float)) and risk_score <= threshold:
        return True
    risky_keywords = ("rain", "storm", "snow", "wind", "雨", "雪", "风", "高温", "霾")
    if sensitivity == "low":
        strong_keywords = ("storm", "heavy", "暴雨", "雷暴", "台风", "大雪")
        return any(keyword in condition for keyword in strong_keywords)
    return any(keyword in condition for keyword in risky_keywords)


TRAVEL_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": [
        "title",
        "city",
        "start_date",
        "end_date",
        "days",
        "attractions",
        "hotel",
        "meals",
        "weather_info",
        "budget",
        "warnings",
        "overall_suggestions",
        "map",
    ],
    "properties": {
        "title": {"type": "string"},
        "city": {"type": "string"},
        "start_date": {"type": "string"},
        "end_date": {"type": "string"},
        "days": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["date", "theme", "weather", "activities"],
                "properties": {
                    "date": {"type": "string"},
                    "day_number": {"type": "integer"},
                    "theme": {"type": "string"},
                    "weather": {"type": "object", "additionalProperties": True},
                    "weather_suggestion": {"type": "string"},
                    "activities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": True,
                            "required": ["time", "period", "type", "title", "reason", "duration", "budget", "tags"],
                            "properties": {
                                "time": {"type": "string"},
                                "period": {"type": "string", "enum": ["morning", "lunch", "afternoon", "evening"]},
                                "type": {"type": "string"},
                                "title": {"type": "string"},
                                "poi_id": {"type": ["string", "null"]},
                                "location": {"type": ["object", "null"], "additionalProperties": True},
                                "transport": {"type": ["string", "null"]},
                                "reason": {"type": "string"},
                                "duration": {"type": "string"},
                                "budget": {"type": "number"},
                                "tags": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                },
            },
        },
        "attractions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "hotel": {"type": "object", "additionalProperties": True},
        "meals": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "weather_info": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "budget": {
            "type": "object",
            "additionalProperties": True,
            "required": ["range", "estimated_total", "breakdown", "per_day"],
            "properties": {
                "range": {"type": "string"},
                "estimated_total": {"type": "number"},
                "breakdown": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "per_day": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "assumptions": {"type": "array", "items": {"type": "string"}},
            },
        },
        "warnings": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "overall_suggestions": {"type": "array", "items": {"type": "string"}},
        "map": {"type": "object", "additionalProperties": True},
    },
}
