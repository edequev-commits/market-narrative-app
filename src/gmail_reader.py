from __future__ import print_function

import os
import base64
import re
import time
from datetime import datetime, time as dt_time
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_gmail_service():
    creds = None
    token_path = os.path.join("config", "token.json")
    credentials_path = os.path.join("config", "credentials.json")

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    return service


def _execute_with_retry(request, max_attempts: int = 5, base_sleep: float = 1.5):
    """
    Reintenta errores transitorios de Gmail API.
    """
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            return request.execute()

        except HttpError as e:
            last_error = e
            status = getattr(e.resp, "status", None)
            message = str(e).lower()

            retryable = (
                status in (429, 500, 502, 503, 504)
                or "backenderror" in message
                or "rate limit" in message
                or "quota" in message
            )

            if not retryable or attempt == max_attempts:
                raise

            sleep_time = base_sleep * (2 ** (attempt - 1))
            print(
                f"[GMAIL RETRY] intento {attempt}/{max_attempts} "
                f"falló con status={status}. Reintentando en {sleep_time:.1f}s..."
            )
            time.sleep(sleep_time)

        except Exception as e:
            last_error = e
            if attempt == max_attempts:
                raise

            sleep_time = base_sleep * (2 ** (attempt - 1))
            print(
                f"[GMAIL RETRY] intento {attempt}/{max_attempts} "
                f"falló por error inesperado. Reintentando en {sleep_time:.1f}s..."
            )
            time.sleep(sleep_time)

    if last_error:
        raise last_error


def get_label_id(service, label_name: str):
    results = _execute_with_retry(service.users().labels().list(userId="me"))
    labels = results.get("labels", [])

    for label in labels:
        if label["name"].lower() == label_name.lower():
            return label["id"]

    return None


def decode_base64_data(data: str) -> str:
    if not data:
        return ""
    try:
        missing_padding = len(data) % 4
        if missing_padding:
            data += "=" * (4 - missing_padding)
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def html_to_text(html: str) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "meta", "head", "title"]):
        tag.decompose()

    for br in soup.find_all("br"):
        br.replace_with("\n")

    for li in soup.find_all("li"):
        li.insert_before("\n• ")

    for tag_name in ["p", "div", "tr", "table", "h1", "h2", "h3", "h4", "section"]:
        for tag in soup.find_all(tag_name):
            tag.append("\n")

    text = soup.get_text(separator=" ")

    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def extract_parts(payload):
    parts_found = []

    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data", "")

    if mime_type in ("text/plain", "text/html") and data:
        parts_found.append({
            "mimeType": mime_type,
            "content": decode_base64_data(data)
        })

    for part in payload.get("parts", []):
        parts_found.extend(extract_parts(part))

    return parts_found


def is_bad_plain_candidate(text: str) -> bool:
    lowered = text.lower()

    bad_markers = [
        "this email doesn't support html",
        "some texts may not be displayed properly",
        "click here to read it in full online",
        "looks like your email provider is scrambling the email",
        "view online",
        "read it in full online",
    ]

    return any(marker in lowered for marker in bad_markers)


