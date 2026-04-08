import re
from collections import Counter


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "will", "have", "has",
    "been", "were", "they", "their", "about", "while", "could", "would", "should",
    "between", "after", "before", "under", "over", "more", "less", "than", "also",
    "pero", "para", "como", "esta", "este", "estas", "estos", "entre", "desde", "hasta",
    "porque", "aunque", "sobre", "hacia", "donde", "cuando", "contra", "tras", "ante",
    "bajo", "muy", "más", "menos", "solo", "sólo", "una", "uno", "unas", "unos", "del",
    "las", "los", "que", "por", "con", "sin", "sus", "esa", "ese", "eso", "al", "lo",
    "se", "ha", "han", "es", "son", "fue", "fueron", "ya", "aun", "aún", "due", "amid",
    "across", "global", "market", "markets"
}


def _safe_text(value) -> str:
    return (value or "").strip()


def _tokenize(text: str) -> list[str]:
    text = _safe_text(text).lower()
    text = re.sub(r"[^a-záéíóúñü0-9\s]", " ", text)
    return [t for t in text.split() if len(t) >= 4 and t not in STOPWORDS]


def _weighted_filtered_text(filtered_signal: dict) -> str:
    parts = []

    driver = _safe_text(filtered_signal.get("driver_principal", ""))
    hechos = filtered_signal.get("hechos_confirmados", [])
    escenario = _safe_text(filtered_signal.get("escenario_dominante", ""))
    interpretacion = _safe_text(filtered_signal.get("interpretacion_institucional", ""))
    riesgos = filtered_signal.get("riesgos_secundarios", [])
    eventos = filtered_signal.get("eventos_clave", [])

    if driver:
        parts.extend([driver] * 3)

    for item in hechos:
        parts.extend([_safe_text(item)] * 3)

    if escenario:
        parts.extend([escenario] * 2)

    if interpretacion:
        parts.extend([interpretacion] * 2)

    for item in riesgos:
        parts.append(_safe_text(item))

    for item in eventos:
        parts.extend([_safe_text(item)] * 2)

    return "\n".join([p for p in parts if p])


def _score_source(source_text: str, filtered_counter: Counter) -> int:
    source_tokens = _tokenize(source_text)
    if not source_tokens:
        return 0

    source_counter = Counter(source_tokens)
    score = 0

    for token, count in source_counter.items():
        if token in filtered_counter:
            score += min(count, filtered_counter[token]) * filtered_counter[token]

    return score


def _build_vital_text(vital_data: dict) -> str:
    fields = [
        "market_levels",
        "whats_happening",
        "watching_today",
        "watching_next",
        "thinking_about_markets",
        "market_in_a_minute_macro",
        "market_in_a_minute_micro_tuesday_morning",
        "market_in_a_minute_micro_monday_night",
        "iran_section",
        "us_macro_section",
        "international_macro_section",
    ]
    return "\n".join(_safe_text(vital_data.get(f, "")) for f in fields)


def _build_reuters_text(reuters_data: dict) -> str:
    parts = [_safe_text(reuters_data.get("body_excerpt", ""))]

    for item in reuters_data.get("fetched_links", []):
        parts.append(_safe_text(item.get("title", "")))
        parts.append(_safe_text(item.get("summary", "")))
        for p in item.get("key_paragraphs", []):
            parts.append(_safe_text(p))

    return "\n".join(parts)


def build_sources_payload(
    emails: list,
    vital_data: dict,
    reuters_data: dict,
    filtered_signal: dict | None = None
) -> list:
    filtered_signal = filtered_signal or {}
    filtered_text = _weighted_filtered_text(filtered_signal)
    filtered_counter = Counter(_tokenize(filtered_text))

    sources = []

    vital_text = _build_vital_text(vital_data)
    vital_score = _score_source(vital_text, filtered_counter)

    if vital_data and vital_data.get("source_subject"):
        sources.append({
            "fuente": "Vital Knowledge",
            "fecha": vital_data.get("source_date", ""),
            "detalle": vital_data.get("source_subject", ""),
            "score": vital_score,
        })

    reuters_text = _build_reuters_text(reuters_data)
    reuters_score = _score_source(reuters_text, filtered_counter)

    if reuters_data and reuters_data.get("source_subject"):
        sources.append({
            "fuente": "Reuters Daily Briefing",
            "fecha": reuters_data.get("source_date", ""),
            "detalle": reuters_data.get("source_subject", ""),
            "score": reuters_score,
        })

    for email in emails:
        sender = _safe_text(email.get("from", ""))
        subject = _safe_text(email.get("subject", ""))
        date = _safe_text(email.get("date", ""))
        body = _safe_text(email.get("body", ""))

        sender_lower = sender.lower()
        if "vital knowledge" in sender_lower:
            continue
        if "dailybriefing@thomsonreuters.com" in sender_lower:
            continue

        source_text = f"{subject}\n{body[:2500]}"
        score = _score_source(source_text, filtered_counter)

        if score <= 0:
            continue

        sources.append({
            "fuente": sender or "Correo",
            "fecha": date,
            "detalle": subject,
            "score": score,
        })

    sources.sort(key=lambda x: x["score"], reverse=True)

    total_score = sum(x["score"] for x in sources)
    if total_score <= 0:
        total_score = 1

    for item in sources:
        item["contribucion"] = round((item["score"] / total_score) * 100)
        del item["score"]

    return sources[:10]