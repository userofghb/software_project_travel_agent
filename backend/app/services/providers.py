from __future__ import annotations

import json
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
        days = _build_rule_based_days(request, attractions, weather_info, start, end)
        budget = _build_budget(days, request, hotel)
        return {
            "title": request["title"],
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
            "overall_suggestions": [
                "每天按上午、午餐、下午、晚间分段安排，避免只堆一个景点。",
                "同一时段可串联相邻景点，但保留用餐、转场和休息时间。",
                "雨天或高温时优先把室内项目放到下午，并保留可替换活动。",
                "预算按住宿、餐饮、交通、门票和弹性预留拆分，便于前端展示。",
            ],
            "map": {
                "points": build_map_points(hotel, attractions, days),
                "routes": [],
            },
        }


def _build_rule_based_days(
    request: dict[str, Any],
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
        day_attractions = _choose_day_attractions(attractions, index, weather)
        activities = _build_day_activities(request, day_attractions, weather)
        days.append(
            {
                "date": travel_date.isoformat(),
                "day_number": index + 1,
                "theme": _day_theme(index, day_attractions, weather),
                "weather": weather,
                "weather_suggestion": _weather_suggestion(weather),
                "activities": activities,
            }
        )
    return days


def _choose_day_attractions(
    attractions: list[dict[str, Any]],
    day_index: int,
    weather: dict[str, Any],
) -> list[dict[str, Any]]:
    if not attractions:
        return []

    ordered = list(attractions)
    if _is_weather_risky(weather):
        ordered = sorted(ordered, key=lambda item: not _is_indoor_attraction(item))

    per_day = min(3, len(ordered))
    start_index = (day_index * per_day) % len(ordered)
    return [ordered[(start_index + offset) % len(ordered)] for offset in range(per_day)]


def _build_day_activities(
    request: dict[str, Any],
    attractions: list[dict[str, Any]],
    weather: dict[str, Any],
) -> list[dict[str, Any]]:
    city = request["city"]
    transport = request.get("transport_preference", "public_transit")
    budget_range = request.get("budget_range", "medium")
    slots = [
        ("09:00", "morning", "2小时"),
        ("11:00", "morning", "1小时"),
        ("14:30", "afternoon", "2.5小时"),
    ]

    activities = [
        _build_attraction_activity(
            attractions[0] if len(attractions) > 0 else None,
            time=slots[0][0],
            period=slots[0][1],
            duration=slots[0][2],
            city=city,
            transport=transport,
            budget_range=budget_range,
            weather=weather,
        ),
        _build_attraction_activity(
            attractions[1] if len(attractions) > 1 else None,
            time=slots[1][0],
            period=slots[1][1],
            duration=slots[1][2],
            city=city,
            transport=transport,
            budget_range=budget_range,
            weather=weather,
        ),
        _build_meal_activity("12:30", "lunch", city, budget_range),
        _build_attraction_activity(
            attractions[2] if len(attractions) > 2 else None,
            time=slots[2][0],
            period=slots[2][1],
            duration=slots[2][2],
            city=city,
            transport=transport,
            budget_range=budget_range,
            weather=weather,
        ),
        _build_meal_activity("18:30", "evening", city, budget_range),
    ]
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
    is_lunch = period == "lunch"
    return {
        "time": time,
        "period": period,
        "title": f"{city}本地{'午餐' if is_lunch else '晚餐'}",
        "type": "food",
        "poi_id": None,
        "location": None,
        "transport": "walk_or_nearby",
        "reason": "按行程动线就近选择本地特色餐厅，避免餐饮和景点相互挤压",
        "duration": "1.5小时" if is_lunch else "2小时",
        "budget": profile["lunch"] if is_lunch else profile["dinner"],
        "tags": ["餐饮", "本地特色"],
    }


def _day_theme(day_index: int, attractions: list[dict[str, Any]], weather: dict[str, Any]) -> str:
    if _is_weather_risky(weather):
        return f"Day {day_index + 1}: 天气友好型城市体验"
    if attractions:
        first_name = attractions[0].get("name") or "城市地标"
        return f"Day {day_index + 1}: {first_name}周边深度游"
    return f"Day {day_index + 1}: 轻松城市探索"


def _weather_suggestion(weather: dict[str, Any]) -> str:
    if _is_weather_risky(weather):
        return "当天存在天气风险，下午优先安排室内、短距离或可替换活动。"
    return "天气条件较适合户外游览，上午可安排多个相邻景点。"


def _is_weather_risky(weather: dict[str, Any]) -> bool:
    condition = str(weather.get("condition") or "").lower()
    risk_score = weather.get("risk_score")
    if isinstance(risk_score, (int, float)) and risk_score <= -2:
        return True
    risky_keywords = ("rain", "storm", "snow", "wind", "雨", "雪", "风", "高温", "雷")
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
        return {"lunch": 45, "dinner": 65, "ticket": 30, "museum_ticket": 0, "premium_ticket": 100, "transport_day": 45, "buffer_rate": 0.08}
    if any(token in value for token in ("high", "luxury", "高")):
        return {"lunch": 120, "dinner": 180, "ticket": 100, "museum_ticket": 50, "premium_ticket": 260, "transport_day": 160, "buffer_rate": 0.15}
    return {"lunch": 70, "dinner": 110, "ticket": 60, "museum_ticket": 20, "premium_ticket": 180, "transport_day": 80, "buffer_rate": 0.12}


def _build_budget(days: list[dict[str, Any]], request: dict[str, Any], hotel: dict[str, Any]) -> dict[str, Any]:
    profile = _budget_profile(request.get("budget_range", "medium"))
    total_days = max(len(days), 1)
    nights = max(total_days - 1, 1 if total_days > 1 and hotel else 0)
    lodging_total = (hotel.get("price_per_night") or 0) * nights
    meal_total = _sum_activity_budget(days, {"food"})
    ticket_total = _sum_activity_budget(days, {"attraction"})
    transport_total = profile["transport_day"] * total_days
    subtotal = lodging_total + meal_total + ticket_total + transport_total
    buffer = _round_to_ten(subtotal * profile["buffer_rate"])

    per_day = []
    for index, day in enumerate(days):
        daily_meals = sum(_safe_int(activity.get("budget")) or 0 for activity in day.get("activities", []) if activity.get("type") == "food")
        daily_tickets = sum(_safe_int(activity.get("budget")) or 0 for activity in day.get("activities", []) if activity.get("type") == "attraction")
        daily_lodging = (hotel.get("price_per_night") or 0) if index < nights else 0
        daily_transport = profile["transport_day"]
        per_day.append(
            {
                "date": day.get("date"),
                "lodging": daily_lodging,
                "meals": daily_meals,
                "transport": daily_transport,
                "tickets": daily_tickets,
                "subtotal": daily_lodging + daily_meals + daily_transport + daily_tickets,
            }
        )

    return {
        "range": request.get("budget_range", "medium"),
        "estimated_total": int(subtotal + buffer),
        "breakdown": [
            {"key": "lodging", "name": "住宿", "value": int(lodging_total)},
            {"key": "meals", "name": "餐饮", "value": int(meal_total)},
            {"key": "transport", "name": "交通", "value": int(transport_total)},
            {"key": "tickets", "name": "门票", "value": int(ticket_total)},
            {"key": "buffer", "name": "弹性预留", "value": int(buffer)},
        ],
        "per_day": per_day,
        "assumptions": [
            "住宿按行程晚数估算。",
            "餐饮按午餐和晚餐分别估算。",
            "交通按每日城市内转场估算，真实费用会随路线调整。",
        ],
    }


def _sum_activity_budget(days: list[dict[str, Any]], activity_types: set[str]) -> int:
    total = 0
    for day in days:
        for activity in day.get("activities", []):
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
                "daily_structure": "每一天都要覆盖 morning、lunch、afternoon、evening，普通全天行程建议 4-5 个活动。",
                "time_realism": "上午可以安排 1-2 个相邻景点；景点之间要考虑转场、排队、用餐和休息。",
                "weather": "雨天、高温或高风险天气下，下午优先安排室内、短距离或可替换活动。",
                "budget": "预算必须拆分住宿、餐饮、交通、门票和弹性预留，并给出每日 subtotal。",
                "activity_fields": "每个 activity 必须包含 time、period、type、title、reason、duration、budget、tags；景点类活动要带 poi_id、location、transport。",
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
                        "每天必须按 morning、lunch、afternoon、evening 编排；上午可以安排 1-2 个相邻景点，"
                        "下午和晚上要考虑体力、转场、用餐、排队、营业时间常识和天气风险。"
                        "activity 要包含 time、period、type、title、reason、duration、budget、tags；"
                        "景点活动只能从输入 attractions 中选择，并保留 poi_id/location/transport，不要虚构经纬度。"
                        "餐饮和休息活动可以作为无坐标建议，但不要冒充 POI。"
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
        return _ensure_plan_defaults(plan, request, attractions, weather_info, hotel)


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

    def add_point(source: dict[str, Any], point_type: str, fallback_id: str | None = None) -> None:
        location = _normalize_location(source.get("location"))
        if location is None:
            return

        point_id = source.get("id") or source.get("poi_id") or fallback_id or source.get("name") or source.get("title")
        name = source.get("name") or source.get("title") or str(point_id or "")
        key = str(point_id or f"{location['lng']},{location['lat']}")
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
            }
        )

    add_point(hotel, "hotel", "hotel")
    for attraction in attractions:
        if isinstance(attraction, dict):
            add_point(attraction, "attraction")

    for day in days or []:
        if not isinstance(day, dict):
            continue
        for activity in day.get("activities") or []:
            if not isinstance(activity, dict):
                continue
            activity_type = str(activity.get("type") or "activity")
            point_type = "attraction" if activity_type == "attraction" else "activity"
            add_point(activity, point_type)
    return points


