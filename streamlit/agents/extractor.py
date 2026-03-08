import requests
import json
import time
import os
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ── Configuração ──────────────────────────────────────────────────────────────
USE_GROQ      = os.getenv("GROQ_API_KEY") is not None
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
ACTIVE_MODEL  = os.getenv("ACTIVE_MODEL", "llama-3.1-8b-instant")
OLLAMA_URL    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

#PROMPT_FILE = Path("prompts/timestamps_v1.txt")
PROMPT_FILE = Path("prompts/timestamps_v2.txt")

def _call_groq(system_prompt: str, user_message: str) -> dict:
    """Chama a API Groq."""
    client = Groq(api_key=GROQ_API_KEY)
    t0 = time.time()
    response = client.chat.completions.create(
        model=ACTIVE_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message}
        ],
        temperature=0.0,
        max_tokens=1500
    )
    duration = round(time.time() - t0, 2)
    return {
        "content": response.choices[0].message.content,
        "duration_seconds": duration
    }


def _call_ollama(system_prompt: str, user_message: str) -> dict:
    """Chama o Ollama local."""
    t0 = time.time()
    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": ACTIVE_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message}
            ],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 1500}
        },
        timeout=180
    )
    response.raise_for_status()
    duration = round(time.time() - t0, 2)
    return {
        "content": response.json()["message"]["content"],
        "duration_seconds": duration
    }


def _parse_json(raw: str) -> dict:
    """Limpeza defensiva e parse do JSON devolvido pelo modelo."""
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:-1]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"_parse_error": str(e), "_raw_response": raw}


def extract_timestamps(letter_path: Path) -> dict:
    """
    Extrai timestamps de uma carta de alta de AVC.
    Usa Groq se GROQ_API_KEY estiver definida, caso contrário usa Ollama local.
    """
    letter_text   = letter_path.read_text(encoding="utf-8")
    system_prompt = PROMPT_FILE.read_text(encoding="utf-8")

    user_message = f"""Extrai os timestamps da seguinte carta de alta de AVC isquémico.

CARTA:
{letter_text}

Devolve APENAS o JSON, sem texto adicional."""

    # Escolhe o backend automaticamente
    if USE_GROQ:
        result = _call_groq(system_prompt, user_message)
        backend = "groq"
    else:
        result = _call_ollama(system_prompt, user_message)
        backend = "ollama"

    return {
        "_meta": {
            "source_file": letter_path.name,
            "model": ACTIVE_MODEL,
            "backend": backend,
            "duration_seconds": result["duration_seconds"],
            "char_count": len(letter_text)
        },
        "timestamps": _parse_json(result["content"])
    }
