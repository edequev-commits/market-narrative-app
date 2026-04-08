import re


DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DAY_MAP = {
    "monday": "Monday",
    "mon": "Monday",
    "tuesday": "Tuesday",
    "tue": "Tuesday",
    "tues": "Tuesday",
    "wednesday": "Wednesday",
    "wed": "Wednesday",
    "thursday": "Thursday",
    "thu": "Thursday",
    "thur": "Thursday",
    "thurs": "Thursday",
    "friday": "Friday",
    "fri": "Friday",
    "saturday": "Saturday",
    "sat": "Saturday",
    "sunday": "Sunday",
    "sun": "Sunday",
}

SECTION_STOP_WORDS = [
    "market levels",
    "earnings of note",
    "trade of the day",
    "company news",
    "bottom line",
    "the idea",
    "quick takes",
    "technicals",
    "charts to watch",
]

EVENT_RULES = [
    {
        "keywords": ["cpi", "consumer price index"],
        "meaning": "Mide inflación al consumidor.",
        "market_relevance": "Puede mover expectativas de tasas, yields, dólar y acciones.",
        "impact": "High",
    },
    {
        "keywords": ["ppi", "producer price index"],
        "meaning": "Mide inflación a nivel productor.",
        "market_relevance": "Puede mover expectativas de inflación y sensibilidad a tasas.",
        "impact": "High",
    },
    {
        "keywords": ["pce"],
        "meaning": "Indicador de inflación muy seguido por el mercado.",
        "market_relevance": "Puede impactar la lectura de tasas y activos de riesgo.",
        "impact": "High",
    },
    {
        "keywords": ["fomc", "fed minutes", "minutes", "federal reserve"],
        "meaning": "Da visibilidad al tono de la Fed.",
        "market_relevance": "Puede mover yields, dólar y equity index futures.",
        "impact": "High",
    },
    {
        "keywords": ["ism", "pmi"],
        "meaning": "Indica ritmo de actividad económica.",
        "market_relevance": "Puede cambiar lectura de crecimiento y apetito por riesgo.",
        "impact": "High",
    },
    {
        "keywords": ["retail sales"],
        "meaning": "Mide fortaleza del consumo.",
        "market_relevance": "Puede mover la percepción de crecimiento.",
        "impact": "High",
    },
    {
        "keywords": ["gdp"],
        "meaning": "Mide crecimiento económico general.",
        "market_relevance": "Puede cambiar la lectura macro dominante.",
        "impact": "High",
    },
    {
        "keywords": ["jobless claims", "claims", "unemployment"],
        "meaning": "Da señales sobre la fortaleza del empleo.",
        "market_relevance": "Puede afectar la lectura macro si sorprende.",
        "impact": "Medium",
    },
    {
        "keywords": ["consumer sentiment", "confidence", "sentiment"],
        "meaning": "Refleja percepción del consumidor.",
        "market_relevance": "Ayuda a interpretar consumo y confianza.",
        "impact": "Medium",
    },
]


def find_vital_knowledge_email(emails: list) -> dict | None:
    ranked = []

    for email in emails:
        sender = (email.get("from", "") or "").lower()
        subject = (email.get("subject", "") or "").lower()
        body = (email.get("body", "") or "").lower()

        score = 0
        if "vital knowledge" in sender:
            score += 5
        if "vital knowledge" in subject:
            score += 4
        if "calendar for the week" in body:
            score += 3
        if "what to watch during the week" in body:
            score += 3
        if "calendar for monday" in body or "calendar for tuesday" in body:
            score += 2
        if "market levels" in body:
            score += 2
        if "what’s happening this morning" in body or "what's happening this morning" in body:
            score += 2
        if "how we’re thinking about markets" in body or "how we're thinking about markets" in body:
            score += 2

        if score > 0:
            ranked.append((score, email))

    if not ranked:
        return None

    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1]


def clean_line(line: str) -> str:
    line = line.replace("\xa0", " ")
    line = line.replace("•", "")
    line = line.replace("–", "-")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def detect_day(text: str) -> str | None:
    lower = text.lower()
    for key, value in DAY_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", lower):
            return value
    return None


def detect_time(text: str) -> str:
    patterns = [
        r"\b\d{1,2}:\d{2}\s?(?:am|pm)\s?et\b",
        r"\b\d{1,2}\s?(?:am|pm)\s?et\b",
        r"\b\d{1,2}:\d{2}\s?(?:am|pm)\b",
        r"\b\d{1,2}\s?(?:am|pm)\b",
    ]
    lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return match.group(0).upper().replace("Et", "ET")
    return ""


def classify_event(event_text: str) -> dict:
    lower = event_text.lower()
    for rule in EVENT_RULES:
        if any(keyword in lower for keyword in rule["keywords"]):
            return {
                "meaning_for_economy": rule["meaning"],
                "market_relevance": rule["market_relevance"],
                "impact": rule["impact"],
            }

    return {
        "meaning_for_economy": "Evento macro relevante para monitorear.",
        "market_relevance": "Puede mover expectativas si el dato sorprende.",
        "impact": "Medium",
    }


