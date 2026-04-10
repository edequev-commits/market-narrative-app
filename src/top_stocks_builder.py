import re
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


FINVIZ_HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

TICKER_PATTERN = re.compile(r"\b[A-Z]{1,5}\b")

INVALID_TICKERS = {
    "A", "I", "AM", "PM", "TV", "USA", "US", "UAE", "EU", "UK",
    "AI", "IPO", "EPS", "FDA", "SEC", "CEO", "CFO", "ET", "EST",
    "GDP", "CPI", "PPI", "PCE", "FOMC", "WTI", "OPEC", "ATM", "ADR",
    "LLM", "BTFD", "USD", "JPY", "EUR", "SPY", "QQQ", "DIA", "IWM",
    "VIX", "NYSE", "NASDAQ"
}


def safe_float(value: Any) -> float | None:
    if value is None:
        return None

    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text == "-":
        return None

    try:
        return float(text)
    except Exception:
        return None


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    if number is None:
        return None
    return int(number)


def parse_human_number_to_int(value: str) -> int | None:
    text = (value or "").strip().upper().replace(",", "")
    if not text or text == "-":
        return None

    multiplier = 1
    if text.endswith("K"):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith("B"):
        multiplier = 1_000_000_000
        text = text[:-1]

    try:
        return int(float(text) * multiplier)
    except Exception:
        return None


def extract_text_blobs(
    filtered_signal: dict,
    vital_data: dict,
    reuters_data: dict,
    cnbc_data: dict,
) -> list[tuple[str, str]]:
    blobs: list[tuple[str, str]] = []

    if filtered_signal:
        blobs.append(("filtered_signal", str(filtered_signal)))

    if vital_data:
        for key in [
            "whats_happening",
            "watching_today",
            "thinking_about_markets",
            "market_in_a_minute_macro",
            "iran_section",
            "us_macro_section",
            "international_macro_section",
        ]:
            value = vital_data.get(key)
            if value:
                blobs.append(("vital", str(value)))

    if reuters_data:
        if reuters_data.get("body_excerpt"):
            blobs.append(("reuters", str(reuters_data.get("body_excerpt"))))

        for item in reuters_data.get("fetched_links", []):
            title = item.get("title", "")
            summary = item.get("summary", "")
            paragraphs = " ".join(item.get("key_paragraphs", []))
            combined = " ".join([title, summary, paragraphs]).strip()
            if combined:
                blobs.append(("reuters_link", combined))

    if cnbc_data:
        if cnbc_data.get("body_excerpt"):
            blobs.append(("cnbc", str(cnbc_data.get("body_excerpt"))))

        for item in cnbc_data.get("selected_emails", []):
            subject = item.get("subject", "")
            if subject:
                blobs.append(("cnbc_headline", subject))

    return blobs


def extract_candidate_tickers(
    filtered_signal: dict,
    vital_data: dict,
    reuters_data: dict,
    cnbc_data: dict,
) -> list[dict]:
    blobs = extract_text_blobs(
        filtered_signal=filtered_signal,
        vital_data=vital_data,
        reuters_data=reuters_data,
        cnbc_data=cnbc_data,
    )

    candidates: list[dict] = []

    strong_patterns = [
        re.compile(r"\b[A-Z]{1,5}\b(?=\s*\()"),
        re.compile(r"\(([A-Z]{1,5})\)"),
        re.compile(r"\b(?:shares of|stock of|ticker|ticker:)\s+([A-Z]{1,5})\b", re.IGNORECASE),
    ]

    for source_name, text in blobs:
        text = text or ""
        found = []

        for pattern in strong_patterns:
            matches = pattern.findall(text)
            for match in matches:
                ticker = match.strip().upper()
                if ticker in INVALID_TICKERS:
                    continue
                if ticker not in found:
                    found.append(ticker)

        for ticker in found:
            candidates.append({
                "ticker": ticker,
                "source": source_name,
                "context": text[:1200]
            })

    return candidates


