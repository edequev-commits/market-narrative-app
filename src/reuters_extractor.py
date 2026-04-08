import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def find_reuters_email(emails: list) -> dict | None:
    ranked = []

    for email in emails:
        sender = (email.get("from", "") or "").lower()
        subject = (email.get("subject", "") or "").lower()
        body = (email.get("body", "") or "").lower()

        score = 0

        if "dailybriefing@thomsonreuters.com" in sender:
            score += 6
        if "reuters daily briefing" in subject:
            score += 5
        if "reuters" in sender:
            score += 2
        if "daily briefing" in subject:
            score += 2
        if "reuters.com" in body:
            score += 1

        if score > 0:
            ranked.append((score, email))

    if not ranked:
        return None

    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1]


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


def extract_reuters_sections(reuters_email: dict) -> dict:
    if not reuters_email:
        return {
            "source_subject": "",
            "source_from": "",
            "source_date": "",
            "body_excerpt": "",
            "links": [],
            "fetched_links": [],
            "parsed_at": datetime.now().isoformat(timespec="seconds"),
        }

    body = reuters_email.get("body", "") or ""
    links = extract_links(body)

    fetched_links = []
    for link in links[:8]:
        fetched_links.append(fetch_link_summary(link))

    body_excerpt = body[:5000]

    return {
        "source_subject": reuters_email.get("subject", ""),
        "source_from": reuters_email.get("from", ""),
        "source_date": reuters_email.get("date", ""),
        "body_excerpt": body_excerpt,
        "links": links,
        "fetched_links": fetched_links,
        "parsed_at": datetime.now().isoformat(timespec="seconds"),
    }