def normalize_event_text(text: str) -> str:
    text = clean_line(text)
    text = text.strip(" -.,;:")
    return text


def is_stop_line(line: str) -> bool:
    lower = line.lower()
    return any(stop in lower for stop in SECTION_STOP_WORDS)


def split_event_candidates(text: str) -> list[str]:
    parts = re.split(r";|\s\|\s|(?<!\d),\s(?=[A-Z])", text)
    cleaned = []
    for part in parts:
        part = normalize_event_text(part)
        if len(part) >= 5:
            cleaned.append(part)
    return cleaned


def parse_weekly_calendar_block(body: str) -> tuple[list, list]:
    lines = [clean_line(x) for x in body.splitlines() if clean_line(x)]

    weekly_overview = []
    daily_calendar = []

    in_calendar_section = False

    for line in lines:
        lower = line.lower()

        if "calendar for the week" in lower:
            in_calendar_section = True
            continue

        if in_calendar_section and is_stop_line(line):
            break

        if not in_calendar_section:
            continue

        if "what to watch during the week" in lower:
            content = line.split("-", 1)[-1].strip() if "-" in line else line
            for event_text in split_event_candidates(content):
                day = detect_day(event_text) or ""
                item = classify_event(event_text)
                weekly_overview.append({
                    "section_type": "weekly_overview",
                    "day": day,
                    "time": detect_time(event_text),
                    "event": event_text,
                    "meaning_for_economy": item["meaning_for_economy"],
                    "market_relevance": item["market_relevance"],
                    "impact": item["impact"],
                    "raw_line": line,
                })
            continue

        if re.search(r"^calendar for (monday|tuesday|wednesday|thursday|friday)", lower):
            header_day = detect_day(line) or ""
            content = line.split("-", 1)[-1].strip() if "-" in line else line

            for event_text in split_event_candidates(content):
                item = classify_event(event_text)
                daily_calendar.append({
                    "section_type": "daily_calendar",
                    "day": header_day,
                    "time": detect_time(event_text),
                    "event": event_text,
                    "meaning_for_economy": item["meaning_for_economy"],
                    "market_relevance": item["market_relevance"],
                    "impact": item["impact"],
                    "raw_line": line,
                })

    return weekly_overview, daily_calendar


def group_calendar_by_day(calendar_items: list) -> list:
    grouped = {day: [] for day in DAY_ORDER}

    for item in calendar_items:
        day = item.get("day") or "Unknown"
        grouped.setdefault(day, []).append(item)

    output = []
    for day in DAY_ORDER:
        if grouped.get(day):
            output.append({
                "day": day,
                "events": grouped[day]
            })

    if grouped.get("Unknown"):
        output.append({
            "day": "Unknown",
            "events": grouped["Unknown"]
        })

    return output


def normalize_section_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def find_marker_position(body: str, markers: list[str]) -> tuple[int, str] | None:
    lower_body = body.lower()
    best = None

    for marker in markers:
        idx = lower_body.find(marker.lower())
        if idx != -1:
            if best is None or idx < best[0]:
                best = (idx, marker)

    return best


def extract_named_section(body: str, start_markers: list[str], end_markers: list[str]) -> str:
    if not body:
        return ""

    start_hit = find_marker_position(body, start_markers)
    if not start_hit:
        return ""

    start_idx = start_hit[0]
    end_idx = len(body)
    lower_body = body.lower()

    for marker in end_markers:
        idx = lower_body.find(marker.lower(), start_idx + 1)
        if idx != -1 and idx < end_idx:
            end_idx = idx

    return normalize_section_text(body[start_idx:end_idx])