def consolidate_candidates(candidates: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}

    for item in candidates:
        ticker = item["ticker"]

        if ticker not in merged:
            merged[ticker] = {
                "ticker": ticker,
                "mentions": 0,
                "sources": [],
                "raw_context": [],
            }

        merged[ticker]["mentions"] += 1

        source = item.get("source", "")
        if source and source not in merged[ticker]["sources"]:
            merged[ticker]["sources"].append(source)

        context = item.get("context", "")
        if context:
            merged[ticker]["raw_context"].append(context)

    return list(merged.values())


def fetch_finviz_quote_page(ticker: str) -> str:
    import time
    import random

    url = f"https://finviz.com/quote.ashx?t={ticker}"

    headers = {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Mozilla/5.0 (X11; Linux x86_64)"
        ]),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://finviz.com/"
    }

    time.sleep(random.uniform(0.5, 1.2))

    response = requests.get(url, headers=headers, timeout=10)

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}")

    return response.text

def parse_finviz_snapshot(html_text: str, ticker: str) -> dict | None:
    soup = BeautifulSoup(html_text, "html.parser")

    company_name = ""
    company_link = soup.select_one(".quote-header_left .tab-link")
    if company_link:
        company_name = company_link.get_text(" ", strip=True)

    sector = ""
    industry = ""
    links = soup.select(".quote-links a")
    if len(links) >= 3:
        sector = links[1].get_text(" ", strip=True)
        industry = links[2].get_text(" ", strip=True)

    snapshot = {}
    table = soup.find("table", class_="snapshot-table2")

    if table:
        cells = table.find_all("td")
        for i in range(0, len(cells) - 1, 2):
            key = cells[i].get_text(" ", strip=True)
            value = cells[i + 1].get_text(" ", strip=True)
            if key:
                snapshot[key] = value

    price = safe_float(snapshot.get("Price"))
    change_pct = safe_float(snapshot.get("Change"))
    volume_raw = snapshot.get("Volume")
    avg_volume_raw = snapshot.get("Avg Volume")
    float_raw = snapshot.get("Shs Float")
    rel_volume_raw = snapshot.get("Rel Volume")

    volume = parse_human_number_to_int(volume_raw) if volume_raw else None
    average_volume = parse_human_number_to_int(avg_volume_raw) if avg_volume_raw else None
    relative_volume = safe_float(rel_volume_raw)

    result = {
        "ticker": ticker,
        "company_name": company_name,
        "sector": sector,
        "industry": industry,
        "price": price,
        "change_pct": change_pct,
        "volume": volume,
        "average_volume": average_volume,
        "float": float_raw or "",
        "relative_volume": relative_volume,
    }

    return result


def enrich_with_finviz_data(ticker: str) -> dict | None:
    try:
        html_text = fetch_finviz_quote_page(ticker)
        return parse_finviz_snapshot(html_text, ticker)
    except Exception:
        return None


