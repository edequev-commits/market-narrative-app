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

MACRO_PAYLOAD_PATH = REPO_DIR / "data" / "dashboard_payload.json"
TICKER_PAYLOAD_PATH = REPO_DIR / "data" / "ticker" / "ticker_dashboard_payload.json"
OUTPUT_PATH = REPO_DIR / "dist" / "index.html"
SNAPSHOTS_DIR = REPO_DIR / "data" / "snapshots"


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
            <td colspan="7" class="empty-note">No hay información de acciones.</td>
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


def save_daily_snapshot(macro_payload: dict, ticker_payload: dict):
    try:
        last_refresh_iso = macro_payload.get("meta", {}).get("last_refresh_iso", "")
        if not last_refresh_iso:
            return

        date_key = last_refresh_iso[:10]
        snapshot_dir = SNAPSHOTS_DIR / date_key
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        macro_path = snapshot_dir / "macro_payload.json"
        ticker_path = snapshot_dir / "ticker_payload.json"
        meta_path = snapshot_dir / "meta.json"

        if macro_path.exists() and ticker_path.exists():
            return

        with open(macro_path, "w", encoding="utf-8") as f:
            json.dump(macro_payload, f, indent=2, ensure_ascii=False)

        with open(ticker_path, "w", encoding="utf-8") as f:
            json.dump(ticker_payload, f, indent=2, ensure_ascii=False)

        meta = {
            "date": date_key,
            "created_at": datetime.now().isoformat()
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        print(f"[SNAPSHOT] Guardado snapshot para {date_key}")

    except Exception as e:
        print(f"[SNAPSHOT ERROR] {e}")


def load_available_snapshots() -> list[dict]:
    if not SNAPSHOTS_DIR.exists():
        return []

    snapshots = []

    for snapshot_dir in SNAPSHOTS_DIR.iterdir():
        if not snapshot_dir.is_dir():
            continue

        macro_path = snapshot_dir / "macro_payload.json"
        ticker_path = snapshot_dir / "ticker_payload.json"
        meta_path = snapshot_dir / "meta.json"

        if not macro_path.exists() or not ticker_path.exists():
            continue

        try:
            macro_payload = load_json(macro_path, {})
            ticker_payload = load_json(ticker_path, {})
            meta_payload = load_json(meta_path, {})

            date_key = snapshot_dir.name

            snapshots.append({
                "date": date_key,
                "display_date": date_key,
                "macro_payload": macro_payload,
                "ticker_payload": ticker_payload,
                "meta": meta_payload,
            })
        except Exception as e:
            print(f"[SNAPSHOT LOAD ERROR] {snapshot_dir}: {e}")

    snapshots = sorted(snapshots, key=lambda x: x["date"])
    return snapshots


def format_title_datetime(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""

    patterns = [
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]

    for pattern in patterns:
        try:
            dt = datetime.strptime(value, pattern)
            return dt.strftime("%d-%m-%y %H:%M")
        except Exception:
            continue

    return value


def build_html(macro_payload: dict, ticker_payload: dict, snapshots: list[dict]) -> str:
    last_refresh = macro_payload.get("meta", {}).get("last_refresh_display", "")
    macro_title_dt = format_title_datetime(last_refresh)
    ticker_generated_at = html_escape(ticker_payload.get("generated_at", ""))
    ticker_title_dt = format_title_datetime(ticker_generated_at)

    narrative_html = f"""
    <div id="macro-narrative-content">
      {paragraphs_from_text(macro_payload.get("narrative", ""))}
    </div>
    """

    drivers_html = render_market_drivers(macro_payload.get("market_drivers", ""))
    sources_html = render_sources(macro_payload.get("sources", []))
    ticker_rows_html = render_ticker_rows(ticker_payload.get("rows", []))

    snapshots_for_js = []
    for item in snapshots:
        snapshots_for_js.append({
            "date": item.get("date", ""),
            "display_date": item.get("display_date", ""),
            "macro_payload": item.get("macro_payload", {}),
            "ticker_payload": item.get("ticker_payload", {}),
        })

    snapshots_json = json.dumps(snapshots_for_js, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard de mercado v. 1.0</title>
  <style>
    :root {{
      --header-gap: 10px;
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
      padding: 22px 24px 36px 24px;
      box-sizing: border-box;
    }}

    .title {{
      font-size: 28px;
      font-weight: 800;
      color: #f8fafc;
      margin: 0 0 12px 0;
      line-height: 1.1;
      text-align: center;
    }}

    .history-ribbon-shell {{
      display: flex;
      justify-content: flex-start;
      align-items: center;
      gap: 10px;
      margin: 0 0 14px 0;
    }}

    .history-nav-btn {{
      width: 36px;
      height: 36px;
      border-radius: 10px;
      border: 1px solid #4b5563;
      background: transparent;
      color: #9ca3af;
      cursor: pointer;
      font-size: 17px;
      font-weight: 800;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: all 0.18s ease;
      box-shadow: none;
    }}

    .history-nav-btn:hover {{
      border-color: #9ca3af;
      color: #d1d5db;
      background: rgba(255,255,255,0.03);
    }}

    .history-nav-btn:disabled {{
      opacity: 0.35;
      cursor: default;
      background: transparent;
    }}

    .history-ribbon {{
      display: flex;
      gap: 8px;
      justify-content: flex-start;
      align-items: center;
      min-height: 42px;
    }}

    .history-date-pill {{
      min-width: 106px;
      border-radius: 12px;
      border: 1px solid #3f4b5f;
      background: transparent;
      color: #9ca3af;
      cursor: pointer;
      padding: 9px 12px;
      text-align: center;
      flex-shrink: 0;
      transition: all 0.18s ease;
      box-shadow: none;
    }}

    .history-date-pill:hover {{
      border-color: #6b7280;
      color: #d1d5db;
      background: rgba(255,255,255,0.03);
    }}

    .history-date-pill.active {{
      border-color: #94a3b8;
      color: #e5e7eb;
      background: rgba(255,255,255,0.04);
    }}

    .history-date-main {{
      font-size: 13px;
      font-weight: 700;
      line-height: 1.1;
      color: inherit;
      white-space: nowrap;
    }}

    .tabs {{
      display: flex;
      gap: 22px;
      margin-bottom: 18px;
      border-bottom: 1px solid #1f2937;
      padding-bottom: 6px;
    }}

    .tab-button {{
      background: transparent;
      color: #94a3b8;
      border: none;
      border-bottom: 2px solid transparent;
      border-radius: 0;
      padding: 8px 0;
      cursor: pointer;
      font-weight: 700;
      font-size: 15px;
      transition: all 0.16s ease;
    }}

    .tab-button:hover {{
      color: #e5e7eb;
    }}

    .tab-button.active {{
      background: transparent;
      color: #ffffff;
      border-color: #60a5fa;
    }}

    .tab-content {{
      display: none;
    }}

    .tab-content.active {{
      display: block;
    }}

    .tab-header-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 2px 0 var(--header-gap) 0;
      flex-wrap: wrap;
      min-height: 18px;
    }}

    .section-title {{
      margin: 0;
      font-size: 13px;
      font-weight: 800;
      color: #67e8f9;
      text-transform: none;
      letter-spacing: 0.2px;
    }}

    .title-separator {{
      color: #64748b;
      font-size: 13px;
      font-weight: 700;
      line-height: 1;
    }}

    .title-datetime {{
      color: #94a3b8;
      font-size: 13px;
      font-weight: 700;
      line-height: 1;
      letter-spacing: 0.2px;
    }}

    .grid {{
      display: grid;
      grid-template-columns: 3fr 0.7fr;
      gap: 24px;
      align-items: start;
    }}

    .card {{
      background: #0b1220;
      border: 1px solid #1e293b;
      border-radius: 18px;
      box-sizing: border-box;
    }}

    .narrative-card {{
      height: 320px;
      overflow-y: auto;
      overflow-x: hidden;
      font-size: 14px;
      line-height: 2.5;
      padding: 14px 24px 22px 24px;
    }}

    .drivers-section {{
      margin-top: 14px;
    }}

    .drivers-section .section-title {{
      margin-bottom: var(--header-gap);
    }}

    .drivers-card {{
      max-height: 330px;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 14px 18px;
      background: #0f172a;
      border: 1px solid #1f2937;
    }}

    .sources-section .tab-header-row {{
      margin: 2px 0 var(--header-gap) 0;
    }}

    .sources-card {{
      height: 320px;
      min-height: 320px;
      max-height: 320px;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 14px 10px 6px 10px;
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
      line-height: 1.35;
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
        min-height: 320px;
        max-height: 320px;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="title">Dashboard de mercado v. 1.0</div>

    <div class="history-ribbon-shell">
      <button class="history-nav-btn" id="history-prev-btn" type="button" onclick="goToRelativeSnapshot(-1)">&#8249;</button>
      <div class="history-ribbon" id="history-ribbon"></div>
      <button class="history-nav-btn" id="history-next-btn" type="button" onclick="goToRelativeSnapshot(1)">&#8250;</button>
    </div>

    <div class="tabs">
      <button class="tab-button active" onclick="showTab('macro-tab', this)">Macro</button>
      <button class="tab-button" onclick="showTab('ticker-tab', this)">Acciones</button>
    </div>

    <div id="macro-tab" class="tab-content active">
      <div class="tab-header-row">
        <div class="section-title">Entorno Macro</div>
        <div class="title-separator">|</div>
        <div class="title-datetime" id="macro-title-datetime">{html_escape(macro_title_dt)}</div>
        <div class="title-separator">|</div>
      </div>

      <div class="grid">
        <div>
          <div class="card narrative-card">
            {narrative_html}
          </div>
        </div>

        <div class="sources-section">
          <div class="tab-header-row">
            <div class="section-title">Fuentes</div>
          </div>
          <div class="card sources-card" id="macro-sources-content">
            {sources_html}
          </div>
        </div>
      </div>

      <div class="drivers-section">
        <div class="section-title">Drivers Hoy</div>
        <div class="card drivers-card" id="macro-drivers-content">
          {drivers_html}
        </div>
      </div>
    </div>

    <div id="ticker-tab" class="tab-content">
      <div class="tab-header-row">
        <div class="section-title">Acciones</div>
        <div class="title-separator">|</div>
        <div class="title-datetime" id="ticker-title-datetime">{html_escape(ticker_title_dt)}</div>
        <div class="title-separator">|</div>
      </div>

      <div class="card stocks-card">
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
            <tbody id="ticker-table-body">
              {ticker_rows_html}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <script>
    const SNAPSHOTS = {snapshots_json};
    let activeSnapshotIndex = SNAPSHOTS.length > 0 ? SNAPSHOTS.length - 1 : -1;
    const visibleRibbonCount = 3;

    function showTab(tabId, buttonElement) {{
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-button').forEach(el => el.classList.remove('active'));

      document.getElementById(tabId).classList.add('active');
      buttonElement.classList.add('active');
    }}

    function escapeHtml(value) {{
      if (value === null || value === undefined) return '';
      return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}

    function paragraphsFromText(text) {{
      const clean = String(text || '').trim();
      if (!clean) {{
        return '<p class="empty-note">Sin información disponible.</p>';
      }}

      const parts = clean.split(/\\n\\s*\\n/).map(x => x.trim()).filter(Boolean);
      const finalParts = parts.length ? parts : [clean];

      return finalParts.map(part =>
        `<p style="margin:0 0 14px 0; line-height:1.8;">${{escapeHtml(part)}}</p>`
      ).join('');
    }}

    function renderDriversHtml(driversText) {{
      const clean = String(driversText || '').trim();
      if (!clean) {{
        return '<div class="empty-note">No hay drivers disponibles.</div>';
      }}

      const rawItems = clean.split('●').map(x => x.trim()).filter(Boolean);

      const rows = rawItems.map(item => `
        <tr>
          <td class="driver-bullet">●</td>
          <td class="driver-text">${{escapeHtml(item)}}</td>
        </tr>
      `).join('');

      return `
        <div class="drivers-table-wrap">
          <table class="drivers-table">
            <tbody>
              ${{rows}}
            </tbody>
          </table>
        </div>
      `;
    }}

    function formatSourceDate(value) {{
      if (!value) return '';
      try {{
        const date = new Date(value);
        if (isNaN(date.getTime())) return escapeHtml(value);

        const dd = String(date.getDate()).padStart(2, '0');
        const mm = String(date.getMonth() + 1).padStart(2, '0');
        const yyyy = date.getFullYear();
        const hh = String(date.getHours()).padStart(2, '0');
        const mi = String(date.getMinutes()).padStart(2, '0');

        return `${{dd}}/${{mm}}/${{yyyy}} - ${{hh}}:${{mi}}`;
      }} catch (e) {{
        return escapeHtml(value);
      }}
    }}

    function renderSourcesHtml(rows) {{
      if (!rows || !rows.length) {{
        return '<div class="empty-note">No hay fuentes disponibles.</div>';
      }}

      const sortedRows = [...rows].sort((a, b) => {{
        const da = new Date(a.fecha || 0).getTime() || 0;
        const db = new Date(b.fecha || 0).getTime() || 0;
        return db - da;
      }});

      return sortedRows.map(item => {{
        const rawName = String(item.fuente || '');
        const cleanName = rawName.split('<')[0].trim();

        return `
          <div class="source-item">
            <div class="source-header">
              <div class="source-name">${{escapeHtml(cleanName)}}</div>
              <div class="source-date">${{formatSourceDate(item.fecha || '')}}</div>
            </div>
            <div class="source-detail">${{escapeHtml(item.detalle || '')}}</div>
          </div>
        `;
      }}).join('');
    }}

    function formatPct(value) {{
      if (value === null || value === undefined || value === '' || value === 'nan') {{
        return {{ text: '', css: 'gap-flat' }};
      }}

      try {{
        const clean = String(value).replace('%', '').replace(/,/g, '').trim();
        const num = parseFloat(clean);

        if (isNaN(num)) {{
          return {{ text: escapeHtml(String(value)), css: 'gap-flat' }};
        }}

        let css = 'gap-flat';
        if (num > 0) css = 'gap-up';
        else if (num < 0) css = 'gap-down';

        return {{ text: `${{num.toFixed(2)}}%`, css }};
      }} catch (e) {{
        return {{ text: escapeHtml(String(value)), css: 'gap-flat' }};
      }}
    }}

    function renderTickerRowsHtml(rows) {{
      if (!rows || !rows.length) {{
        return `
          <tr>
            <td colspan="7" class="empty-note">No hay información de acciones.</td>
          </tr>
        `;
      }}

      return rows.map(item => {{
        const gapInfo = formatPct(item.gap_pct || '');
        const ticker = escapeHtml(item.ticker || '');
        const companyName = escapeHtml(item.company_name || '');
        const sector = escapeHtml(item.sector || '');
        const industry = escapeHtml(item.industry || '');
        const volume = escapeHtml(item.volume || '');
        const averageVolume = escapeHtml(item.average_volume || '');
        const relativeVolume = escapeHtml(item.relative_volume || '');
        const whatHappened = escapeHtml(item.what_happened || item.what_is_happening || '');
        const marketRead = escapeHtml(item.market_read || '');
        const businessImpact = escapeHtml(item.business_impact || '');
        const score = escapeHtml(item.score ?? 0);

        const metaParts = [sector, industry].filter(Boolean);
        const metaText = metaParts.join(' · ');

        let descriptionBlock = '';
        if (whatHappened) {{
          descriptionBlock += `<div class="ticker-fact"><strong>Qué pasó:</strong> ${{whatHappened}}</div>`;
        }}
        if (marketRead) {{
          descriptionBlock += `<div class="ticker-read"><strong>Lectura:</strong> ${{marketRead}}</div>`;
        }}
        if (businessImpact) {{
          descriptionBlock += `<div class="ticker-impact"><strong>Impacto:</strong> ${{businessImpact}}</div>`;
        }}

        return `
          <tr>
            <td class="ticker-cell compact-ticker-cell">
              <div class="ticker-main">${{ticker}} <span class="company-name">${{companyName}}</span></div>
              <div class="ticker-meta">${{metaText}}</div>
            </td>
            <td class="${{gapInfo.css}} compact-col">${{gapInfo.text}}</td>
            <td class="compact-col">${{volume}}</td>
            <td class="compact-col">${{averageVolume}}</td>
            <td class="compact-col">${{relativeVolume}}</td>
            <td class="description-cell ticker-description-cell">${{descriptionBlock}}</td>
            <td class="compact-col score-cell">${{score}}</td>
          </tr>
        `;
      }}).join('');
    }}

    function formatTitleDatetime(value) {{
      const clean = String(value || '').trim();
      if (!clean) return '';

      const patterns = [
        /^(\\d{{2}})-(\\d{{2}})-(\\d{{4}})\\s+(\\d{{2}}):(\\d{{2}})(?::\\d{{2}})?$/,
        /^(\\d{{4}})-(\\d{{2}})-(\\d{{2}})\\s+(\\d{{2}}):(\\d{{2}})(?::\\d{{2}})?$/
      ];

      let match = clean.match(patterns[0]);
      if (match) {{
        const dd = match[1];
        const mm = match[2];
        const yyyy = match[3].slice(-2);
        const hh = match[4];
        const mi = match[5];
        return `${{dd}}-${{mm}}-${{yyyy}} ${{hh}}:${{mi}}`;
      }}

      match = clean.match(patterns[1]);
      if (match) {{
        const yyyy = match[1].slice(-2);
        const mm = match[2];
        const dd = match[3];
        const hh = match[4];
        const mi = match[5];
        return `${{dd}}-${{mm}}-${{yyyy}} ${{hh}}:${{mi}}`;
      }}

      return clean;
    }}

    function renderSnapshot(snapshot) {{
      if (!snapshot) return;

      const macroPayload = snapshot.macro_payload || {{}};
      const tickerPayload = snapshot.ticker_payload || {{}};
      const meta = macroPayload.meta || {{}};

      const macroTitleDatetimeEl = document.getElementById('macro-title-datetime');
      const tickerTitleDatetimeEl = document.getElementById('ticker-title-datetime');
      const macroNarrativeEl = document.getElementById('macro-narrative-content');
      const macroDriversEl = document.getElementById('macro-drivers-content');
      const macroSourcesEl = document.getElementById('macro-sources-content');
      const tickerTableBodyEl = document.getElementById('ticker-table-body');

      if (macroTitleDatetimeEl) {{
        macroTitleDatetimeEl.textContent = formatTitleDatetime(meta.last_refresh_display || '');
      }}

      if (tickerTitleDatetimeEl) {{
        tickerTitleDatetimeEl.textContent = formatTitleDatetime(tickerPayload.generated_at || '');
      }}

      if (macroNarrativeEl) {{
        macroNarrativeEl.innerHTML = paragraphsFromText(macroPayload.narrative || '');
      }}

      if (macroDriversEl) {{
        macroDriversEl.innerHTML = renderDriversHtml(macroPayload.market_drivers || '');
      }}

      if (macroSourcesEl) {{
        macroSourcesEl.innerHTML = renderSourcesHtml(macroPayload.sources || []);
      }}

      if (tickerTableBodyEl) {{
        tickerTableBodyEl.innerHTML = renderTickerRowsHtml(tickerPayload.rows || []);
      }}
    }}

    function getRibbonWindowBounds() {{
      if (SNAPSHOTS.length <= visibleRibbonCount) {{
        return {{ start: 0, end: SNAPSHOTS.length }};
      }}

      let start = activeSnapshotIndex - Math.floor(visibleRibbonCount / 2);
      if (start < 0) start = 0;

      let end = start + visibleRibbonCount;
      if (end > SNAPSHOTS.length) {{
        end = SNAPSHOTS.length;
        start = end - visibleRibbonCount;
      }}

      return {{ start, end }};
    }}

    function renderHistoryRibbon() {{
      const ribbon = document.getElementById('history-ribbon');
      const prevBtn = document.getElementById('history-prev-btn');
      const nextBtn = document.getElementById('history-next-btn');

      if (!ribbon) return;

      ribbon.innerHTML = '';

      const bounds = getRibbonWindowBounds();
      const visibleItems = SNAPSHOTS.slice(bounds.start, bounds.end);

      visibleItems.forEach((item, localIndex) => {{
        const realIndex = bounds.start + localIndex;

        const btn = document.createElement('button');
        btn.className = 'history-date-pill' + (realIndex === activeSnapshotIndex ? ' active' : '');
        btn.type = 'button';
        btn.innerHTML = `
          <div class="history-date-main">${{item.date}}</div>
        `;

        btn.onclick = () => {{
          activeSnapshotIndex = realIndex;
          renderSnapshot(SNAPSHOTS[activeSnapshotIndex]);
          renderHistoryRibbon();
        }};

        ribbon.appendChild(btn);
      }});

      if (prevBtn) {{
        prevBtn.disabled = activeSnapshotIndex <= 0;
      }}

      if (nextBtn) {{
        nextBtn.disabled = activeSnapshotIndex >= SNAPSHOTS.length - 1 || activeSnapshotIndex === -1;
      }}
    }}

    function goToRelativeSnapshot(delta) {{
      if (!SNAPSHOTS.length) return;

      const nextIndex = activeSnapshotIndex + delta;
      if (nextIndex < 0 || nextIndex >= SNAPSHOTS.length) return;

      activeSnapshotIndex = nextIndex;
      renderSnapshot(SNAPSHOTS[activeSnapshotIndex]);
      renderHistoryRibbon();
    }}

    renderHistoryRibbon();

    if (SNAPSHOTS.length > 0) {{
      renderSnapshot(SNAPSHOTS[activeSnapshotIndex]);
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

    save_daily_snapshot(macro_payload, ticker_payload)
    snapshots = load_available_snapshots()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html = build_html(macro_payload, ticker_payload, snapshots)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard generado: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()