def _points_for_day(day: dict[str, Any], points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hotel = next((point for point in points if point.get("type") == "hotel"), None)
    sequence = [hotel] if hotel else []
    activities = day.get("activities") or []
    for activity in activities:
        matched = _match_point(activity, points)
        if matched and matched not in sequence:
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
        "mode": _route_mode(mode),
        "distance_m": 2000,
        "duration_s": 1200,
        "polyline": f"{_location_text(origin)};{_location_text(destination)}",
        "steps": [],
        "source": "mock",
    }


def _normalize_path_route(day: str | None, origin: dict[str, Any], destination: dict[str, Any], mode: str, data: dict[str, Any]) -> dict[str, Any]:
    paths = data.get("route", {}).get("paths") or []
    path = paths[0] if paths else {}
    steps = path.get("steps") or []
    return {
        "day": day,
        "from": origin.get("name"),
        "to": destination.get("name"),
        "mode": mode,
        "distance_m": _safe_int(path.get("distance")),
        "duration_s": _safe_int(path.get("duration")),
        "polyline": ";".join(step.get("polyline", "") for step in steps if step.get("polyline")),
        "steps": [
            {
                "instruction": step.get("instruction"),
                "distance_m": _safe_int(step.get("distance")),
                "duration_s": _safe_int(step.get("duration")),
                "polyline": step.get("polyline"),
            }
            for step in steps
        ],
        "source": "amap",
    }


