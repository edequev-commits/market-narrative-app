# =========================
# FINVIZ NEWS + SNAPSHOT AUTOMATION
# VERSION ESTABLE SIN GRAFICAS
# =========================

import os
import re
import ssl
import time
import smtplib
import mimetypes
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup


# =========================
# CONFIGURACIÓN
# =========================


BASE_DIR = r"C:\Trading\finviz_news"
OUTPUT_DIR = os.path.join(BASE_DIR, "finviz_news")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

GAP_UP_FILE = os.path.join(BASE_DIR, "tradeideas_gap_up.txt")
GAP_DOWN_FILE = os.path.join(BASE_DIR, "tradeideas_gap_down.txt")


EMAIL_TO = "edequev@gmail.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finviz.com/",
}

REQUEST_TIMEOUT = 20
DELAY_BETWEEN_TICKERS_SEC = 3
RETRY_WAIT_ON_429_SEC = 12
MAX_FETCH_ATTEMPTS = 2  # intento inicial + 1 reintento largo

NEWS_COLUMNS = [
    "Ticker",
    "NewsDateTime",
    "Headline",
    "Link",
    "Source",
    "Priority",
]

FINVIZ_TARGET_COLUMNS = [
    "Ticker",
    "Company",
    "Sector",
    "Industry",
    "Country",
    "Market Cap",
    "Price",
    "Change",
    "Volume",
    "Avg Volume",
    "Rel Volume",
    "Float",
    "Short Float",
    "ATR",
    "Beta",
    "Earnings",
    "Target Price",
    "Forward P/E",
    "EPS next Y",
    "Sales past 5Y",
    "Inst Own",
    "Insider Own",
    "Gap_Type",
]


# =========================
# UTILIDADES GENERALES
# =========================

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def ensure_output_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)


def safe_get_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"No existe la variable de entorno requerida: {name}")
    return value


def load_tickers(file_path: str, gap_type: str) -> List[Tuple[str, str]]:
    tickers = []
    if not os.path.exists(file_path):
        log(f"[WARN] No existe archivo: {file_path}")
        return tickers

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            ticker = line.strip().upper().replace("$", "")
            if ticker:
                tickers.append((gap_type, ticker))

    return tickers


