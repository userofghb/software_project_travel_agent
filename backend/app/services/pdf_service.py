from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.dto.plan import TripPlanResponse, TripPlanVersionResponse

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

PAGE_WIDTH, PAGE_HEIGHT = A4


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _format_budget(value: Any) -> str:
    try:
        return f"¥{int(value)}"
    except (TypeError, ValueError):
        try:
            return f"¥{float(value):.2f}"
        except (TypeError, ValueError):
            return ""


def build_plan_pdf_bytes(plan: TripPlanResponse, version: TripPlanVersionResponse) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    stylesheet = getSampleStyleSheet()
    heading_style = ParagraphStyle(
        "Heading1",
        parent=stylesheet["Heading1"],
        fontName="STSong-Light",
        fontSize=18,
        leading=22,
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "Heading2",
        parent=stylesheet["Heading2"],
        fontName="STSong-Light",
        fontSize=12,
        leading=16,
        alignment=TA_LEFT,
    )
    normal_style = ParagraphStyle(
        "Normal",
        parent=stylesheet["Normal"],
        fontName="STSong-Light",
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=stylesheet["Normal"],
        fontName="STSong-Light",
        fontSize=9,
        leading=12,
        alignment=TA_LEFT,
    )

    story = []
    story.append(Paragraph(f"{_safe_text(plan.title)} - v{version.version_no}", heading_style))
    story.append(Spacer(1, 12))

    detail_data = [
        [Paragraph("<b>目的地</b>", normal_style), Paragraph(_safe_text(plan.city), normal_style)],
        [Paragraph("<b>出发日期</b>", normal_style), Paragraph(_safe_text(plan.start_date), normal_style)],
        [Paragraph("<b>结束日期</b>", normal_style), Paragraph(_safe_text(plan.end_date), normal_style)],
        [Paragraph("<b>预算范围</b>", normal_style), Paragraph(_safe_text(plan.budget_range), normal_style)],
        [Paragraph("<b>版本</b>", normal_style), Paragraph(f"v{version.version_no}", normal_style)],
    ]
    story.append(Table(detail_data, colWidths=[100, 360], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ])))
    story.append(Spacer(1, 18))

    content = version.content_json if isinstance(version.content_json, dict) else {}
    budget = content.get("budget") if isinstance(content.get("budget"), dict) else {}
    summary_budget = budget.get("estimated_total")
    story.append(Paragraph("<b>方案摘要</b>", subtitle_style))
    summary_text = []
    summary_text.append(f"总预算：{_format_budget(summary_budget)}")
    pace = _safe_text(content.get("pace"))
    if pace:
        summary_text.append(f"行程节奏：{pace}")
    warning_count = len(content.get("warnings", [])) if isinstance(content.get("warnings"), list) else 0
    summary_text.append(f"预警记录：{warning_count} 条")
    story.append(Paragraph("，".join(summary_text), normal_style))
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>预算明细</b>", subtitle_style))
    breakdown = budget.get("breakdown") if isinstance(budget.get("breakdown"), list) else []
    if breakdown:
        budget_rows = [[Paragraph("<b>类别</b>", normal_style), Paragraph("<b>金额</b>", normal_style)]]
        for item in breakdown:
            if not isinstance(item, dict):
                continue
            budget_rows.append([
                Paragraph(_safe_text(item.get("name") or item.get("key") or item.get("label") or "其他"), normal_style),
                Paragraph(_format_budget(item.get("value")), normal_style),
            ])
        story.append(Table(budget_rows, colWidths=[260, 200], style=TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])))
    else:
        story.append(Paragraph("预算数据暂无", normal_style))
    story.append(Spacer(1, 18))

    story.append(Paragraph("<b>每日行程</b>", subtitle_style))
    days = content.get("days") if isinstance(content.get("days"), list) else []
    if days:
        for day_index, raw_day in enumerate(days, start=1):
            if not isinstance(raw_day, dict):
                continue
            date_text = _safe_text(raw_day.get("date") or raw_day.get("day_date") or "")
            label = f"Day {day_index}"
            if date_text:
                label += f" ({date_text})"
            story.append(Paragraph(label, normal_style))
            weather = raw_day.get("weather") if isinstance(raw_day.get("weather"), dict) else {}
            weather_line = []
            condition = _safe_text(weather.get("condition"))
            if condition:
                weather_line.append(f"天气：{condition}")
            low = weather.get("low")
            high = weather.get("high")
            if low is not None or high is not None:
                weather_line.append(f"温度：{_safe_text(low)}-{_safe_text(high)}")
            if weather_line:
                story.append(Paragraph("，".join(weather_line), small_style))

            activities = raw_day.get("activities") if isinstance(raw_day.get("activities"), list) else []
            if activities:
                activity_lines = []
                for activity in activities:
                    if not isinstance(activity, dict):
                        continue
                    activity_lines.append(_format_activity_line(activity))
                story.append(Paragraph("<br/>".join(activity_lines), normal_style))
            else:
                story.append(Paragraph("暂无活动安排", normal_style))
            story.append(Spacer(1, 10))
    else:
        story.append(Paragraph("行程天数信息暂无", normal_style))
        story.append(Spacer(1, 12))

    suggestions = content.get("overall_suggestions") if isinstance(content.get("overall_suggestions"), list) else []
    if suggestions:
        story.append(Paragraph("<b>总体建议</b>", subtitle_style))
        suggestion_lines = [f"• {_safe_text(item)}" for item in suggestions if item is not None]
        story.append(Paragraph("<br/>".join(suggestion_lines), normal_style))
        story.append(Spacer(1, 12))

    story.append(Paragraph("<b>生成版本信息</b>", subtitle_style))
    story.append(Paragraph(_safe_text(version.change_summary), normal_style))
    story.append(Spacer(1, 14))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def _format_activity_line(activity: dict[str, Any]) -> str:
    title = _safe_text(activity.get("title") or activity.get("name") or "未命名活动")
    time = _safe_text(activity.get("time") or activity.get("start_time") or "--:--")
    typ = _safe_text(activity.get("type") or activity.get("category") or "活动")
    budget = _format_budget(activity.get("budget"))
    reason = _safe_text(activity.get("reason") or activity.get("description") or "")
    parts = [f"{time} {title}", f"类型：{typ}"]
    if budget:
        parts.append(f"预算：{budget}")
    if reason:
        parts.append(f"说明：{reason}")
    return "<br/>".join(parts)
