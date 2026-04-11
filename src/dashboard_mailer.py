import base64
from email.mime.text import MIMEText

from src.gmail_service import get_gmail_service


def build_email_body(payload: dict) -> str:
    meta = payload.get("meta", {})
    narrative = payload.get("narrative", "")
    sources = payload.get("sources", [])
    today_events = payload.get("vital", {}).get("daily_calendar", [])
    reuters_links = payload.get("reuters", {}).get("fetched_links", [])

    lines = []
    lines.append("DAILY MARKET DASHBOARD")
    lines.append("")
    lines.append(f"Fecha de procesamiento: {meta.get('processed_date_display', '')}")
    lines.append(f"Última actualización: {meta.get('last_refresh_display', '')}")
    lines.append("")
    lines.append("NARRATIVA DE MERCADO")
    lines.append(narrative)
    lines.append("")
    lines.append("EVENTOS DEL DÍA")
    for ev in today_events:
        lines.append(
            f"- {ev.get('day', '')} | {ev.get('time', '')} | {ev.get('event', '')} | Impacto: {ev.get('impact', '')}"
        )
    lines.append("")
    lines.append("FUENTES USADAS")
    for src in sources:
        lines.append(
            f"- [{src.get('tipo', '')}] {src.get('fuente', '')} | {src.get('fecha', '')} | {src.get('detalle', '')}"
        )
    lines.append("")
    lines.append("REUTERS - LINKS REVISADOS")
    for item in reuters_links:
        lines.append(f"- {item.get('title', '')}")
        lines.append(f"  URL: {item.get('url', '')}")
        if item.get("summary"):
            lines.append(f"  Resumen: {item.get('summary', '')}")

    return "\n".join(lines)

def _clean_text(value: str) -> str:
    return (value or "").strip()


def _format_top_stocks(top_stocks: list[dict]) -> str:
    if not top_stocks:
        return "Sin acciones destacadas hoy."

    lines = []
    for item in top_stocks:
        ticker = item.get("ticker", "")
        change_pct = item.get("change_pct", "")
        price = item.get("price", "")
        sector = item.get("sector", "")
        industry = item.get("industry", "")
        description = item.get("description", "")

        lines.append(
            f"- {ticker} | %Cambio: {change_pct} | Precio: {price} | Sector: {sector} | Industria: {industry}\n"
            f"  {description}"
        )

    return "\n".join(lines)


def _format_sources(sources: list[dict]) -> str:
    if not sources:
        return "Sin fuentes disponibles."

    lines = []
    for src in sources:
        fuente = src.get("fuente", "")
        fecha = src.get("fecha", "")
        detalle = src.get("detalle", "")
        lines.append(f"- {fuente} | {fecha} | {detalle}")

    return "\n".join(lines)


def build_dashboard_email_body(dashboard_payload: dict) -> str:
    meta = dashboard_payload.get("meta", {})
    narrative = _clean_text(dashboard_payload.get("narrative", ""))
    regime = _clean_text(dashboard_payload.get("regime", ""))
    market_drivers = _clean_text(dashboard_payload.get("market_drivers", ""))
    top_stocks = dashboard_payload.get("top_stocks_in_play", [])
    sources = dashboard_payload.get("sources", [])

    last_refresh = meta.get("last_refresh_display", "No disponible")

    body = f"""DAILY MARKET DASHBOARD

Última actualización: {last_refresh}

==============================
NARRATIVA MACRO
==============================
{narrative}

==============================
MARKET REGIME
==============================
{regime}

==============================
MARKET DRIVERS TODAY
==============================
{market_drivers}

==============================
TOP STOCKS IN PLAY TODAY
==============================
{_format_top_stocks(top_stocks)}

==============================
FUENTES
==============================
{_format_sources(sources)}
"""
    return body



def send_dashboard_email(to_email: str, subject_date: str, dashboard_payload: dict):
    service = get_gmail_service()

    subject = f"Daily Market Dashboard {subject_date}"
    body = build_dashboard_email_body(dashboard_payload)

    message = MIMEText(body, "plain", "utf-8")
    message["to"] = to_email
    message["subject"] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": raw_message}).execute()