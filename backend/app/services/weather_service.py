from app.dto.warning import WeatherWarningItem, WeatherWarningResponse


class WeatherService:
    @staticmethod
    def build_warnings(plan_id: int, version_id: int, weather_info: list[dict]) -> WeatherWarningResponse:
        warnings: list[WeatherWarningItem] = []
        for item in weather_info:
            condition = item.get("condition", "")
            # dict.get() returns the default only when the key is missing;
            # if the key exists with value None, it returns None — guard against that.
            risk_score = item.get("risk_score")
            if risk_score is None:
                risk_score = 0
            normalized = {
                "moderate_rain": "moderate_rain",
                "heavy_rain": "heavy_rain",
                "中雨": "moderate_rain",
                "暴雨": "heavy_rain",
            }.get(condition, condition)

            if normalized in {"moderate_rain", "heavy_rain"} or risk_score <= -3:
                level = "high" if normalized == "heavy_rain" or risk_score <= -5 else "medium"
                warnings.append(
                    WeatherWarningItem(
                        date=item["date"],
                        type="heavy_rain" if level == "high" else "rain",
                        level=level,
                        impact="Outdoor activities may be affected",
                        suggestion="Consider switching that day to more indoor activities",
                    )
                )
        return WeatherWarningResponse(plan_id=plan_id, version_id=version_id, warnings=warnings)