def dedupe_tickers(ticker_pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seen = set()
    result = []
    for gap_type, ticker in ticker_pairs:
        key = (gap_type, ticker)
        if key not in seen:
            seen.add(key)
            result.append((gap_type, ticker))
    return result


def get_run_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def normalize_whitespace(text: str) -> str:
    return " ".join((text or "").split())


def is_news_from_today(news_dt: Optional[datetime]) -> bool:
    if news_dt is None:
        return False
    return news_dt.date() == datetime.now().date()


def is_valid_trading_news(news_dt: Optional[datetime]) -> bool:
    if news_dt is None:
        return False

    now = datetime.now()

    # Solo noticias del día actual
    if news_dt.date() != now.date():
        return False

    # Solo hasta las 9:30 AM
    cutoff = news_dt.replace(hour=9, minute=30, second=0, microsecond=0)
    return news_dt <= cutoff


# =========================
# PARSING DE FECHAS FINVIZ
# =========================

def parse_finviz_news_datetime(date_text: str) -> Optional[datetime]:
    if not date_text:
        return None

    date_text = date_text.strip()
    now = datetime.now()

    m_today = re.match(r"^Today\s+(\d{1,2}:\d{2}[AP]M)$", date_text, re.IGNORECASE)
    if m_today:
        time_part = m_today.group(1).upper()
        return datetime.strptime(
            f"{now.strftime('%Y-%m-%d')} {time_part}",
            "%Y-%m-%d %I:%M%p"
        )

    m_yesterday = re.match(r"^Yesterday\s+(\d{1,2}:\d{2}[AP]M)$", date_text, re.IGNORECASE)
    if m_yesterday:
        dt = now - timedelta(days=1)
        time_part = m_yesterday.group(1).upper()
        return datetime.strptime(
            f"{dt.strftime('%Y-%m-%d')} {time_part}",
            "%Y-%m-%d %I:%M%p"
        )

    m_full = re.match(r"^([A-Za-z]{3}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}[AP]M)$", date_text)
    if m_full:
        date_part = m_full.group(1)
        time_part = m_full.group(2).upper()
        try:
            return datetime.strptime(f"{date_part} {time_part}", "%b-%d-%y %I:%M%p")
        except ValueError:
            return None

    m_time_only = re.match(r"^(\d{1,2}:\d{2}[AP]M)$", date_text, re.IGNORECASE)
    if m_time_only:
        return None

    return None


# =========================
# SCRAPING FINVIZ
# =========================

def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def fetch_finviz_quote_page(session: requests.Session, ticker: str) -> Tuple[Optional[BeautifulSoup], Optional[str]]:
    url = f"https://finviz.com/quote.ashx?t={ticker}"

    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)

            if response.status_code == 429:
                if attempt < MAX_FETCH_ATTEMPTS:
                    log(f"[RETRY] {ticker} - Intento {attempt} bloqueado (429). Esperando {RETRY_WAIT_ON_429_SEC}s...")
                    time.sleep(RETRY_WAIT_ON_429_SEC)
                    continue
                return None, "429"

            if response.status_code >= 400:
                return None, f"HTTP_{response.status_code}"

            return BeautifulSoup(response.text, "html.parser"), None

        except requests.RequestException:
            if attempt < MAX_FETCH_ATTEMPTS:
                time.sleep(5)
                continue
            return None, "REQUEST_ERROR"

    return None, "UNKNOWN_ERROR"


def extract_company_header(soup: BeautifulSoup) -> Dict[str, str]:
    info = {
        "Company": "",
        "Sector": "",
        "Industry": "",
        "Country": "",
    }

    company_tag = soup.find("div", class_="quote-header_left")
    if company_tag:
        a_tags = company_tag.find_all("a")
        if a_tags:
            info["Company"] = normalize_whitespace(a_tags[0].get_text(" ", strip=True))

    if not info["Company"]:
        title_tag = soup.find("title")
        if title_tag:
            title_text = normalize_whitespace(title_tag.get_text(" ", strip=True))
            info["Company"] = title_text.replace("Stock Price and Chart", "").replace("Stock Quote", "").strip(" -")

    links = soup.select("div.quote-links a.tab-link")
    if len(links) >= 3:
        info["Sector"] = normalize_whitespace(links[0].get_text(" ", strip=True))
        info["Industry"] = normalize_whitespace(links[1].get_text(" ", strip=True))
        info["Country"] = normalize_whitespace(links[2].get_text(" ", strip=True))
    else:
        fallback_links = soup.select("div.quote-links a")
        if len(fallback_links) >= 3:
            info["Sector"] = normalize_whitespace(fallback_links[0].get_text(" ", strip=True))
            info["Industry"] = normalize_whitespace(fallback_links[1].get_text(" ", strip=True))
            info["Country"] = normalize_whitespace(fallback_links[2].get_text(" ", strip=True))

    return info


