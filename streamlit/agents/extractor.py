import requests
import json
import time
import os
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

"""Agente 1 — extrai timestamps de uma carta de alta usando LLM (Groq ou Ollama local)."""

# ── Configuração ──────────────────────────────────────────────────────────────
ACTIVE_MODEL    = os.getenv("ACTIVE_MODEL", "llama3.1:8b")
LLM_BACKEND     = os.getenv("LLM_BACKEND", "ollama").lower()
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
OLLAMA_URL      = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LITELLM_URL     = os.getenv("LITELLM_URL", "")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "timestamps_v2.txt"


def _call_litellm(system_prompt: str, user_message: str) -> dict:
    """Chama uma gateway LiteLLM (OpenAI-compatible)."""
    t0 = time.time()
    response = requests.post(
        f"{LITELLM_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
        json={
            "model": ACTIVE_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message}
            ],
            "temperature": 0.0,
            "max_tokens": 1500
        },
        timeout=600
    )
    response.raise_for_status()
    duration = round(time.time() - t0, 2)
    return {
        "content": response.json()["choices"][0]["message"]["content"],
        "duration_seconds": duration
    }


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
        timeout=600  # aumentado de 180 para 600 — inferência em CPU pode demorar
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
        result = json.loads(text)
        if isinstance(result, dict):
            return result
        # modelo devolveu string ou lista em vez de objecto — tentar encontrar {} no texto
    except json.JSONDecodeError:
        pass
    import re
    match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    return {"_parse_error": "modelo não devolveu JSON válido", "_raw_response": raw}


def extract_timestamps(letter_path: Path) -> dict:
    """
    Extrai timestamps de uma carta de alta de AVC.
    Usa Groq se LLM_BACKEND=groq, caso contrário usa Ollama local.
    """
    letter_text   = letter_path.read_text(encoding="utf-8")
    system_prompt = PROMPT_FILE.read_text(encoding="utf-8")

    user_message = f"""Extrai os timestamps da seguinte carta de alta de AVC isquémico.

CARTA:
{letter_text}

Devolve APENAS o JSON, sem texto adicional."""

    if LLM_BACKEND == "groq":
        result = _call_groq(system_prompt, user_message)
        backend = "groq"
    elif LLM_BACKEND == "litellm":
        result = _call_litellm(system_prompt, user_message)
        backend = "litellm"
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