def extract_best_body_text(payload) -> str:
    parts = extract_parts(payload)

    plain_candidates = []
    html_candidates = []

    for part in parts:
        mime_type = part.get("mimeType", "")
        content = part.get("content", "").strip()

        if not content:
            continue

        if mime_type == "text/plain":
            plain_candidates.append(content)
        elif mime_type == "text/html":
            html_candidates.append(content)

    good_plain_candidates = [
        x for x in plain_candidates
        if len(x) > 400 and not is_bad_plain_candidate(x)
    ]

    if good_plain_candidates:
        return max(good_plain_candidates, key=len)

    html_texts = []
    for candidate in html_candidates:
        converted = html_to_text(candidate)
        if len(converted) > 200:
            html_texts.append(converted)

    if html_texts:
        return max(html_texts, key=len)

    if plain_candidates:
        return max(plain_candidates, key=len)

    if html_candidates:
        converted_html = [html_to_text(x) for x in html_candidates]
        converted_html = [x for x in converted_html if x.strip()]
        if converted_html:
            return max(converted_html, key=len)

    return ""


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r", "\n")
    text = text.replace("\xa0", " ")

    junk_patterns = [
        r"The email doesn't support HTML,?\s*some texts may not be displayed properly\.?",
        r"Looks like your email provider is scrambling the email.*?(?=\n|$)",
        r"Click here to read it in full online:.*?(?=\n|$)",
        r"View Online.*?(?=\n|$)",
        r"We'd hate to see you go, but if you want to unsubscribe.*?(?=\n|$)",
        r"This message was sent to .*?(?=\n|$)",
        r"Manage preferences.*?(?=\n|$)",
        r"Unsubscribe.*?(?=\n|$)",
    ]

    for pattern in junk_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    text = re.sub(r"https?://\S+\.(png|jpg|jpeg|gif|webp)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\s*https?://[^\]]+\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://\S{60,}", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(\[\s*\]\s*){1,}", "", text)
    text = re.sub(r"[_=~-]{6,}", "", text)
    text = re.sub(r"(?m)^\s*\*\s+", "• ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"([a-z0-9\)])([A-Z])", r"\1 \2", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def read_messages_from_label(
    label_name: str = "Noticias Trading",
    max_results: int = 200,
    timezone_name: str = "America/Mexico_City",
    start_hour: int = 1,
    start_minute: int = 0,
    end_hour: int = 9,
    end_minute: int = 0,
    exclude_senders: list[str] | None = None,
):
    service = get_gmail_service()

    exclude_senders = exclude_senders or []
    exclude_senders = [x.lower().strip() for x in exclude_senders if x and x.strip()]

    label_id = get_label_id(service, label_name)
    if not label_id:
        raise ValueError(f"No se encontró la etiqueta: {label_name}")

    tz = ZoneInfo(timezone_name)
    today = datetime.now(tz).date()
    start_time = dt_time(start_hour, start_minute, 0)
    end_time = dt_time(end_hour, end_minute, 0)

    collected_messages = []
    next_page_token = None

    while True:
        response = _execute_with_retry(
            service.users().messages().list(
                userId="me",
                labelIds=[label_id],
                maxResults=100,
                pageToken=next_page_token
            )
        )

        messages = response.get("messages", [])
        collected_messages.extend(messages)

        if len(collected_messages) >= max_results:
            collected_messages = collected_messages[:max_results]
            break

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    output = []

    for msg in collected_messages:
        try:
            msg_data = _execute_with_retry(
                service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="full"
                )
            )
        except Exception as e:
            print(f"[GMAIL SKIP] No se pudo leer el mensaje {msg.get('id', '')}: {e}")
            continue

        payload = msg_data.get("payload", {})
        headers = payload.get("headers", [])

        subject = ""
        sender = ""
        date_str = ""

        for h in headers:
            name = h.get("name", "").lower()
            if name == "subject":
                subject = h.get("value", "")
            elif name == "from":
                sender = h.get("value", "")
            elif name == "date":
                date_str = h.get("value", "")

        body_text = extract_best_body_text(payload)
        body_text = clean_text(body_text)

        try:
            parsed_date = parsedate_to_datetime(date_str)

            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=tz)
            else:
                parsed_date = parsed_date.astimezone(tz)

            email_date = parsed_date.date()
            email_time = parsed_date.time().replace(tzinfo=None)
        except Exception:
            continue

        sender_clean = clean_text(sender)
        sender_lower = sender_clean.lower()

        if any(excluded in sender_lower for excluded in exclude_senders):
            continue

        if email_date == today and start_time <= email_time <= end_time:
            output.append({
                "id": msg["id"],
                "subject": clean_text(subject),
                "from": sender_clean,
                "date": parsed_date.isoformat(),
                "body": body_text
            })

    output.sort(key=lambda x: x["date"])
    return output