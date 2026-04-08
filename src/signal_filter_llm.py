import json
import os
from openai import OpenAI


JSON_SCHEMA = {
    "driver_principal": "",
    "hechos_confirmados": [],
    "escenario_dominante": "",
    "interpretacion_institucional": "",
    "riesgos_secundarios": [],
    "eventos_clave": [],
}


def build_signal_filter_prompt(raw_input: str) -> str:
    return f"""
Actúa como Head Market Strategist de una prop trading firm institucional.

OBJETIVO
Analizar el INPUT y devolver una versión limpia, priorizada y sin contradicciones dominantes.

DEFINICIONES

DRIVER_PRINCIPAL
- La fuerza dominante que realmente explica el movimiento o la percepción de riesgo del mercado.
- Debe ser una sola tesis central.

HECHOS_CONFIRMADOS
- Solo hechos explícitos del INPUT.
- Deben ser concretos, verificables y estrictamente necesarios para explicar el driver principal.
- No incluir inferencias, probabilidades, consecuencias, reacción de mercado, evaluaciones estratégicas ni lenguaje condicional.
- No puede incluir lenguaje como “es probable”, “es poco probable”, “podría”, “sugiere”, “implica”.
- No puede incluir juicios como “ha logrado objetivos”, “es favorable”, “es costoso”, “es poco atractivo”.
- Si una afirmación mezcla hecho e interpretación, NO va en hechos_confirmados.
- Si una afirmación describe cómo reaccionan los mercados, tampoco va en hechos_confirmados.

ESCENARIO_DOMINANTE
- El escenario base más prudente y probable.
- Si hay contradicción entre señales, prioriza el escenario más conservador.
- Debe redactarse con probabilidad cualitativa, no numérica.
- Usa expresiones como:
  - alta probabilidad
  - moderada probabilidad
  - baja probabilidad
- No uses porcentajes numéricos.
- Evita conclusiones definitivas.

INTERPRETACION_INSTITUCIONAL
- Lectura prudente derivada de los hechos confirmados.
- Debe sonar institucional, sin convertir interpretación en hecho.
- Aquí sí pueden ir evaluaciones estratégicas, implicaciones macro y lectura de reacción de mercado.
- Debe mantenerse prudente y condicional.

RIESGOS_SECUNDARIOS
- Escenarios posibles, no dominantes, que podrían alterar la tesis principal.
- No redactarlos como si ya estuvieran ocurriendo.
- Si una afirmación es extrema, sensible o proviene de una sola fuente, colócala aquí o en interpretación, no en hechos_confirmados.

EVENTOS_CLAVE
- Eventos próximos que pueden confirmar, modificar o invalidar la narrativa principal.
- Deben estar directamente relacionados con el driver principal.
- Excluye earnings, IPOs, M&A y eventos corporativos si no son esenciales para entender el driver dominante.

REGLAS
- Usa SOLO información presente en el INPUT.
- No inventes información ni agregues hechos nuevos.
- Mantén el foco en el driver principal.
- Ignora información secundaria que no sea necesaria para entender la narrativa dominante, aunque aparezca en el INPUT.
- No incluyas nombres específicos de empresas, indicadores o niveles de mercado salvo que sean esenciales para explicar el driver principal.
- Si hay contradicción entre un escenario extremo y uno moderado, prioriza el moderado.
- En temas geopolíticos, evita asumir escaladas mayores como escenario base si el INPUT también muestra negociación, dudas o señales mixtas.
- Si un hecho es sensible, extremo o proviene de una sola fuente (por ejemplo: inteligencia, apoyo militar, ciberataques, operaciones encubiertas), no lo clasifiques como hecho_confirmado; muévelo a riesgos_secundarios.
- hechos_confirmados debe contener solo hechos nucleares del driver principal.
- eventos_clave debe contener solo validadores directos del driver principal.
- El objetivo no es resumir todo el INPUT, sino aislar la tesis central con el menor ruido posible.

LÍMITES
- Máximo 4 hechos_confirmados.
- Máximo 5 riesgos_secundarios.
- Máximo 5 eventos_clave.

SALIDA
Devuelve únicamente JSON válido con esta estructura:

{json.dumps(JSON_SCHEMA, ensure_ascii=False, indent=2)}

INPUT:
{raw_input}
""".strip()


def _normalize_list(value, max_items: int) -> list:
    if not isinstance(value, list):
        return []

    cleaned = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            cleaned.append(text)

    return cleaned[:max_items]


def _normalize_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_output(parsed: dict) -> dict:
    result = JSON_SCHEMA.copy()
    result.update(parsed if isinstance(parsed, dict) else {})

    result["driver_principal"] = _normalize_text(result.get("driver_principal"))
    result["escenario_dominante"] = _normalize_text(result.get("escenario_dominante"))
    result["interpretacion_institucional"] = _normalize_text(result.get("interpretacion_institucional"))
    result["hechos_confirmados"] = _normalize_list(result.get("hechos_confirmados"), 4)
    result["riesgos_secundarios"] = _normalize_list(result.get("riesgos_secundarios"), 5)
    result["eventos_clave"] = _normalize_list(result.get("eventos_clave"), 5)

    return result


def run_signal_filter(raw_input: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("No se encontró OPENAI_API_KEY")

    client = OpenAI(api_key=api_key)
    prompt = build_signal_filter_prompt(raw_input)

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a careful institutional strategist. "
                    "Do not invent facts. "
                    "Separate facts, interpretation, risks, reaction, and upcoming events rigorously. "
                    "Use qualitative probabilities only, never numeric probabilities. "
                    "Keep only the most relevant information for the dominant narrative. "
                    "Return valid JSON only."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    try:
        parsed = json.loads(content)
        return _normalize_output(parsed)
    except Exception:
        fallback = JSON_SCHEMA.copy()
        fallback["raw_response"] = content
        return fallback