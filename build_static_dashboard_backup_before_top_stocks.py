import json
import html
import re
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "dashboard_payload.json"
DIST_DIR = BASE_DIR / "dist"
OUTPUT_FILE = DIST_DIR / "index.html"


def load_payload():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"No existe el archivo requerido: {DATA_FILE}")

    with DATA_FILE.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if not payload:
        raise ValueError("dashboard_payload.json está vacío")

    if not isinstance(payload, dict):
        raise TypeError("dashboard_payload.json no tiene estructura JSON tipo objeto")

    return payload


def clean_source_name(raw_name: str) -> str:
    raw_name = (raw_name or "").strip()
    if "<" in raw_name:
        raw_name = raw_name.split("<", 1)[0].strip()
    return raw_name.strip('" ').strip()


def format_source_datetime(raw_date: str) -> str:
    raw_date = (raw_date or "").strip()
    if not raw_date:
        return ""
    try:
        dt = datetime.fromisoformat(raw_date)
        return dt.strftime("%d/%m/%Y - %H:%M")
    except Exception:
        return raw_date


def render_paragraphs(text: str) -> str:
    safe = html.escape(text or "")
    paragraphs = [p.strip() for p in safe.split("\n\n") if p.strip()]
    if not paragraphs:
        cleaned = safe.replace("\n", " ").strip()
        paragraphs = [cleaned] if cleaned else []

    return "".join(
        f'<p style="margin:0 0 16px 0; line-height:1.65;">{p.replace(chr(10), " ")}</p>'
        for p in paragraphs
    )


def format_regime_text(regime: str) -> str:
    text = (regime or "").strip()
    if not text:
        return ""

    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\s+", " ", text).strip()

    pattern = re.compile(
        r"^(?P<header>.*?MARKET REGIME:.*?)(?P<semaforo>[🟢🟡🔴])\s*(SEM[ÁA]FORO:\s*(?:Favorable|Mixto|Adverso))?\s*(?P<body>.*)$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if match:
        header = match.group("header").strip()
        semaforo_icon = match.group("semaforo").strip()
        body = match.group("body").strip()
        new_header = f"{header} {semaforo_icon}"
        return f"{new_header}\n\n{body}"

    return text


def get_regime_accent_color(regime: str) -> str:
    text = (regime or "").strip()

    if "🟢" in text:
        return "#22c55e"
    if "🔴" in text:
        return "#ef4444"
    return "#fbbf24"


def render_sources(sources: list) -> str:
    if not sources:
        return '<div class="empty-note">No hay fuentes cargadas.</div>'

    blocks = []
    for src in sources:
        fuente = html.escape(clean_source_name(str(src.get("fuente", ""))))
        fecha = html.escape(format_source_datetime(str(src.get("fecha", ""))))
        detalle = html.escape(str(src.get("detalle", "")))

        blocks.append(
            f"""
            <div class="source-item">
                <div class="source-header">
                    <div class="source-name">{fuente}</div>
                    <div class="source-date">{fecha}</div>
                </div>
                <div class="source-detail">{detalle}</div>
            </div>
            """
        )
    return "".join(blocks)


def build_html(payload: dict) -> str:
    meta = payload.get("meta", {})
    narrative = payload.get("narrative", "")
    regime = payload.get("regime", "")
    sources = payload.get("sources", [])

    last_refresh = html.escape(str(meta.get("last_refresh_display", "No disponible")))
    narrative_html = render_paragraphs(narrative)
    regime_html = render_paragraphs(format_regime_text(regime))
    regime_accent = get_regime_accent_color(regime)
    sources_html = render_sources(sources)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Market Dashboard</title>
  <style>
    :root {{
      --regime-accent: {regime_accent};
    }}

    html, body {{
      margin: 0;
      padding: 0;
      background: #05070d;
      color: #e5e7eb;
      font-family: Arial, Helvetica, sans-serif;
    }}

    .container {{
      max-width: 1600px;
      margin: 0 auto;
      padding: 28px 24px 40px 24px;
      box-sizing: border-box;
    }}

    .title {{
      font-size: 42px;
      font-weight: 800;
      color: #f8fafc;
      margin-bottom: 10px;
    }}

    .subtle {{
      color: #94a3b8;
      font-size: 15px;
      margin-bottom: 18px;
    }}

    .grid {{
      display: grid;
      grid-template-columns: 3fr 0.7fr;
      gap: 24px;
      align-items: start;
    }}

    .section-title {{
      margin-top: 8px;
      margin-bottom: 10px;
      font-size: 13px;
      font-weight: 800;
      color: #67e8f9;
      text-transform: uppercase;
      letter-spacing: 1.1px;
    }}

    .card {{
      background: #0b1220;
      border: 1px solid #1e293b;
      border-radius: 18px;
      padding: 22px 24px;
      box-sizing: border-box;
    }}

    .narrative-card {{
      height: 320px;
      overflow-y: auto;
      overflow-x: hidden;
    }}

    .regime-card {{
      height: 195px;
      overflow-y: auto;
      overflow-x: hidden;
      background: #111827;
      border: 1px solid #374151;
      border-left: 4px solid var(--regime-accent);
    }}

    .sources-card {{
      height: 539px;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 14px 14px 8px 14px;
    }}

    .source-item {{
      border-bottom: 1px solid #172033;
      padding: 0 0 12px 0;
      margin: 0 0 12px 0;
    }}

    .source-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 4px;
    }}

    .source-name {{
      color: #ffffff;
      font-size: 15px;
      font-weight: 700;
      line-height: 1.4;
      flex: 1;
      min-width: 0;
      word-break: break-word;
    }}

    .source-date {{
      color: #94a3b8;
      font-size: 12px;
      line-height: 1.4;
      white-space: nowrap;
      text-align: right;
      flex-shrink: 0;
      padding-top: 2px;
    }}

    .source-detail {{
      color: #cbd5e1;
      font-size: 13px;
      line-height: 1.5;
      word-break: break-word;
    }}

    .empty-note {{
      color: #cbd5e1;
      font-size: 14px;
    }}

    @media (max-width: 1000px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}

      .sources-card {{
        height: 320px;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="title">Daily Market Dashboard v1.0</div>
    <div class="subtle">Última actualización: {last_refresh}</div>

    <div class="grid">
      <div>
        <div class="section-title">Narrativa macro</div>
        <div class="card narrative-card">
          {narrative_html}
        </div>

        <div style="height:14px;"></div>

        <div class="section-title" style="color: var(--regime-accent);">Market Regime</div>
        <div class="card regime-card">
          {regime_html}
        </div>
      </div>

      <div>
        <div class="section-title">Fuentes</div>
        <div class="card sources-card">
          {sources_html}
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""


def main():
    payload = load_payload()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    html_output = build_html(payload)
    OUTPUT_FILE.write_text(html_output, encoding="utf-8")
    print(f"Archivo generado: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()