import json
import subprocess
import sys
import html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components


st.set_page_config(
    page_title="Dailyt Market Dashboard v1.0",
    layout="wide"
)


def load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def run_pipeline() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [sys.executable, "app.py"],
            capture_output=True,
            text=True,
            cwd=".",
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode == 0:
            return True, result.stdout
        return False, (result.stdout or "") + "\n" + (result.stderr or "")
    except Exception as e:
        return False, str(e)


def get_today_events(payload: dict) -> list:
    weekday = payload.get("meta", {}).get("processed_weekday", datetime.now().strftime("%A"))
    grouped = payload.get("vital", {}).get("calendar_grouped_by_day", [])

    for block in grouped:
        if block.get("day", "").lower() == weekday.lower():
            return block.get("events", [])

    return payload.get("vital", {}).get("daily_calendar", [])


def impact_badge(impact: str) -> str:
    impact = (impact or "Medium").lower()
    if impact == "high":
        return '<span class="badge badge-high">ALTO</span>'
    if impact == "medium":
        return '<span class="badge badge-medium">MEDIO</span>'
    return '<span class="badge badge-low">BAJO</span>'


def build_narrative_component(narrative: str) -> str:
    safe = html.escape(narrative or "")
    paragraphs = [p.strip() for p in safe.split("\n\n") if p.strip()]
    if not paragraphs:
        cleaned = safe.replace("\n", " ").strip()
        paragraphs = [cleaned] if cleaned else []

    paragraphs_html = "".join(
        f'<p style="margin:0 0 16px 0; line-height:1.65;">{p.replace(chr(10), " ")}</p>'
        for p in paragraphs
    )

    return f"""
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        html, body {{
          margin: 0;
          padding: 0;
          background: transparent;
          font-family: Arial, Helvetica, sans-serif;
        }}
        .card {{
          background: linear-gradient(180deg, #0b1220 0%, #07101a 100%);
          border: 1px solid #1e293b;
          border-radius: 18px;
          padding: 22px 24px;
          box-sizing: border-box;
          height: 460px;
          overflow-y: auto;
          overflow-x: hidden;
          color: #f8fafc;
          font-size: 19px;
        }}
        p:last-child {{
          margin-bottom: 0 !important;
        }}
      </style>
    </head>
    <body>
      <div class="card">
        {paragraphs_html}
      </div>
    </body>
    </html>
    """


def build_sources_component(sources: list) -> str:
    if not sources:
        items_html = '<div style="color:#cbd5e1;font-size:13px;">No hay fuentes cargadas.</div>'
    else:
        blocks = []
        for src in sources:
            fuente = html.escape(str(src.get("fuente", "")))
            fecha = html.escape(str(src.get("fecha", "")))
            detalle = html.escape(str(src.get("detalle", "")))

            blocks.append(
                f"""
                <div class="source-item">
                    <div class="source-name">{fuente}</div>
                    <div class="source-date">{fecha}</div>
                    <div class="source-detail">{detalle}</div>
                </div>
                """
            )
        items_html = "".join(blocks)

    return f"""
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        html, body {{
          margin: 0;
          padding: 0;
          background: transparent;
          font-family: Arial, Helvetica, sans-serif;
        }}
        .card {{
          background: #0b1220;
          border: 1px solid #1e293b;
          border-radius: 18px;
          padding: 14px 14px 8px 14px;
          box-sizing: border-box;
          height: 460px;
          overflow-y: auto;
          overflow-x: auto;
          color: #e5e7eb;
        }}
        .source-item {{
          border-bottom: 1px solid #172033;
          padding: 0 0 12px 0;
          margin: 0 0 12px 0;
          min-width: 320px;
        }}
        .source-name {{
          color: #ffffff;
          font-size: 15px;
          font-weight: 700;
          line-height: 1.4;
          margin-bottom: 4px;
          word-break: break-word;
        }}
        .source-date {{
          color: #94a3b8;
          font-size: 12px;
          margin-bottom: 4px;
          word-break: break-word;
        }}
        .source-detail {{
          color: #cbd5e1;
          font-size: 13px;
          line-height: 1.5;
          word-break: break-word;
        }}
      </style>
    </head>
    <body>
      <div class="card">
        {items_html}
      </div>
    </body>
    </html>
    """


