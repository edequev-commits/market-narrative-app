from __future__ import annotations

import json
from pathlib import Path


def load_ranking_rules(base_dir: Path) -> dict:
    rules_path = base_dir / "config" / "ticker_ranking_rules.json"
    with open(rules_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _to_float(value) -> float:
    if value is None:
        return 0.0

    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return 0.0

    multiplier = 1.0
    if text.endswith("K"):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith("B"):
        multiplier = 1_000_000_000
        text = text[:-1]

    try:
        return float(text) * multiplier
    except Exception:
        return 0.0


def _bucket_score(value: float, buckets: list[dict]) -> int:
    for bucket in buckets:
        if value >= float(bucket["min"]):
            return int(bucket["score"])
    return 0


def calculate_ticker_score(row: dict, rules: dict) -> dict:
    catalyst = str(row.get("catalyst_strength", "LOW")).upper()
    rvol = _to_float(row.get("relative_volume", 0))
    volume = _to_float(row.get("volume", 0))
    gap_pct = abs(_to_float(row.get("gap_pct", 0)))

    catalyst_score = int(rules["catalyst_strength"].get(catalyst, 1))
    rvol_score = _bucket_score(rvol, rules["rvol"])
    volume_score = _bucket_score(volume, rules["premarket_volume"])
    gap_score = _bucket_score(gap_pct, rules["gap_pct"])

    total_score = catalyst_score + rvol_score + volume_score + gap_score

    return {
        "score": total_score,
        "score_breakdown": {
            "catalyst": catalyst_score,
            "rvol": rvol_score,
            "premarket_volume": volume_score,
            "gap_pct": gap_score,
        },
    }