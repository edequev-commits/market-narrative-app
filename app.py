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
from src.dashboard_mailer import send_dashboard_email
from src.dashboard_sources import build_sources_payload
from src.signal_filter_llm import run_signal_filter


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROMPTS_DIR = BASE_DIR / "prompts"
MONTERREY_TZ = timezone(timedelta(hours=-6))

def main():
    load_dotenv()

    emails = read_messages_from_label(
        label_name="Noticias Trading",
        max_results=200,
        timezone_name="America/Monterrey",
        start_hour=1,
        start_minute=0,
        end_hour=9,
        end_minute=0,
        exclude_senders=["edequev@gmail.com"],
    )

    json_output_file = str(DATA_DIR / "gmail_today.json")
    raw_prompt_input_file = str(DATA_DIR / "gmail_input_for_prompt.txt")
    filtered_signal_file = str(DATA_DIR / "filtered_signal.json")
    filtered_signal_text_file = str(DATA_DIR / "filtered_signal_for_prompt.txt")
    narrative_output_file = str(DATA_DIR / "market_narrative.txt")
    prompt_debug_file = str(DATA_DIR / "final_prompt.txt")
    vital_output_file = str(DATA_DIR / "vital_knowledge_extracted.json")
    reuters_output_file = str(DATA_DIR / "reuters_extracted.json")
    refresh_meta_file = str(DATA_DIR / "last_refresh.json")
    dashboard_payload_file = str(DATA_DIR / "dashboard_payload.json")

    save_json(emails, json_output_file)

    vital_email = find_vital_knowledge_email(emails)
    vital_data = extract_vital_knowledge_sections(vital_email)
    save_json(vital_data, vital_output_file)

    reuters_email = find_reuters_email(emails)
    reuters_data = extract_reuters_sections(reuters_email)
    save_json(reuters_data, reuters_output_file)

    raw_prompt_input = build_prompt_input_from_emails(
        emails=emails,
        vital_data=vital_data,
        reuters_data=reuters_data
    )
    save_text(raw_prompt_input, raw_prompt_input_file)

    print("\nFiltrando señales y resolviendo contradicciones...\n")
    filtered_signal = run_signal_filter(raw_prompt_input)
    save_json(filtered_signal, filtered_signal_file)

    filtered_signal_text = json.dumps(filtered_signal, indent=2, ensure_ascii=False)
    save_text(filtered_signal_text, filtered_signal_text_file)

    sources_payload = build_sources_payload(
        emails=emails,
        vital_data=vital_data,
        reuters_data=reuters_data,
        filtered_signal=filtered_signal
    )

    prompt_template = load_prompt(str(PROMPTS_DIR / "market_narrative.txt"))
    final_prompt = prompt_template.replace("{news_data}", filtered_signal_text)
    save_text(final_prompt, prompt_debug_file)

    print("\nEjecutando modelo de narrativa final...\n")
    narrative = run_market_narrative(final_prompt)
    save_text(narrative, narrative_output_file)

    now = datetime.now(MONTERREY_TZ)
    refresh_meta = {
        "last_refresh_iso": now.isoformat(timespec="seconds"),
        "last_refresh_display": now.strftime("%d-%m-%Y %H:%M:%S"),
        "processed_weekday": now.strftime("%A"),
        "processed_date_display": now.strftime("%d-%m-%Y"),
    }
    save_json(refresh_meta, refresh_meta_file)

    dashboard_payload = {
        "meta": refresh_meta,
        "narrative": narrative,
        "vital": vital_data,
        "reuters": reuters_data,
        "sources": sources_payload,
        "filtered_signal": filtered_signal,
        "email_count": len(emails),
    }
    save_json(dashboard_payload, dashboard_payload_file)

    send_dashboard_email(
        to_email="edequev@gmail.com",
        subject_date=now.strftime("%d-%m-%y"),
        dashboard_payload=dashboard_payload
    )

    print("Narrativa generada correctamente.")
    print("Archivo input bruto:", raw_prompt_input_file)
    print("Archivo señal filtrada JSON:", filtered_signal_file)
    print("Archivo señal filtrada texto:", filtered_signal_text_file)
    print("Archivo narrativa:", narrative_output_file)
    print("Archivo Vital Knowledge:", vital_output_file)
    print("Archivo Reuters:", reuters_output_file)
    print("Archivo dashboard payload:", dashboard_payload_file)
    print("Última actualización:", refresh_meta["last_refresh_display"])


if __name__ == "__main__":
    main()