st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], .main, .block-container {
    background: #05070d !important;
    color: #e5e7eb !important;
}

header[data-testid="stHeader"], section[data-testid="stSidebar"] {
    background: #05070d !important;
}

.block-container {
    max-width: 1600px !important;
    padding-top: 1.8rem !important;
    padding-bottom: 1.5rem !important;
}

.title {
    font-size: 38px;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 8px;
}

.subtle {
    color: #94a3b8;
    font-size: 15px;
    margin-bottom: 10px;
}

.section-title {
    margin-top: 8px;
    margin-bottom: 10px;
    font-size: 13px;
    font-weight: 800;
    color: #67e8f9;
    text-transform: uppercase;
    letter-spacing: 1.1px;
}

.calendar-card {
    background: #0b1220;
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 12px;
}

.event-time {
    font-size: 20px;
    font-weight: 800;
    color: #f8fafc;
}

.event-title {
    font-size: 18px;
    font-weight: 800;
    color: #f8fafc;
    line-height: 1.35;
}

.event-text {
    font-size: 15px;
    color: #cbd5e1;
    line-height: 1.6;
}

.badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 800;
}

.badge-high {
    background: rgba(239,68,68,0.15);
    color: #f87171;
    border: 1px solid rgba(239,68,68,0.30);
}

.badge-medium {
    background: rgba(245,158,11,0.15);
    color: #fbbf24;
    border: 1px solid rgba(245,158,11,0.30);
}

.badge-low {
    background: rgba(34,197,94,0.15);
    color: #4ade80;
    border: 1px solid rgba(34,197,94,0.30);
}

div.stButton > button {
    height: 44px;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 700;
    background-color: #0b1220;
    color: #f8fafc;
    border: 1px solid #1e293b;
    margin-top: 10px;
}

div.stButton > button:hover {
    border-color: #38bdf8;
}
</style>
""", unsafe_allow_html=True)


left, right = st.columns([5.4, 1.6])

with left:
    st.markdown('<div class="title">Dailyt Market Dashboard v1.0</div>', unsafe_allow_html=True)

with right:
    if st.button("Refresh", use_container_width=True):
        with st.spinner("Actualizando..."):
            ok, output = run_pipeline()
        st.session_state["pipeline_output"] = output
        if ok:
            st.rerun()
        else:
            st.error("La actualización falló.")

payload = load_json("data/dashboard_payload.json")
meta = payload.get("meta", {})
narrative = payload.get("narrative", "")
today_events = get_today_events(payload)
sources = payload.get("sources", [])

st.markdown(
    f'<div class="subtle">Última actualización: {meta.get("last_refresh_display", "No disponible")}</div>',
    unsafe_allow_html=True
)

if "pipeline_output" in st.session_state:
    with st.expander("Ver log"):
        st.text(st.session_state["pipeline_output"])

col_narrative, col_sources = st.columns([7, 3], gap="large")

with col_narrative:
    st.markdown('<div class="section-title">Narrativa macro</div>', unsafe_allow_html=True)
    components.html(build_narrative_component(narrative), height=460, scrolling=False)

with col_sources:
    st.markdown('<div class="section-title">Fuentes</div>', unsafe_allow_html=True)
    components.html(build_sources_component(sources), height=460, scrolling=False)

st.markdown('<div class="section-title">Calendario económico — Hoy</div>', unsafe_allow_html=True)

if not today_events:
    st.info("No se encontraron eventos para el día procesado.")
else:
    for event in today_events:
        st.markdown(
            f"""
            <div class="calendar-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <div class="event-time">{event.get("time", "")}</div>
                    <div>{impact_badge(event.get("impact", "Medium"))}</div>
                </div>
                <div class="event-title">{event.get("event", "")}</div>
                <div style="height:8px;"></div>
                <div class="event-text"><strong>Qué significa:</strong> {event.get("meaning_for_economy", "")}</div>
                <div class="event-text" style="margin-top:6px;"><strong>Por qué le importa al mercado:</strong> {event.get("market_relevance", "")}</div>
            </div>
            """,
            unsafe_allow_html=True
        )