from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI


def load_prompt(prompt_path: str) -> str:
    path = Path(prompt_path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el prompt del ticker: {prompt_path}")

    return path.read_text(encoding="utf-8").strip()


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("La respuesta del modelo vino vacía.")

    # Caso ideal: ya vino JSON puro
    try:
        return json.loads(text)
    except Exception:
        pass

    # Caso común: el modelo metió texto extra antes/después
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No se encontró un objeto JSON válido en la respuesta del modelo.")

    candidate = text[start:end + 1]
    return json.loads(candidate)


def _normalize_output(data: Dict[str, Any]) -> Dict[str, Any]:
    allowed_sentiments = {"Bullish", "Bearish", "Neutral", "Mixed"}
    allowed_strength = {"HIGH", "MEDIUM", "LOW"}
    allowed_extraordinary = {"Yes", "No"}

    normalized = {
        "ticker": str(data.get("ticker", "")).strip(),
        "what_is_happening": str(data.get("what_is_happening", "")).strip(),
        "key_driver": str(data.get("key_driver", "")).strip(),
        "business_impact": str(data.get("business_impact", "")).strip(),
        "catalyst_type": str(data.get("catalyst_type", "")).strip(),
        "catalyst_strength": str(data.get("catalyst_strength", "LOW")).strip().upper(),
        "sentiment": str(data.get("sentiment", "Neutral")).strip().title(),
        "is_extraordinary": str(data.get("is_extraordinary", "No")).strip().title(),
        "summary": str(data.get("summary", "")).strip(),
        "institutional_relevance": str(data.get("institutional_relevance", "")).strip(),
    }

    if normalized["catalyst_strength"] not in allowed_strength:
        normalized["catalyst_strength"] = "LOW"

    if normalized["sentiment"] not in allowed_sentiments:
        normalized["sentiment"] = "Neutral"

    if normalized["is_extraordinary"] not in allowed_extraordinary:
        normalized["is_extraordinary"] = "No"

    return normalized


def run_ticker_analysis(
    prompt_template: str,
    ticker_news_input: str,
    model: str = "gpt-4.1-mini",
) -> Dict[str, Any]:
    if not prompt_template or not prompt_template.strip():
        raise ValueError("El prompt_template está vacío.")

    if not ticker_news_input or not ticker_news_input.strip():
        raise ValueError("ticker_news_input está vacío.")

    client = OpenAI()

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un analista profesional de trading intradía en una prop firm.\n\n"
                    "RESPONDE SIEMPRE EN ESPAÑOL.\n"
                    "No uses lenguaje técnico complejo.\n"
                    "Explica de forma clara y directa para alguien no experto.\n"
                    "No inventes hechos.\n\n"
                    "REGLAS CLAVE:\n"
                    "- Si existe contenido con Source = FINVIZ_AI, debes considerarlo como el driver principal.\n"
                    "- El resto de noticias son complemento.\n"
                    "- Siempre explica qué está pasando y por qué se mueve la acción.\n"
                    "- Siempre incluye impacto en el negocio (ingresos, costos o expectativas).\n"
                    "- Evita respuestas genéricas como 'no hay noticias relevantes'.\n\n"
                    "REGLA DE CALIFICACIÓN DEL CATALIZADOR:\n"
                    "- HIGH si:\n"
                    "  * Evento corporativo directo fuerte (earnings, FDA, contrato relevante), o\n"
                    "  * Evento macro / sector fuerte (petróleo, guerra, AI, cripto, metales, etc.)\n"
                    "    Y la empresa se ve directamente beneficiada o perjudicada\n"
                    "    Y existe evidencia clara en noticias o FINVIZ_AI\n"
                    "- MEDIUM si:\n"
                    "  * Evento relevante pero indirecto o de menor claridad\n"
                    "- LOW si:\n"
                    "  * No hay catalizador claro o es débil\n\n"
                    "REGLA ESPECIAL PARA EARNINGS:\n"
                    "Si la noticia menciona earnings, resultados trimestrales o reportes financieros:\n"
                    "- Identifica si EPS fue mejor o peor de lo esperado\n"
                    "- Identifica si ingresos fueron mejor o peor\n"
                    "- Identifica si guidance fue positivo o negativo\n"
                    "Clasificación:\n"
                    "- HIGH si 2 o más son claramente positivos (>10% o fuerte beat)\n"
                    "- MEDIUM si solo 1 es positivo\n"
                    "- LOW si ninguno o son negativos\n\n"
                    "La respuesta debe ser exclusivamente un JSON válido."
                ),
            },
            {
                "role": "user",
                "content": prompt_template.replace("{ticker_news_input}", ticker_news_input),
            },
        ],
    )

    content = response.choices[0].message.content or ""
    parsed = _extract_json_from_text(content)
    return _normalize_output(parsed)