import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.gmail_reader import read_messages_from_label
from src.file_utils import save_json, save_text
from src.prompt_input_builder import build_prompt_input_from_emails
from src.llm_runner import load_prompt, run_market_narrative
from src.vital_extractor import find_vital_knowledge_email, extract_vital_knowledge_sections
from src.reuters_extractor import find_reuters_email, extract_reuters_sections
from src.cnbc_extractor import find_cnbc_emails, extract_cnbc_sections
from src.dashboard_sources import build_sources_payload
from src.signal_filter_llm import run_signal_filter
from src.top_stocks_builder import build_top_stocks_in_play
from src.dashboard_mailer import send_dashboard_email


CONFIG_PATH = Path(__file__).resolve().parent / "config" / "app_config.json"

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_config()

REPO_DIR = Path(__file__).resolve().parent

BASE_DIR = REPO_DIR
DATA_DIR = REPO_DIR / "data"
PROMPTS_DIR = REPO_DIR / "prompts"
DIST_DIR = REPO_DIR / "dist"
RUNS_DIR = REPO_DIR / "data" / "runs"
LOGS_DIR = REPO_DIR / "logs"
DASHBOARD_PAYLOAD_FILE = REPO_DIR / "data" / "dashboard_payload.json"




GMAIL_LABEL_NAME = CONFIG["gmail"]["label_name"]
GMAIL_MAX_MESSAGES = CONFIG["gmail"]["max_messages"]

MACRO_WINDOW_START = CONFIG["windows"]["macro"]["start_time"]
MACRO_WINDOW_END = CONFIG["windows"]["macro"]["end_time"]

MONTERREY_TZ = timezone(timedelta(hours=-6))






def extract_raw_micro_from_vital(vital_data: dict) -> str:
    micro_lines = []

    if not vital_data:
        return ""

    for key, value in vital_data.items():
        key_lower = key.lower()

        if any(word in key_lower for word in [
            "micro",
            "consumer",
            "tmt",
            "financial",
            "energy",
            "industrial",
            "m&a",
            "strategic"
        ]):
            if value:
                micro_lines.append(f"\n[{key.upper()}]\n{value}")

    return "\n".join(micro_lines)


def build_sources_fallback(vital_data: dict, reuters_data: dict, cnbc_data: dict) -> list[dict]:
    fallback = []

    if vital_data and (vital_data.get("source_subject") or vital_data.get("source_from")):
        fallback.append({
            "fuente": vital_data.get("source_from", "Vital Knowledge"),
            "fecha": vital_data.get("source_date", ""),
            "detalle": vital_data.get("source_subject", "Vital Knowledge"),
        })

    if reuters_data and (reuters_data.get("source_subject") or reuters_data.get("source_from")):
        fallback.append({
            "fuente": reuters_data.get("source_from", "Reuters Daily Briefing"),
            "fecha": reuters_data.get("source_date", ""),
            "detalle": reuters_data.get("source_subject", "Reuters Daily Briefing"),
        })


    if cnbc_data and cnbc_data.get("selected_emails"):
        for item in cnbc_data.get("selected_emails", []):

            sender = (item.get("from") or "").lower()

            if "morningsquawk@response.cnbc.com" in sender:
                fuente = "CNBC Morning Squawk"
            elif "breakingnews@response.cnbc.com" in sender:
                fuente = "CNBC Breaking News"
            else:
                fuente = "CNBC"

            fallback.append({
                "fuente": fuente,
                "fecha": item.get("date", ""),
                "detalle": item.get("subject", ""),
            })


    return fallback


