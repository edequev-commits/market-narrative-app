import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def parse_iso_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat((value or "").strip())
    except Exception:
        return datetime.min


def find_cnbc_emails(emails: list, limit: int = 3) -> list:
    matches = []

    for email in emails:
        sender = (email.get("from", "") or "").lower()
        subject = (email.get("subject", "") or "").lower()
        body = (email.get("body", "") or "").lower()

        if "breakingnews@response.cnbc.com" not in sender:
            continue

        score = 0
        score += 10

        if "breaking news" in subject:
            score += 3
        if "cnbc.com" in body:
            score += 1

        matches.append({
            "score": score,
            "date_obj": parse_iso_datetime(email.get("date", "")),
            "email": email,
        })

    matches.sort(key=lambda x: (x["date_obj"], x["score"]), reverse=True)

    selected = []
    for item in matches[:limit]:
        email = dict(item["email"])
        email["_recency_rank"] = len(selected) + 1
        selected.append(email)

    return selected


def extract_links(text: str) -> list[str]:
    if not text:
        return []

    links = re.findall(r"https?://[^\s<>\"]+", text)
    clean_links = []

    for link in links:
        link = link.rstrip(").,;]")
        if link not in clean_links:
            clean_links.append(link)

    return clean_links


def fetch_link_summary(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        meta_desc = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            meta_desc = meta.get("content", "").strip()

        paragraphs = []
        for p in soup.find_all("p"):
            text = " ".join(p.get_text(" ", strip=True).split())
            if len(text) >= 80:
                paragraphs.append(text)
            if len(paragraphs) >= 3:
                break

        return {
            "url": url,
            "title": title,
            "summary": meta_desc,
            "key_paragraphs": paragraphs,
            "status": "ok"
        }

    except Exception as e:
        return {
            "url": url,
            "title": "",
            "summary": "",
            "key_paragraphs": [],
            "status": f"error: {str(e)}"
        }


def extract_cnbc_sections(cnbc_emails: list) -> dict:
    if not cnbc_emails:
        return {
            "source_subject": "",
            "source_from": "",
            "source_date": "",
            "body_excerpt": "",
            "links": [],
            "fetched_links": [],
            "selected_emails": [],
            "parsed_at": datetime.now().isoformat(timespec="seconds"),
        }

    selected_emails = []
    all_links = []
    seen_links = set()
    excerpts = []

    for email in cnbc_emails:
        subject = email.get("subject", "")
        sender = email.get("from", "")
        date = email.get("date", "")
        body = email.get("body", "") or ""
        rank = email.get("_recency_rank", "")

        selected_emails.append({
            "subject": subject,
            "from": sender,
            "date": date,
            "recency_rank": rank,
        })

        excerpts.append(
            f"[CNBC #{rank}] {subject}\nFecha: {date}\n{body[:1500]}"
        )

        for link in extract_links(body):
            if link not in seen_links:
                seen_links.add(link)
                all_links.append(link)

    fetched_links = []
    for link in all_links[:8]:
        fetched_links.append(fetch_link_summary(link))

    primary_email = cnbc_emails[0]

    return {
        "source_subject": primary_email.get("subject", ""),
        "source_from": primary_email.get("from", ""),
        "source_date": primary_email.get("date", ""),
        "body_excerpt": "\n\n".join(excerpts)[:7000],
        "links": all_links,
        "fetched_links": fetched_links,
        "selected_emails": selected_emails,
        "parsed_at": datetime.now().isoformat(timespec="seconds"),
    }