def get_finviz_news_from_soup(soup: BeautifulSoup) -> List[Dict[str, object]]:
    news = []
    table = soup.find("table", class_="fullview-news-outer")
    if not table:
        table = soup.find(id="news-table")
    if not table:
        return news

    rows = table.find_all("tr")
    current_date_prefix = None

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 2:
            continue

        raw_date = normalize_whitespace(cols[0].get_text(" ", strip=True))
        link_tag = cols[1].find("a")
        if not link_tag:
            continue

        headline = normalize_whitespace(link_tag.get_text(" ", strip=True))
        link = link_tag.get("href", "").strip()

        if link.startswith("/"):
            link = "https://finviz.com" + link

        parsed_dt = parse_finviz_news_datetime(raw_date)

        if parsed_dt is None:
            time_only_match = re.match(r"^(\d{1,2}:\d{2}[AP]M)$", raw_date, re.IGNORECASE)
            if time_only_match and current_date_prefix is not None:
                try:
                    parsed_dt = datetime.strptime(
                        f"{current_date_prefix} {time_only_match.group(1).upper()}",
                        "%Y-%m-%d %I:%M%p"
                    )
                except ValueError:
                    parsed_dt = None

        if parsed_dt is not None:
            current_date_prefix = parsed_dt.strftime("%Y-%m-%d")

        news.append({
            "datetime_obj": parsed_dt,
            "datetime_str": parsed_dt.strftime("%Y-%m-%d %H:%M:%S") if parsed_dt else "",
            "headline": headline,
            "link": link,
        })

    return news


def get_finviz_ai_summary_from_soup(soup: BeautifulSoup, ticker: str) -> Optional[Dict[str, str]]:
    try:
        candidates = []

        for tag in soup.find_all(["a", "div", "span", "p"], limit=400):
            text = normalize_whitespace(tag.get_text(" ", strip=True))
            if not text:
                continue

            if len(text) < 50 or len(text) > 400:
                continue

            lower_text = text.lower()
            score = 0

            if "today," in lower_text:
                score += 3
            if "am" in lower_text or "pm" in lower_text:
                score += 2
            if ticker.lower() in lower_text:
                score += 3
            if "%" in text:
                score += 1
            if any(word in lower_text for word in [
                "oil", "iran", "ceasefire", "surging", "premarket",
                "ai", "earnings", "revenue", "guidance", "upgrade",
                "downgrade", "contract", "deal"
            ]):
                score += 2

            if score >= 5:
                candidates.append((score, text))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_text = candidates[0][1]

        return {
            "headline": best_text,
            "link": "",
            "source": "FINVIZ_AI",
            "priority": "HIGH",
        }

    except Exception:
        return None


def get_finviz_data_from_soup(soup: BeautifulSoup, ticker: str) -> Dict[str, str]:
    data = {
        "Ticker": ticker,
        "Company": "",
        "Sector": "",
        "Industry": "",
        "Country": "",
        "Price": "",
        "Change": "",
        "Volume": "",
        "Avg Volume": "",
        "Rel Volume": "",
        "Float": "",
    }

    header_info = extract_company_header(soup)
    data.update(header_info)

    table = soup.find("table", class_="snapshot-table2")
    if table:
        cells = table.find_all("td")
        for i in range(0, len(cells), 2):
            if i + 1 < len(cells):
                key = normalize_whitespace(cells[i].get_text(" ", strip=True))
                val = normalize_whitespace(cells[i + 1].get_text(" ", strip=True))

                if key == "Price":
                    data["Price"] = val
                elif key == "Change":
                    data["Change"] = val
                elif key == "Volume":
                    data["Volume"] = val
                elif key == "Avg Volume":
                    data["Avg Volume"] = val
                elif key == "Rel Volume":
                    data["Rel Volume"] = val
                elif key == "Shs Float":
                    data["Float"] = val
                else:
                    data[key] = val

    normalized = {}
    for col in FINVIZ_TARGET_COLUMNS:
        normalized[col] = data.get(col, "")

    return normalized


# =========================
# EMAIL
# =========================

def attach_file(msg: EmailMessage, file_path: str) -> None:
    ctype, encoding = mimetypes.guess_type(file_path)
    if ctype is None or encoding is not None:
        ctype = "application/octet-stream"

    maintype, subtype = ctype.split("/", 1)

    with open(file_path, "rb") as fp:
        msg.add_attachment(
            fp.read(),
            maintype=maintype,
            subtype=subtype,
            filename=os.path.basename(file_path)
        )