def extract_vital_knowledge_sections(vital_email: dict) -> dict:
    if not vital_email:
        return {
            "weekly_overview": [],
            "daily_calendar": [],
            "calendar_grouped_by_day": [],
            "source_subject": "",
            "source_from": "",
            "source_date": "",
            "market_levels": "",
            "whats_happening": "",
            "watching_today": "",
            "watching_next": "",
            "thinking_about_markets": "",
            "market_in_a_minute_macro": "",
            "market_in_a_minute_micro_tuesday_morning": "",
            "market_in_a_minute_micro_monday_night": "",
            "iran_section": "",
            "us_macro_section": "",
            "international_macro_section": "",
            "energy_section": "",
            "tmt_section": "",
            "calendar_this_week": "",
            "calendar_next_week": "",
            "catalysts_section": "",
        }

    body = vital_email.get("body", "") or ""
    weekly_overview, daily_calendar = parse_weekly_calendar_block(body)

    market_levels = extract_named_section(
        body,
        start_markers=["Market levels"],
        end_markers=["What’s happening this morning", "What's happening this morning"]
    )

    whats_happening = extract_named_section(
        body,
        start_markers=["What’s happening this morning", "What's happening this morning"],
        end_markers=[
            "What we’ll be watching on Tuesday", "What we'll be watching on Tuesday",
            "What we’ll be watching on Wednesday", "What we'll be watching on Wednesday",
            "How we’re thinking about markets", "How we're thinking about markets"
        ]
    )

    watching_today = extract_named_section(
        body,
        start_markers=["What we’ll be watching on Tuesday", "What we'll be watching on Tuesday"],
        end_markers=[
            "What we’ll be watching on Wednesday", "What we'll be watching on Wednesday",
            "How we’re thinking about markets", "How we're thinking about markets"
        ]
    )

    watching_next = extract_named_section(
        body,
        start_markers=["What we’ll be watching on Wednesday", "What we'll be watching on Wednesday"],
        end_markers=["How we’re thinking about markets", "How we're thinking about markets"]
    )

    thinking_about_markets = extract_named_section(
        body,
        start_markers=["How we’re thinking about markets", "How we're thinking about markets"],
        end_markers=["Market in a Minute (macro)"]
    )

    market_in_a_minute_macro = extract_named_section(
        body,
        start_markers=["Market in a Minute (macro)"],
        end_markers=[
            "Market in a Minute (micro – Tuesday morning)",
            "Market in a Minute (micro - Tuesday morning)",
            "Market in a Minute (micro - Tuesday morning)",
            "Market in a Minute (micro"
        ]
    )

    market_in_a_minute_micro_tuesday_morning = extract_named_section(
        body,
        start_markers=[
            "Market in a Minute (micro – Tuesday morning)",
            "Market in a Minute (micro - Tuesday morning)"
        ],
        end_markers=[
            "Market in a Minute (micro – Monday night)",
            "Market in a Minute (micro - Monday night)",
            "Calendar for Tuesday 4/7",
            "Iran"
        ]
    )

    market_in_a_minute_micro_monday_night = extract_named_section(
        body,
        start_markers=[
            "Market in a Minute (micro – Monday night)",
            "Market in a Minute (micro - Monday night)"
        ],
        end_markers=["Calendar for Tuesday 4/7", "Iran"]
    )

    iran_section = extract_named_section(
        body,
        start_markers=["Iran"],
        end_markers=["US macro"]
    )

    us_macro_section = extract_named_section(
        body,
        start_markers=["US macro"],
        end_markers=["International macro"]
    )

    international_macro_section = extract_named_section(
        body,
        start_markers=["International macro"],
        end_markers=["Consumer", "Energy", "Financials", "Healthcare", "M&A/Strategic Actions", "TMT", "Calendar for the week"]
    )

    energy_section = extract_named_section(
        body,
        start_markers=["Energy"],
        end_markers=["Financials", "Healthcare", "M&A/Strategic Actions", "TMT", "Calendar for the week"]
    )

    tmt_section = extract_named_section(
        body,
        start_markers=["TMT"],
        end_markers=["Calendar for the week of Monday April 6", "Calendar for the week of Monday April 13", "Catalysts"]
    )

    calendar_this_week = extract_named_section(
        body,
        start_markers=["Calendar for the week of Monday April 6"],
        end_markers=["Calendar for the week of Monday April 13", "Catalysts"]
    )

    calendar_next_week = extract_named_section(
        body,
        start_markers=["Calendar for the week of Monday April 13"],
        end_markers=["Catalysts"]
    )

    catalysts_section = extract_named_section(
        body,
        start_markers=["Catalysts – big events to watch over the coming months", "Catalysts - big events to watch over the coming months"],
        end_markers=[]
    )

    return {
        "weekly_overview": weekly_overview,
        "daily_calendar": daily_calendar,
        "calendar_grouped_by_day": group_calendar_by_day(daily_calendar),
        "source_subject": vital_email.get("subject", ""),
        "source_from": vital_email.get("from", ""),
        "source_date": vital_email.get("date", ""),
        "market_levels": market_levels,
        "whats_happening": whats_happening,
        "watching_today": watching_today,
        "watching_next": watching_next,
        "thinking_about_markets": thinking_about_markets,
        "market_in_a_minute_macro": market_in_a_minute_macro,
        "market_in_a_minute_micro_tuesday_morning": market_in_a_minute_micro_tuesday_morning,
        "market_in_a_minute_micro_monday_night": market_in_a_minute_micro_monday_night,
        "iran_section": iran_section,
        "us_macro_section": us_macro_section,
        "international_macro_section": international_macro_section,
        "energy_section": energy_section,
        "tmt_section": tmt_section,
        "calendar_this_week": calendar_this_week,
        "calendar_next_week": calendar_next_week,
        "catalysts_section": catalysts_section,
    }