def _normalize_transit_route(day: str | None, origin: dict[str, Any], destination: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    transits = data.get("route", {}).get("transits") or []
    transit = transits[0] if transits else {}
    segments = transit.get("segments") or []
    steps = []
    polylines = []
    for segment in segments:
        walking = segment.get("walking") or {}
        for step in walking.get("steps") or []:
            steps.append({"instruction": step.get("instruction"), "polyline": step.get("polyline")})
            if step.get("polyline"):
                polylines.append(step["polyline"])
        bus = segment.get("bus", {})
        buslines = bus.get("buslines") or []
        for busline in buslines:
            steps.append({"instruction": busline.get("name"), "polyline": busline.get("polyline")})
            if busline.get("polyline"):
                polylines.append(busline["polyline"])
    return {
        "day": day,
        "from": origin.get("name"),
        "to": destination.get("name"),
        "mode": "transit",
        "distance_m": _safe_int(transit.get("distance")),
        "duration_s": _safe_int(transit.get("duration")),
        "polyline": ";".join(polylines),
        "steps": steps,
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
) -> dict[str, Any]:
    fallback = RuleBasedPlannerProvider().generate_plan(request, {}, attractions, weather_info, hotel)
    for key, value in fallback.items():
        plan.setdefault(key, value)
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
    plan.setdefault("map", {"points": build_map_points(hotel, attractions, plan["days"]), "routes": []})
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
    normalized["type"] = normalized.get("type") or "activity"
    matched = _find_activity_attraction(normalized, attractions)
    if matched and normalized["type"] not in {"food", "meal", "rest", "transport"}:
        normalized["type"] = "attraction"
        normalized.setdefault("poi_id", matched.get("id"))
        normalized.setdefault("location", matched.get("location"))
        normalized.setdefault("address", matched.get("address"))
        normalized.setdefault("transport", request.get("transport_preference", "public_transit"))
    normalized.setdefault("duration", _default_duration(normalized["period"], normalized["type"]))
    if normalized.get("budget") is None:
        if normalized["type"] == "food":
            profile = _budget_profile(request.get("budget_range", "medium"))
            normalized["budget"] = profile["lunch"] if normalized["period"] == "lunch" else profile["dinner"]
        elif matched:
            normalized["budget"] = _activity_ticket_budget(matched, request.get("budget_range", "medium"))
        else:
            normalized["budget"] = 0
    if not isinstance(normalized.get("tags"), list):
        normalized["tags"] = [str(normalized["tags"])] if normalized.get("tags") else []
    if matched:
        for tag in _activity_tags(matched, weather):
            if tag not in normalized["tags"]:
                normalized["tags"].append(tag)
    normalized.setdefault("reason", "结合时间、天气、预算和动线安排")
    return normalized


def _needs_activity_completion(activities: list[dict[str, Any]]) -> bool:
    periods = {activity.get("period") for activity in activities}
    has_food = any(activity.get("type") == "food" for activity in activities)
    return len(activities) < 4 or not {"morning", "afternoon", "evening"}.issubset(periods) or not has_food


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
    if not isinstance(time_text, str) or ":" not in time_text:
        return "morning"
    hour = _safe_int(time_text.split(":", 1)[0])
    if hour is None:
        return "morning"
    if hour < 12:
        return "morning"
    if hour < 14:
        return "lunch"
    if hour < 18:
        return "afternoon"
    return "evening"


def _default_duration(period: str, activity_type: str) -> str:
    if activity_type == "food":
        return "1.5小时" if period == "lunch" else "2小时"
    if period == "morning":
        return "2小时"
    if period == "afternoon":
        return "2.5小时"
    return "1.5小时"


def _activity_signature(activity: dict[str, Any]) -> str:
    return str(activity.get("poi_id") or activity.get("title") or "").strip().lower()


def _activity_sort_key(activity: dict[str, Any]) -> tuple[int, str]:
    time_text = activity.get("time")
    if not isinstance(time_text, str) or ":" not in time_text:
        return (24 * 60, "")
    hour, minute = time_text.split(":", 1)
    return ((_safe_int(hour) or 24) * 60 + (_safe_int(minute) or 0), time_text)


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


def _budget_profile(budget_range: str) -> dict[str, Any]:
    value = str(budget_range or "").lower()
    if any(token in value for token in ("low", "budget", "经济", "低", "省钱", "实惠")):
        return {
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
            "lunch": 120,
            "dinner": 180,
            "ticket": 100,
            "museum_ticket": 50,
            "premium_ticket": 260,
            "transport_day": 160,
            "buffer_rate": 0.15,
        }
    return {
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


def _is_weather_risky(weather: dict[str, Any]) -> bool:
    condition = str(weather.get("condition") or "").lower()
    risk_score = weather.get("risk_score")
    if isinstance(risk_score, (int, float)) and risk_score <= -2:
        return True
    risky_keywords = ("rain", "storm", "snow", "wind", "雨", "雪", "风", "高温", "霾")
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