def send_email(files: List[str], subject: str) -> None:
    gmail_user = safe_get_env("GMAIL_USER")
    gmail_app_password = safe_get_env("GMAIL_APP_PASSWORD")

    msg = EmailMessage()
    msg["From"] = gmail_user
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.set_content("Adjunto archivos CSV generados automáticamente.")

    for file_path in files:
        attach_file(msg, file_path)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
        smtp.login(gmail_user, gmail_app_password)
        smtp.send_message(msg)


# =========================
# EXPORTACIÓN
# =========================

def enforce_news_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in NEWS_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[NEWS_COLUMNS]


def enforce_finviz_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in FINVIZ_TARGET_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[FINVIZ_TARGET_COLUMNS]


def export_to_excel(df: pd.DataFrame, excel_path: str, sheet_name: str = "Sheet1") -> None:
    log(f"Generando Excel: {excel_path}")

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        for col in ws.columns:
            max_length = 0
            col_letter = col[0].column_letter

            for cell in col:
                try:
                    if cell.value is not None:
                        max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    pass

            ws.column_dimensions[col_letter].width = min(max_length + 2, 60)


def save_outputs(news_rows: List[Dict[str, object]], finviz_rows: List[Dict[str, object]], run_ts: str) -> Tuple[str, str, str, str]:
    news_df = pd.DataFrame(news_rows)
    finviz_df = pd.DataFrame(finviz_rows)

    if news_df.empty:
        news_df = pd.DataFrame(columns=NEWS_COLUMNS)
    else:
        news_df = enforce_news_columns(news_df)

    if finviz_df.empty:
        finviz_df = pd.DataFrame(columns=FINVIZ_TARGET_COLUMNS)
    else:
        finviz_df = enforce_finviz_columns(finviz_df)

    news_xlsx = os.path.join(OUTPUT_DIR, f"news_output_{run_ts}.xlsx")
    news_csv = os.path.join(OUTPUT_DIR, f"news_output_{run_ts}.csv")
    finviz_xlsx = os.path.join(OUTPUT_DIR, f"finviz_data_{run_ts}.xlsx")
    finviz_csv = os.path.join(OUTPUT_DIR, f"finviz_data_{run_ts}.csv")


    news_df.to_csv(news_csv, index=False, encoding="utf-8-sig")
    finviz_df.to_csv(finviz_csv, index=False, encoding="utf-8-sig")

    export_to_excel(news_df, news_xlsx, sheet_name="News")
    export_to_excel(finviz_df, finviz_xlsx, sheet_name="Finviz_Data")

    return news_xlsx, news_csv, finviz_xlsx, finviz_csv


# =========================
# MAIN
# =========================