def infer_theme_and_catalyst(
    ticker: str,
    raw_context: list[str],
    narrative: str,
    regime: str,
    stock_data: dict,
) -> tuple[str, str, str]:
    context_text = " ".join(raw_context).lower()
    narrative_text = (narrative or "").lower()
    regime_text = (regime or "").lower()
    sector = (stock_data.get("sector") or "").strip()
    industry = (stock_data.get("industry") or "").strip()

    theme = "General"
    catalyst = "Movimiento relevante con atención del mercado"
    description = "Acción con movimiento activo y potencial intradía hoy."

    if any(word in context_text or word in narrative_text for word in ["oil", "crude", "iran", "middle east", "hormuz", "energy"]):
        theme = "Energy"
        catalyst = "Tema energético / crudo / geopolítica"
        description = "Nombre alineado al tema energético del día y con potencial de continuidad si el flujo sigue activo."
    elif any(word in context_text or word in narrative_text for word in ["ai", "chip", "semiconductor", "nvidia", "data center"]):
        theme = "AI / Semiconductors"
        catalyst = "Tema de IA / semiconductores"
        description = "Nombre ligado a IA o chips con atención del mercado y posibilidad de expansión si entra más volumen."
    elif any(word in context_text for word in ["earnings", "guidance", "revenue", "eps"]):
        theme = "Earnings"
        catalyst = "Reporte / guidance / reacción a resultados"
        description = "Acción con catalizador de resultados y potencial de movimiento si el mercado sigue validando la noticia."
    elif any(word in context_text for word in ["fda", "trial", "drug", "biotech", "approval"]):
        theme = "Biotech / Healthcare"
        catalyst = "Catalizador clínico o regulatorio"
        description = "Nombre con catalizador binario o fuerte, útil para vigilar si mantiene volumen."
    elif any(word in context_text for word in ["bank", "yield", "rates", "fed", "treasury"]):
        theme = "Rates / Financials"
        catalyst = "Sensibilidad a tasas o lectura macro"
        description = "Acción sensible al tono macro del día, con potencial si el mercado profundiza esa lectura."

    if sector and industry:
        description = f"{industry} dentro de {sector}; nombre con catalizador vigente y potencial de movimiento intradía."
    elif industry:
        description = f"{industry}; nombre con catalizador vigente y potencial de movimiento intradía."

    if "transicional" in regime_text or "volátil" in regime_text:
        description = description.rstrip(".") + " En un mercado mixto, exige confirmación antes de entrar."
    elif "defensivo" in regime_text or "risk-off" in regime_text:
        description = description.rstrip(".") + " En un entorno defensivo, solo vale la pena si el movimiento sigue muy limpio."

    return theme, catalyst, description


def score_stock_candidate(
    stock_data: dict,
    mentions: int,
    sources: list[str],
    raw_context: list[str],
    narrative: str,
    regime: str,
) -> int:
    score = 0

    context_text = " ".join(raw_context).lower()
    narrative_text = (narrative or "").lower()
    regime_text = (regime or "").lower()

    change_pct = abs(stock_data.get("change_pct") or 0)
    relative_volume = stock_data.get("relative_volume") or 0
    volume = stock_data.get("volume") or 0
    average_volume = stock_data.get("average_volume") or 0

    # 1) Catalizador / relevancia
    score += min(mentions * 4, 12)
    score += min(len(sources) * 4, 12)

    if any(word in context_text for word in ["earnings", "guidance", "revenue", "eps", "fda", "approval", "deal", "contract", "oil", "iran", "ai", "chip"]):
        score += 6

    # 2) Fuerza de movimiento
    if change_pct >= 2:
        score += 8
    elif change_pct >= 1:
        score += 5

    if relative_volume >= 2:
        score += 10
    elif relative_volume >= 1.2:
        score += 6
    elif relative_volume >= 0.8:
        score += 3

    if volume and average_volume:
        ratio = volume / average_volume if average_volume > 0 else 0
        if ratio >= 1:
            score += 10
        elif ratio >= 0.5:
            score += 6
        elif ratio >= 0.25:
            score += 3

    # 3) Alineación con narrativa
    if any(word in narrative_text and word in context_text for word in ["oil", "iran", "energy", "ai", "chip", "rates", "fed"]):
        score += 12

    # 4) Ajuste al régimen
    if "transicional" in regime_text or "volátil" in regime_text:
        if relative_volume >= 1.2:
            score += 6
        if change_pct >= 2:
            score += 4
    elif "defensivo" in regime_text or "risk-off" in regime_text:
        if any(word in context_text for word in ["earnings", "fda", "approval", "deal", "contract"]):
            score += 6
    else:
        if change_pct >= 2 and relative_volume >= 1:
            score += 8

    return int(min(score, 100))


