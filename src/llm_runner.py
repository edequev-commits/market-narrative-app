from pathlib import Path
from openai import OpenAI
import os


def load_prompt(filepath: str) -> str:
    path = Path(filepath)
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def run_market_narrative(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("No se encontró OPENAI_API_KEY")

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un estratega institucional de mercado. "
                    "Debes producir una narrativa clara, precisa y sin inventar hechos."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    return response.choices[0].message.content.strip()