def main() -> None:
    log("Inicio de ejecución")
    ensure_output_dir()

    run_ts = get_run_timestamp()
    email_subject = f"Acciones in play {run_ts}"

    tickers = []
    tickers.extend(load_tickers(GAP_UP_FILE, "GAP_UP"))
    tickers.extend(load_tickers(GAP_DOWN_FILE, "GAP_DOWN"))
    tickers = dedupe_tickers(tickers)

    if not tickers:
        log("[WARN] No se encontraron tickers en archivos de entrada.")

    log(f"Tickers a procesar: {len(tickers)}")

    session = create_session()

    news_rows: List[Dict[str, object]] = []
    finviz_rows: List[Dict[str, object]] = []
    skipped_tickers: List[str] = []

    for idx, (gap_type, ticker) in enumerate(tickers, start=1):
        time.sleep(DELAY_BETWEEN_TICKERS_SEC)
        log(f"Procesando {idx}/{len(tickers)}: {ticker} ({gap_type})")

        soup, fetch_error = fetch_finviz_quote_page(session, ticker)

        if soup is None:
            if fetch_error == "429":
                log(f"[WARN PAGE] {ticker}: Finviz bloqueó temporalmente este ticker (429).")
            else:
                log(f"[WARN PAGE] {ticker}: no se pudo obtener la página ({fetch_error}).")

            skipped_tickers.append(ticker)
            continue

        try:
            ticker_news = get_finviz_news_from_soup(soup)
            ai_summary = get_finviz_ai_summary_from_soup(soup, ticker)

            log(f"  Noticias encontradas para {ticker}: {len(ticker_news)}")

            news_added_for_ticker = 0

            for item in ticker_news:
                if not is_valid_trading_news(item["datetime_obj"]):
                    continue

                row = {
                    "Ticker": ticker,
                    "NewsDateTime": item["datetime_str"],
                    "Headline": item["headline"],
                    "Link": item["link"],
                    "Source": "FINVIZ_NEWS",
                    "Priority": "NORMAL",
                }
                news_rows.append(row)
                news_added_for_ticker += 1

            log(f"  Noticias válidas agregadas para {ticker}: {news_added_for_ticker}")

            if ai_summary:
                now_dt = datetime.now()
                cutoff = now_dt.replace(hour=9, minute=30, second=0, microsecond=0)

                if now_dt <= cutoff:
                    news_rows.append({
                        "Ticker": ticker,
                        "NewsDateTime": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "Headline": ai_summary["headline"],
                        "Link": ai_summary["link"],
                        "Source": ai_summary["source"],
                        "Priority": ai_summary["priority"],
                    })
                    log(f"  AI Summary agregado para {ticker}")
                else:
                    log(f"  AI Summary ignorado (fuera de horario) para {ticker}")

            if news_added_for_ticker == 0:
                log(f"  [INFO] {ticker} no tuvo noticias válidas para trading")

        except Exception as e:
            log(f"[ERROR NEWS] {ticker}: {e}")

        try:
            finviz_row = get_finviz_data_from_soup(soup, ticker)
            finviz_row["Gap_Type"] = gap_type

            log(
                f"  SNAPSHOT {ticker} | "
                f"Price={finviz_row.get('Price', '')} | "
                f"Change={finviz_row.get('Change', '')} | "
                f"Volume={finviz_row.get('Volume', '')} | "
                f"AvgVol={finviz_row.get('Avg Volume', '')} | "
                f"RVOL={finviz_row.get('Rel Volume', '')}"
            )

            finviz_rows.append(finviz_row)

        except Exception as e:
            log(f"[ERROR SNAPSHOT] {ticker}: {e}")

    log(f"Total noticias agregadas al archivo final: {len(news_rows)}")
    log(f"Total filas técnicas agregadas al archivo final: {len(finviz_rows)}")

    if skipped_tickers:
        log(f"Tickers omitidos por problema de descarga: {', '.join(skipped_tickers)}")

    news_xlsx, news_csv, finviz_xlsx, finviz_csv = save_outputs(news_rows, finviz_rows, run_ts)
    log(f"Archivo generado: {news_xlsx}")
    log(f"Archivo generado: {news_csv}")
    log(f"Archivo generado: {finviz_xlsx}")
    log(f"Archivo generado: {finviz_csv}")

    # Copia de CSVs a outputs/ para consumo del dashboard
    news_csv_copy = os.path.join(OUTPUTS_DIR, os.path.basename(news_csv))
    finviz_csv_copy = os.path.join(OUTPUTS_DIR, os.path.basename(finviz_csv))

    import shutil
    shutil.copy2(news_csv, news_csv_copy)
    shutil.copy2(finviz_csv, finviz_csv_copy)

    log(f"[EXPORT] CSV copiado a outputs: {news_csv_copy}")
    log(f"[EXPORT] CSV copiado a outputs: {finviz_csv_copy}")



    try:
        send_email([news_csv, finviz_csv], email_subject)
        log(f"Email enviado correctamente con asunto: {email_subject}")
        log(f"Adjuntos enviados: {os.path.basename(news_csv)}, {os.path.basename(finviz_csv)}")
    except Exception as e:
        log(f"[ERROR EMAIL] {e}")

    log("Fin de ejecución")


if __name__ == "__main__":
    main()