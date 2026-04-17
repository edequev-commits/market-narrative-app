from pathlib import Path
import json
from datetime import datetime


CONFIG_PATH = Path(__file__).resolve().parent / "config" / "app_config.json"

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = load_config()

REPO_DIR = Path(__file__).resolve().parent

BASE_DIR = REPO_DIR
MACRO_PAYLOAD_PATH = REPO_DIR / "data" / "dashboard_payload.json"
TICKER_PAYLOAD_PATH = REPO_DIR / "data" / "ticker" / "ticker_dashboard_payload.json"
OUTPUT_PATH = REPO_DIR / "dist" / "index.html"


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def html_escape(text: str) -> str:
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def paragraphs_from_text(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return '<p class="empty-note">Sin información disponible.</p>'

    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not parts:
        parts = [text]

    return "".join(
        f'<p style="margin:0 0 14px 0; line-height:1.8;">{html_escape(part)}</p>'
        for part in parts
    )


def render_market_drivers(drivers_text: str) -> str:
    text = str(drivers_text or "").strip()
    if not text:
        return '<div class="empty-note">No hay drivers disponibles.</div>'

    items = []
    raw_items = [item.strip() for item in text.split("●") if item.strip()]

    for item in raw_items:
        items.append(f"""
            <tr>
                <td class="driver-bullet">●</td>
                <td class="driver-text">{html_escape(item)}</td>
            </tr>
        """)

    return f"""
    <div class="drivers-table-wrap">
      <table class="drivers-table">
        <tbody>
          {''.join(items)}
        </tbody>
      </table>
    </div>
    """


def format_source_date(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""

    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d/%m/%Y - %H:%M")
    except Exception:
        return html_escape(value)


def render_sources(rows: list[dict]) -> str:
    if not rows:
        return '<div class="empty-note">No hay fuentes disponibles.</div>'

    def _sort_key(item: dict):
        value = str(item.get("fecha", "") or "").strip()
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.min

    def clean_source_name(raw_name: str) -> str:
        if not raw_name:
            return ""
        return str(raw_name).split("<")[0].strip()

    sorted_rows = sorted(rows, key=_sort_key, reverse=True)

    items = []
    for item in sorted_rows:
        items.append(f"""
            <div class="source-item">
                <div class="source-header">
                    <div class="source-name">{html_escape(clean_source_name(item.get("fuente", "")))}</div>
                    <div class="source-date">{format_source_date(item.get("fecha", ""))}</div>
                </div>
                <div class="source-detail">{html_escape(item.get("detalle", ""))}</div>
            </div>
        """)

    return "".join(items)


def format_pct(value) -> tuple[str, str]:
    if value in (None, "", "nan"):
        return "", "gap-flat"

    try:
        clean = str(value).replace("%", "").replace(",", "").strip()
        num = float(clean)
    except Exception:
        return html_escape(str(value)), "gap-flat"

    if num > 0:
        css = "gap-up"
    elif num < 0:
        css = "gap-down"
    else:
        css = "gap-flat"

    return f"{num:.2f}%", css


def render_ticker_rows(rows: list[dict]) -> str:
    if not rows:
        return """
        <tr>
            <td colspan="7" class="empty-note">No hay información de ticker intelligence.</td>
        </tr>
        """

    html_rows = []

    for item in rows:
      
        gap_text, gap_class = format_pct(item.get("gap_pct", ""))
        what_happened = html_escape(item.get("what_happened", item.get("what_is_happening", "")))
        market_read = html_escape(item.get("market_read", ""))
        business_impact = html_escape(item.get("business_impact", ""))

        company_name = html_escape(item.get("company_name", ""))
        sector = html_escape(item.get("sector", ""))
        industry = html_escape(item.get("industry", ""))

        description_block = ""
        if what_happened:
            description_block += f'<div class="ticker-fact"><strong>Qué pasó:</strong> {what_happened}</div>'
        if market_read:
            description_block += f'<div class="ticker-read"><strong>Lectura:</strong> {market_read}</div>'
        if business_impact:
            description_block += f'<div class="ticker-impact"><strong>Impacto:</strong> {business_impact}</div>'

        meta_parts = [part for part in [sector, industry] if part]
        meta_text = " · ".join(meta_parts)

        ticker_block = f"""
            <div class="ticker-main">{html_escape(item.get("ticker", ""))} <span class="company-name">{company_name}</span></div>
            <div class="ticker-meta">{meta_text}</div>
        """

        html_rows.append(f"""
            <tr>
                <td class="ticker-cell compact-ticker-cell">{ticker_block}</td>
                <td class="{gap_class} compact-col">{gap_text}</td>
                <td class="compact-col">{html_escape(item.get("volume", ""))}</td>
                <td class="compact-col">{html_escape(item.get("average_volume", ""))}</td>
                <td class="compact-col">{html_escape(item.get("relative_volume", ""))}</td>
                <td class="description-cell ticker-description-cell">{description_block}</td>
                <td class="compact-col score-cell">{html_escape(item.get("score", 0))}</td>
            </tr>
        """)

    return "".join(html_rows)


def build_html(macro_payload: dict, ticker_payload: dict) -> str:
    last_refresh = macro_payload.get("meta", {}).get("last_refresh_display", "")
    narrative_html = f"""
    <div class="last-update">Última actualización: {html_escape(last_refresh)}</div>
    {paragraphs_from_text(macro_payload.get("narrative", ""))}
    """
    regime_html = paragraphs_from_text(macro_payload.get("regime", ""))
    drivers_html = render_market_drivers(macro_payload.get("market_drivers", ""))
    sources_html = render_sources(macro_payload.get("sources", []))
    ticker_generated_at = html_escape(ticker_payload.get("generated_at", ""))
    ticker_rows_html = render_ticker_rows(ticker_payload.get("rows", []))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Market Dashboard</title>
  <style>
    :root {{
      --regime-accent: #fbbf24;
    }}

    html, body {{
      margin: 0;
      padding: 0;
      background: #05070d;
      color: #e5e7eb;
      font-family: Arial, Helvetica, sans-serif;
    }}

    .container {{
      max-width: 1720px;
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

    .tabs {{
      display: flex;
      gap: 10px;
      margin-bottom: 18px;
    }}

    .tab-button {{
      background: #111827;
      color: #cbd5e1;
      border: 1px solid #374151;
      border-radius: 10px;
      padding: 10px 14px;
      cursor: pointer;
      font-weight: 700;
    }}

    .tab-button.active {{
      background: #2563eb;
      color: #ffffff;
      border-color: #2563eb;
    }}

    .tab-content {{
      display: none;
    }}

    .tab-content.active {{
      display: block;
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
      font-size: 14px;
      line-height: 2.5;
    }}

    .regime-card {{
      height: 195px;
      overflow-y: auto;
      overflow-x: hidden;
      background: #111827;
      border: 1px solid #374151;
      border-left: 4px solid var(--regime-accent);
      font-size: 14px;
      line-height: 1.3;
    }}

    .drivers-card {{
      max-height: 260px;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 10px 16px;
      background: #0f172a;
      border: 1px solid #1f2937;
    }}

    .drivers-table-wrap {{
      width: 100%;
      overflow-x: hidden;
    }}

    .drivers-table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}

    .drivers-table tbody tr {{
      border-bottom: 1px solid rgba(148, 163, 184, 0.10);
    }}

    .drivers-table tbody tr:last-child {{
      border-bottom: none;
    }}

    .last-update {{
      color: #94a3b8;
      font-style: italic;
      font-size: 13px;
      margin-bottom: 10px;
    }}

    .driver-bullet {{
      width: 18px;
      vertical-align: top;
      padding: 3px 6px 3px 0;
      color: #e5e7eb;
      font-size: 14px;
      line-height: 1.25;
      white-space: nowrap;
    }}

    .driver-text {{
      padding: 3px 0;
      color: #e5e7eb;
      font-size: 14px;
      line-height: 1.3;
      word-break: break-word;
    }}

    .stocks-card {{
      overflow-x: hidden;
      overflow-y: hidden;
      padding: 18px 18px 14px 18px;
    }}

    .stocks-table-wrap {{
      width: 100%;
      overflow-x: hidden;
      overflow-y: hidden;
      border: 1px solid #172033;
      border-radius: 14px;
    }}

    .stocks-table {{
      width: 100%;
      table-layout: fixed;
      border-collapse: collapse;
      background: #0f172a;
    }}

    .stocks-table thead th {{
      position: sticky;
      top: 0;
      background: #111827;
      color: #cbd5e1;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      text-align: left;
      padding: 9px 6px;
      border-bottom: 1px solid #1f2937;
      white-space: normal;
      line-height: 1.2;
    }}

    .stocks-table tbody td {{
      font-size: 12px;
      color: #e5e7eb;
      padding: 8px 6px;
      border-bottom: 1px solid #172033;
      vertical-align: top;
      word-wrap: break-word;
      overflow-wrap: break-word;
    }}

    .stocks-table tbody tr:hover {{
      background: rgba(148, 163, 184, 0.06);
    }}

    .ticker-cell {{
      font-weight: 800;
      color: #ffffff;
      white-space: nowrap;
    }}

    .compact-ticker-cell {{
      white-space: normal;
    }}

    .compact-col {{
      white-space: nowrap;
      font-size: 11px;
    }}

    .description-cell {{
      min-width: 320px;
      line-height: 1.45;
      color: #cbd5e1;
    }}

    .ticker-description-cell {{
      font-size: 12px;
      line-height: 1.35;
    }}

    .ticker-main {{
      font-weight: 800;
      color: #ffffff;
      white-space: normal;
      line-height: 1.25;
    }}

    .company-name {{
      color: #60a5fa;
      font-weight: 700;
    }}

    .ticker-meta {{
      margin-top: 4px;
      font-size: 10px;
      color: #94a3b8;
      line-height: 1.25;
      white-space: normal;
    }}

    .ticker-impact {{
      margin-top: 6px;
      color: #cbd5e1;
      font-size: 11px;
      line-height: 1.35;
    }}

    .ticker-fact {{
     color: #e5e7eb;
     font-size: 12px;
     line-height: 1.35;
     margin-bottom: 6px;
    }}

    .ticker-read {{
     color: #93c5fd;
     font-size: 12px;
     line-height: 1.35;
     margin-bottom: 6px;
    }}

    .gap-up {{
      color: #22c55e !important;
      font-weight: 700;
    }}

    .gap-down {{
      color: #f472b6 !important;
      font-weight: 700;
    }}

    .gap-flat {{
      color: #cbd5e1 !important;
      font-weight: 700;
    }}

    .score-cell {{
      color: #fbbf24;
      font-weight: 800;
      font-size: 13px;
    }}

    .sources-card {{
      height: 320px;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 10px 10px 6px 10px;
    }}

    .source-item {{
      border-bottom: 1px solid #172033;
      padding: 0 0 6px 0;
      margin: 0 0 6px 0;
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
      font-size: 10px;
      font-weight: 700;
      line-height: 1.25;
      flex: 1;
      min-width: 0;
      word-break: break-word;
    }}

    .source-date {{
      color: #94a3b8;
      font-size: 10px;
      line-height: 1.25;
      white-space: nowrap;
      text-align: right;
      flex-shrink: 0;
      padding-top: 1px;
    }}

    .source-detail {{
      color: #cbd5e1;
      font-size: 9px;
      line-height: 1.25;
      word-break: break-word;
    }}

    .empty-note {{
      color: #cbd5e1;
      font-size: 14px;
    }}

    @media (max-width: 1200px) {{
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
    <div class="title">Daily Market Dashboard v1.1</div>

    <div class="tabs">
      <button class="tab-button active" onclick="showTab('macro-tab', this)">Noticias Macro</button>
      <button class="tab-button" onclick="showTab('ticker-tab', this)">Ticker Intelligence</button>
    </div>

    <div id="macro-tab" class="tab-content active">
      <div class="grid">
        <div>
          <div class="section-title">Narrativa macro</div>
          <div class="card narrative-card">
            {narrative_html}
          </div>

          <div style="height:14px;"></div>

          <!--
          <div class="section-title" style="color: var(--regime-accent);">Market Regime</div>
          <div class="card regime-card">
            {regime_html}
          </div>
          -->

          <div style="height:14px;"></div>

          <div class="section-title">Market Drivers Today</div>
          <div class="card drivers-card">
            {drivers_html}
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

    <div id="ticker-tab" class="tab-content">
      <div class="section-title">Ticker Intelligence</div>
      <div class="card stocks-card">
        <div class="last-update">Última actualización: {ticker_generated_at}</div>
        <div class="stocks-table-wrap">
          <table class="stocks-table ticker-intel-table">
            <colgroup>
              <col style="width: 13%;">
              <col style="width: 6%;">
              <col style="width: 8%;">
              <col style="width: 8%;">
              <col style="width: 6%;">
              <col style="width: 49%;">
              <col style="width: 10%;">
            </colgroup>
            <thead>
              <tr>
                <th>Ticker</th>
                <th>% Gap</th>
                <th>Volume</th>
                <th>Avg. Vol.</th>
                <th>RVOL</th>
                <th>¿Qué está pasando?</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {ticker_rows_html}
            </tbody>
          </table>
        </div>
      </div>
    </div>

  </div>

  <script>
    function showTab(tabId, buttonElement) {{
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-button').forEach(el => el.classList.remove('active'));

      document.getElementById(tabId).classList.add('active');
      buttonElement.classList.add('active');
    }}
  </script>
</body>
</html>"""


def main() -> None:
    macro_payload = load_json(MACRO_PAYLOAD_PATH, {
        "meta": {},
        "narrative": "",
        "regime": "",
        "market_drivers": "",
        "top_stocks_in_play": [],
        "sources": [],
    })

    ticker_payload = load_json(TICKER_PAYLOAD_PATH, {
        "generated_at": "",
        "rows": [],
    })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html = build_html(macro_payload, ticker_payload)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard generado: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()