from pathlib import Path
import json
from datetime import datetime, time as dt_time
import pandas as pd

from src.ticker.ticker_llm_runner import load_prompt, run_ticker_analysis

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "app_config.json"

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_config()

RANKING_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "ticker_ranking_rules.json"

def load_ranking_config():
    if not RANKING_CONFIG_PATH.exists():
        raise FileNotFoundError(f"No se encontró ticker_ranking_rules.json")
    with open(RANKING_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

RANKING_CONFIG = load_ranking_config()

REPO_DIR = Path(__file__).resolve().parent

APP_BASE_DIR = REPO_DIR
FINVIZ_BASE_DIR = Path(CONFIG["paths"]["finviz_news_base_dir"])
TICKER_OUTPUT_DIR = REPO_DIR / "data" / "ticker"
FINVIZ_OUTPUTS_DIR = Path(CONFIG["paths"]["finviz_outputs_dir"])
GAP_UP_FILE_PATH = REPO_DIR / "tradeideas_gap_up.txt"
GAP_DOWN_FILE_PATH = REPO_DIR / "tradeideas_gap_down.txt"
TICKER_WINDOW_START = CONFIG["windows"]["ticker"]["start_time"]
TICKER_WINDOW_END = CONFIG["windows"]["ticker"]["end_time"]

BASE_DIR = REPO_DIR

TICKER_OUTPUT_PATH = TICKER_OUTPUT_DIR / "ticker_dashboard_payload.json"
PROMPT_FILE = REPO_DIR / "prompts" / "ticker" / "ticker_catalyst_analysis.txt"

FINVIZ_DIR = FINVIZ_BASE_DIR
FINVIZ_OUTPUT_DIR = FINVIZ_BASE_DIR / "finviz_news"

GAP_UP_FILE = GAP_UP_FILE_PATH
GAP_DOWN_FILE = GAP_DOWN_FILE_PATH


PREMARKET_START = dt_time(0, 0)
PREMARKET_END = dt_time(9, 30)


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def ensure_output_dir() -> None:
    TICKER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_tickers_from_file(path: Path) -> list[str]:
    if not path.exists():
        return []

    tickers = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            ticker = line.strip().upper().replace("$", "")
            if ticker:
                tickers.append(ticker)
    return tickers


def load_all_tickers() -> list[str]:
    tickers = load_tickers_from_file(GAP_UP_FILE) + load_tickers_from_file(GAP_DOWN_FILE)
    return list(dict.fromkeys(tickers))


def get_latest_file(prefix):
    outputs_dir = REPO_DIR / "outputs"
    finviz_dir = REPO_DIR / "finviz_news"

    files = []

    # Buscar en outputs/ de forma directa y recursiva
    files.extend(outputs_dir.glob(f"{prefix}_*.csv"))
    files.extend(outputs_dir.glob(f"**/{prefix}_*.csv"))

    # Buscar en finviz_news/ de forma directa y recursiva
    files.extend(finviz_dir.glob(f"{prefix}_*.csv"))
    files.extend(finviz_dir.glob(f"**/{prefix}_*.csv"))

    # Quitar duplicados y ordenar por fecha de modificación
    files = list({f.resolve(): f for f in files}.values())
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    if files:
        log(f"[FILE DETECTION] {prefix} encontrado: {files[0]}")
        return files[0]

    raise FileNotFoundError(f"No se encontró ningún archivo para {prefix}")





def read_csv_flexible(path: Path) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin1"]
    last_error = None

    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_error = e

    raise last_error


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    return df


def safe_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def parse_pct_to_float(value) -> float:
    try:
        text = safe_str(value).replace("%", "").replace(",", "")
        return float(text)
    except Exception:
        return 0.0


def parse_volume_to_float(value) -> float:
    try:
        text = safe_str(value).upper().replace(",", "").strip()
        if text.endswith("K"):
            return float(text[:-1]) * 1_000
        if text.endswith("M"):
            return float(text[:-1]) * 1_000_000
        if text.endswith("B"):
            return float(text[:-1]) * 1_000_000_000
        return float(text)
    except Exception:
        return 0.0


def compute_score(row: dict) -> tuple[int, dict]:

    weights = RANKING_CONFIG["weights"]
    catalyst_strength_map = RANKING_CONFIG.get("catalyst_strength_map", {})

    gap = abs(parse_pct_to_float(row.get("gap_pct", "0")))
    rvol = float(row.get("relative_volume", 0) or 0)
    vol = parse_volume_to_float(row.get("volume", "0"))

    catalyst_type = str(row.get("catalyst_type", "unknown") or "unknown").lower()
    sentiment = str(row.get("sentiment", "Neutral") or "Neutral").lower()
    is_extraordinary = str(row.get("is_extraordinary", "No") or "No").strip().lower()

    # 1) Catalyst type score
    catalyst_type_score = catalyst_strength_map.get(catalyst_type, 0)

    # 2) RVOL score con penalización real
    if rvol >= 5:
        rvol_score = 4
    elif rvol >= 3:
        rvol_score = 3
    elif rvol >= 1.5:
        rvol_score = 2
    elif rvol >= 1.0:
        rvol_score = 0
    else:
        rvol_score = -2

    # 3) Premarket volume score
    if vol >= 50_000_000:
        volume_score = 4
    elif vol >= 20_000_000:
        volume_score = 3
    elif vol >= 5_000_000:
        volume_score = 2
    elif vol >= 1_000_000:
        volume_score = 1
    else:
        volume_score = 0

    # 4) Gap score
    if gap >= 15:
        gap_score = 4
    elif gap >= 8:
        gap_score = 3
    elif gap >= 3:
        gap_score = 2
    elif gap >= 1:
        gap_score = 1
    else:
        gap_score = 0

    # 5) Sentiment score
    if sentiment == "positive":
        sentiment_score = 1
    elif sentiment == "negative":
        sentiment_score = -1
    else:
        sentiment_score = 0

    # 6) Extraordinary score
    extraordinary_score = 1 if is_extraordinary == "sí" or is_extraordinary == "si" or is_extraordinary == "yes" else 0

    breakdown = {
        "catalyst_type": catalyst_type_score * weights["catalyst"],
        "rvol": rvol_score * weights["rvol"],
        "premarket_volume": volume_score * weights["premarket_volume"],
        "gap_pct": gap_score * weights["gap_pct"],
        "sentiment": sentiment_score,
        "extraordinary": extraordinary_score,
    }

    total_score = sum(breakdown.values())

    return total_score, breakdown

def classify_catalyst(text: str) -> str:
    if not text:
        return "unknown"

    text_lower = text.lower()
    keyword_map = RANKING_CONFIG["catalyst_keywords"]

    for category, keywords in keyword_map.items():
        for kw in keywords:
            if kw in text_lower:
                return category

    return "unknown"


def filter_premarket_news_window(news_df: pd.DataFrame) -> pd.DataFrame:
    if news_df.empty or "NewsDateTime" not in news_df.columns:
        return news_df

    df = news_df.copy()
    df["NewsDateTime_dt"] = pd.to_datetime(df["NewsDateTime"], errors="coerce")
    df = df[df["NewsDateTime_dt"].notna()].copy()

    if df.empty:
        return df

    latest_date = df["NewsDateTime_dt"].dt.date.max()
    df = df[df["NewsDateTime_dt"].dt.date == latest_date].copy()

    df["NewsTime"] = df["NewsDateTime_dt"].dt.time
    df = df[df["NewsTime"].apply(lambda t: PREMARKET_START <= t <= PREMARKET_END)].copy()

    return df


def build_prompt_input(ticker, finviz_row, news_subset):
    lines = []
    lines.append(f"TICKER: {ticker}")
    lines.append("")

    lines.append("DATOS FINVIZ:")
    lines.append(f"- Company: {finviz_row.get('Company','')}")
    lines.append(f"- Sector: {finviz_row.get('Sector','')}")
    lines.append(f"- Industry: {finviz_row.get('Industry','')}")
    lines.append(f"- Change: {finviz_row.get('Change','')}")
    lines.append(f"- Volume: {finviz_row.get('Volume','')}")
    lines.append(f"- Avg Volume: {finviz_row.get('Avg Volume','')}")
    lines.append(f"- Rel Volume: {finviz_row.get('Rel Volume','')}")
    lines.append("")

    lines.append("NOTICIAS PREMARKET (12:00am a 9:30am):")
    for _, row in news_subset.iterrows():
        lines.append(f"- Fecha: {safe_str(row.get('NewsDateTime',''))}")
        lines.append(f"  Source: {safe_str(row.get('Source',''))}")
        lines.append(f"  Priority: {safe_str(row.get('Priority',''))}")
        lines.append(f"  Headline: {safe_str(row.get('Headline',''))}")
        lines.append("")

    return "\n".join(lines)


def pick_relevant_news_subset(news_df: pd.DataFrame, ticker: str, max_items: int = 4) -> pd.DataFrame:
    subset = news_df[news_df["Ticker"].astype(str).str.upper() == ticker].copy()
    if subset.empty:
        return subset

    if "Priority" in subset.columns:
        priority_map = {"HIGH": 3, "MEDIUM": 2, "NORMAL": 1, "LOW": 0}
        subset["PriorityScore"] = subset["Priority"].astype(str).str.upper().map(priority_map).fillna(0)
    else:
        subset["PriorityScore"] = 0

    if "NewsDateTime_dt" not in subset.columns:
        if "NewsDateTime" in subset.columns:
            try:
                subset["NewsDateTime_dt"] = pd.to_datetime(subset["NewsDateTime"], errors="coerce")
            except Exception:
                subset["NewsDateTime_dt"] = pd.NaT
        else:
            subset["NewsDateTime_dt"] = pd.NaT

    subset = subset.sort_values(
        ["PriorityScore", "NewsDateTime_dt"],
        ascending=[False, False]
    )

    return subset.head(max_items)


def build_payload():
    ensure_output_dir()

    prompt = load_prompt(str(PROMPT_FILE))

    tickers = load_all_tickers()
    log(f"Tickers cargados desde gap files: {len(tickers)}")

    if not tickers:
        raise RuntimeError("No se encontraron tickers en tradeideas_gap_up.txt o tradeideas_gap_down.txt")

    news_file = get_latest_file("news_output")
    finviz_file = get_latest_file("finviz_data")

    log(f"Usando news file: {news_file.name}")
    log(f"Usando finviz file: {finviz_file.name}")

    news_df = normalize_columns(read_csv_flexible(news_file))
    finviz_df = normalize_columns(read_csv_flexible(finviz_file))

    required_news_cols = {"Ticker", "Headline"}
    required_finviz_cols = {"Ticker", "Company", "Sector", "Industry"}

    if not required_news_cols.issubset(set(news_df.columns)):
        raise RuntimeError(f"El archivo news_output no tiene las columnas mínimas esperadas: {required_news_cols}")

    if not required_finviz_cols.issubset(set(finviz_df.columns)):
        raise RuntimeError(f"El archivo finviz_data no tiene las columnas mínimas esperadas: {required_finviz_cols}")

    news_df = filter_premarket_news_window(news_df)
    log(f"Noticias dentro de ventana 12:00am-9:30am: {len(news_df)}")

    rows = []

    for ticker in tickers:
        finviz_match = finviz_df[finviz_df["Ticker"].astype(str).str.upper() == ticker]
        if finviz_match.empty:
            log(f"[WARN] No se encontró info Finviz para {ticker}")
            continue

        finviz_row = finviz_match.iloc[0]
        ticker_news_df = pick_relevant_news_subset(news_df, ticker, max_items=4)

        if ticker_news_df.empty:
            analysis = {
                "ticker": ticker,
                "what_is_happening": "No se encontraron noticias relevantes para este ticker entre 12:00am y 9:30am.",
                "key_driver": "",
                "business_impact": "No hay un impacto claro sobre el negocio en este momento.",
                "catalyst_type": "",
                "catalyst_strength": "LOW",
                "sentiment": "Neutral",
                "is_extraordinary": "No",
                "summary": "",
                "institutional_relevance": "",
            }
        else:
            prompt_input = build_prompt_input(ticker, finviz_row, ticker_news_df)

            try:
                analysis = run_ticker_analysis(prompt, prompt_input)
            except Exception as e:
                log(f"[ERROR LLM] {ticker}: {e}")
                fallback_headline = safe_str(ticker_news_df.iloc[0].get("Headline", ""))
                analysis = {
                    "ticker": ticker,
                    "what_is_happening": fallback_headline or "No se pudo interpretar este ticker.",
                    "key_driver": fallback_headline,
                    "business_impact": "No fue posible calcular el impacto con el modelo; revisar el headline principal.",
                    "catalyst_type": "",
                    "catalyst_strength": "LOW",
                    "sentiment": "Neutral",
                    "is_extraordinary": "No",
                    "summary": fallback_headline,
                    "institutional_relevance": "",
                }

        row = {
            "ticker": ticker,
            "company_name": safe_str(finviz_row.get("Company")),
            "sector": safe_str(finviz_row.get("Sector")),
            "industry": safe_str(finviz_row.get("Industry")),
            "gap_pct": safe_str(finviz_row.get("Change")),
            "volume": safe_str(finviz_row.get("Volume")),
            "average_volume": safe_str(finviz_row.get("Avg Volume")),
            "relative_volume": safe_str(finviz_row.get("Rel Volume")),
            "what_happened": safe_str(analysis.get("what_is_happening", "")),
            "market_read": safe_str(analysis.get("summary", "")),
            "what_is_happening": safe_str(analysis.get("what_is_happening", "")),
            "catalyst_strength": safe_str(analysis.get("catalyst_strength", "LOW")).upper() or "LOW",
            "sentiment": safe_str(analysis.get("sentiment", "Neutral")) or "Neutral",
            "key_driver": safe_str(analysis.get("key_driver", "")),
            "business_impact": safe_str(analysis.get("business_impact", "")),
            "catalyst_type": safe_str(analysis.get("catalyst_type", "")),
            "is_extraordinary": safe_str(analysis.get("is_extraordinary", "No")) or "No",
            "institutional_relevance": safe_str(analysis.get("institutional_relevance", "")),
        }

        # Clasificación automática de catalizador
        combined_text = row["what_is_happening"] + " " + row["key_driver"]
        row["catalyst_type"] = classify_catalyst(combined_text)  



        score, breakdown = compute_score(row)
        row["score"] = score
        row["score_breakdown"] = breakdown

        rows.append(row)

    payload = {
        "generated_at": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        "rows": sorted(rows, key=lambda x: -x["score"])
    }

    with open(TICKER_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    log(f"Ticker payload generado: {TICKER_OUTPUT_PATH}")
    log(f"Rows generadas: {len(rows)}")

    return payload


if __name__ == "__main__":
    build_payload()