def main():
    load_dotenv()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    macro_start_hour, macro_start_minute = map(int, MACRO_WINDOW_START.split(":"))
    macro_end_hour, macro_end_minute = map(int, MACRO_WINDOW_END.split(":"))

    emails = read_messages_from_label(
        label_name=GMAIL_LABEL_NAME,
        max_results=GMAIL_MAX_MESSAGES,
        timezone_name="America/Monterrey",
        start_hour=macro_start_hour,
        start_minute=macro_start_minute,
        end_hour=macro_end_hour,
        end_minute=macro_end_minute,
        exclude_senders=["edequev@gmail.com"],
    )


    json_output_file = str(DATA_DIR / "gmail_today.json")
    raw_prompt_input_file = str(DATA_DIR / "gmail_input_for_prompt.txt")
    filtered_signal_file = str(DATA_DIR / "filtered_signal.json")
    filtered_signal_text_file = str(DATA_DIR / "filtered_signal_for_prompt.txt")
    narrative_output_file = str(DATA_DIR / "market_narrative.txt")
    regime_output_file = str(DATA_DIR / "market_regime.txt")
    drivers_output_file = str(DATA_DIR / "market_drivers.txt")
    prompt_debug_file = str(DATA_DIR / "final_prompt.txt")
    regime_prompt_debug_file = str(DATA_DIR / "final_regime_prompt.txt")
    vital_output_file = str(DATA_DIR / "vital_knowledge_extracted.json")
    reuters_output_file = str(DATA_DIR / "reuters_extracted.json")
    cnbc_output_file = str(DATA_DIR / "cnbc_extracted.json")
    refresh_meta_file = str(DATA_DIR / "last_refresh.json")
    dashboard_payload_file = str(DASHBOARD_PAYLOAD_FILE)
    top_stocks_output_file = str(DATA_DIR / "top_stocks_in_play.json")

    save_json(emails, json_output_file)

    vital_email = find_vital_knowledge_email(emails)
    vital_data = extract_vital_knowledge_sections(vital_email)
    save_json(vital_data, vital_output_file)

    reuters_email = find_reuters_email(emails)
    reuters_data = extract_reuters_sections(reuters_email)
    save_json(reuters_data, reuters_output_file)

    cnbc_emails = find_cnbc_emails(emails, limit=10)
    cnbc_data = extract_cnbc_sections(cnbc_emails)
    save_json(cnbc_data, cnbc_output_file)

    raw_prompt_input = build_prompt_input_from_emails(
        emails=emails,
        vital_data=vital_data,
        reuters_data=reuters_data,
        cnbc_data=cnbc_data,
    )
    save_text(raw_prompt_input, raw_prompt_input_file)

    filtered_signal = run_signal_filter(raw_prompt_input)
    save_json(filtered_signal, filtered_signal_file)

    raw_micro = extract_raw_micro_from_vital(vital_data)

    filtered_signal_text = f"""
{json.dumps(filtered_signal, indent=2, ensure_ascii=False)}

=== MICRO DRIVERS RAW (NO FILTRADOS) ===
{raw_micro}
"""
    save_text(filtered_signal_text, filtered_signal_text_file)

    narrative_prompt_template = load_prompt(str(PROMPTS_DIR / "market_narrative.txt"))
    final_prompt = narrative_prompt_template.replace("{news_data}", filtered_signal_text)
    save_text(final_prompt, prompt_debug_file)
    narrative = run_market_narrative(final_prompt)
    save_text(narrative, narrative_output_file)

    drivers_prompt_template = load_prompt(str(PROMPTS_DIR / "market_drivers.txt"))
    final_drivers_prompt = drivers_prompt_template.replace("{news_data}", filtered_signal_text)
    market_drivers = run_market_narrative(final_drivers_prompt)
    save_text(market_drivers, drivers_output_file)

    regime_prompt_template = load_prompt(str(PROMPTS_DIR / "market_regime_snapshot.txt"))
    final_regime_prompt = regime_prompt_template.replace("{news_data}", filtered_signal_text)
    save_text(final_regime_prompt, regime_prompt_debug_file)
    regime = run_market_narrative(final_regime_prompt)
    save_text(regime, regime_output_file)

    top_stocks_in_play = build_top_stocks_in_play(
        filtered_signal=filtered_signal,
        vital_data=vital_data,
        reuters_data=reuters_data,
        cnbc_data=cnbc_data,
        narrative=narrative,
        regime=regime,
        max_stocks=6,
    )
    save_json(top_stocks_in_play, top_stocks_output_file)

   
    try:
        sources_payload = build_sources_payload(
            emails=emails,
            vital_data=vital_data,
            reuters_data=reuters_data,
            filtered_signal=filtered_signal
        )
    except Exception:
         sources_payload = []

    # 🔥 AGREGAR ESTE BLOQUE JUSTO DEBAJO
    cnbc_sources = build_sources_fallback(
        vital_data={},
        reuters_data={},
        cnbc_data=cnbc_data
    )

    sources_payload.extend(cnbc_sources)


    if not sources_payload:
        sources_payload = build_sources_fallback(
            vital_data=vital_data,
            reuters_data=reuters_data,
            cnbc_data=cnbc_data,
        )

    now = datetime.now(MONTERREY_TZ)
    refresh_meta = {
        "last_refresh_iso": now.isoformat(timespec="seconds"),
        "last_refresh_display": now.strftime("%d-%m-%Y %H:%M:%S"),
    }
    save_json(refresh_meta, refresh_meta_file)

    dashboard_payload = {
        "meta": refresh_meta,
        "narrative": narrative,
        "regime": regime,
        "market_drivers": market_drivers,
        "top_stocks_in_play": top_stocks_in_play,
        "sources": sources_payload,
        "vital": vital_data,
        "reuters": reuters_data,
        "cnbc": cnbc_data,
    }
    save_json(dashboard_payload, dashboard_payload_file)

    send_dashboard_email(
        to_email="edequev@gmail.com",
        subject_date=now.strftime("%d-%m-%y"),
        dashboard_payload=dashboard_payload
    )


if __name__ == "__main__":
    main()