def passes_minimum_filters(stock_data: dict, regime: str) -> bool:
    price = stock_data.get("price")
    volume = stock_data.get("volume")
    average_volume = stock_data.get("average_volume")
    relative_volume = stock_data.get("relative_volume")
    sector = (stock_data.get("sector") or "").lower()

    if price is None or price < 2:
        return False

    if volume is None or volume < 100_000:
        return False

    if average_volume is None or average_volume < 100_000:
        return False

    if relative_volume is None or relative_volume < 0.3:
        return False

    if "etf" in sector:
        return False

    return True

def rank_and_select_top_stocks(
    enriched_candidates: list[dict],
    max_stocks: int = 6,
) -> list[dict]:
    sorted_items = sorted(
        enriched_candidates,
        key=lambda x: (x.get("score", 0), abs(x.get("change_pct") or 0), x.get("relative_volume") or 0),
        reverse=True,
    )

    selected = []
    selected_tickers = set()
    theme_counter: dict[str, int] = {}

    # Primera pasada: intenta diversidad, pero no sacrifica demasiada cobertura
    for item in sorted_items:
        ticker = item.get("ticker")
        theme = item.get("theme", "General")

        if ticker in selected_tickers:
            continue

        current_count = theme_counter.get(theme, 0)
        if current_count >= 2:
            continue

        selected.append(item)
        selected_tickers.add(ticker)
        theme_counter[theme] = current_count + 1

        if len(selected) >= max_stocks:
            break

    # Segunda pasada: rellena hasta llegar a 6 aunque repita tema
    if len(selected) < max_stocks:
        for item in sorted_items:
            ticker = item.get("ticker")
            if ticker in selected_tickers:
                continue

            selected.append(item)
            selected_tickers.add(ticker)

            if len(selected) >= max_stocks:
                break

    for idx, item in enumerate(selected, start=1):
        item["rank"] = idx

    return selected


def build_top_stocks_in_play(
    filtered_signal: dict,
    vital_data: dict,
    reuters_data: dict,
    cnbc_data: dict,
    narrative: str,
    regime: str,
    max_stocks: int = 6,
) -> list[dict]:
    candidates = extract_candidate_tickers(
        filtered_signal=filtered_signal,
        vital_data=vital_data,
        reuters_data=reuters_data,
        cnbc_data=cnbc_data,
    )

    consolidated = consolidate_candidates(candidates)
    print(f"[TOP STOCKS] candidatos extraídos: {len(candidates)}")
    print(f"[TOP STOCKS] candidatos consolidados: {len(consolidated)}")

    enriched: list[dict] = []

    for item in consolidated:
        ticker = item["ticker"]
        finviz_data = enrich_with_finviz_data(ticker)
        if not finviz_data:
            print(f"[TOP STOCKS] Finviz sin datos para: {ticker}")
            continue    
     
        if not passes_minimum_filters(finviz_data, regime):
            print(f"[TOP STOCKS] ticker descartado por filtros: {ticker}")
            continue

        theme, catalyst, description = infer_theme_and_catalyst(
            ticker=ticker,
            raw_context=item["raw_context"],
            narrative=narrative,
            regime=regime,
            stock_data=finviz_data,
        )

        score = score_stock_candidate(
            stock_data=finviz_data,
            mentions=item["mentions"],
            sources=item["sources"],
            raw_context=item["raw_context"],
            narrative=narrative,
            regime=regime,
        )

        enriched.append({
            "ticker": ticker,
            "company_name": finviz_data.get("company_name", ""),
            "sector": finviz_data.get("sector", ""),
            "industry": finviz_data.get("industry", ""),
            "description": description,
            "change_pct": finviz_data.get("change_pct"),
            "price": finviz_data.get("price"),
            "volume": finviz_data.get("volume"),
            "average_volume": finviz_data.get("average_volume"),
            "float": finviz_data.get("float", ""),
            "relative_volume": finviz_data.get("relative_volume"),
            "catalyst": catalyst,
            "theme": theme,
            "score": score,
            "source_reference": " + ".join(item["sources"]),
        })

    print(f"[TOP STOCKS] candidatos enriquecidos finales: {len(enriched)}")
    return rank_and_select_top_stocks(enriched, max_stocks=max_stocks)