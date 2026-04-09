from datetime import datetime


def parse_iso_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat((value or "").strip())
    except Exception:
        return datetime.min


def clean_cnbc_body(body: str) -> str:
    text = (body or "").strip()

    if not text:
        return ""

    bad_markers = [
        "Manage Newsletters",
        "Terms of Service",
        "Join the CNBC Panel",
        "Digital Products",
        "Feedback",
        "Privacy Policy",
        "CNBC Events",
        "© 2026 CNBC LLC",
        "A Versant Media company",
        "900 Sylvan Avenue",
        "Data is a real-time snapshot",
        "Data also provided by THOMSON REUTERS",
        "Follow @CNBC for breaking news and real-time market updates",
    ]

    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if any(marker.lower() in line.lower() for marker in bad_markers):
            continue

        lines.append(line)

    cleaned = "\n".join(lines).strip()

    if len(cleaned) > 2000:
        cleaned = cleaned[:2000]

    return cleaned


def find_cnbc_emails(emails: list, limit: int = 3) -> list:
    matches = []

    for email in emails:
        sender = (email.get("from", "") or "").lower()
        subject = (email.get("subject", "") or "").lower()
        body = (email.get("body", "") or "").lower()

        if "breakingnews@response.cnbc.com" not in sender:
            continue

        score = 10

        if "breaking news" in subject:
            score += 3
        if "cnbc" in subject:
            score += 1
        if "cnbc" in body:
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
    excerpts = []

    for email in cnbc_emails:
        subject = email.get("subject", "")
        sender = email.get("from", "")
        date = email.get("date", "")
        body = clean_cnbc_body(email.get("body", "") or "")
        rank = email.get("_recency_rank", "")

        selected_emails.append({
            "subject": subject,
            "from": sender,
            "date": date,
            "recency_rank": rank,
        })

        excerpt_block = [
            f"[CNBC #{rank}] {subject}",
            f"Fecha: {date}",
        ]

        if body:
            excerpt_block.append(body)

        excerpts.append("\n".join(excerpt_block))

    primary_email = cnbc_emails[0]

    return {
        "source_subject": primary_email.get("subject", ""),
        "source_from": primary_email.get("from", ""),
        "source_date": primary_email.get("date", ""),
        "body_excerpt": "\n\n".join(excerpts)[:7000],
        "links": [],
        "fetched_links": [],
        "selected_emails": selected_emails,
        "parsed_at": datetime.now().isoformat(timespec="seconds"),
    }