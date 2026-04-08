"""
Agente RF6 — Extrai variáveis categóricas + mortalidade 30 dias
"""

import os
import re
import json
from pathlib import Path
from typing import Any, Dict, Optional
import requests


def _call_llm(prompt: str) -> str:
    backend = os.getenv("LLM_BACKEND", "ollama")
    model   = os.getenv("ACTIVE_MODEL", "llama3.1:8b")

    if backend == "ollama":
        url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/generate"
        resp = requests.post(
            url,
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.0}},
            timeout=600  # aumentado para suportar inferência em CPU
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()

    elif backend == "groq":
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()

    raise ValueError(f"Backend '{backend}' não suportado")


def _load_prompt(name: str) -> str:
    path = Path(__file__).parent.parent / "prompts" / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt não encontrado: {path}")
    return path.read_text(encoding="utf-8")


def _safe_parse(response: str) -> dict:
    cleaned = re.sub(r'```(?:json)?\s*\n?', '', response).strip()
    cleaned = re.sub(r'\n?\s*```$', '', cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


def _extract_value(data: dict, key: str) -> Any:
    entry = data.get(key)
    if entry is None:
        return None
    v = entry.get("value") if isinstance(entry, dict) else entry
    if v is None or str(v).lower() in {"null", "none", "n/a", "na", ""}:
        return None
    return v


def _extract_excerpt(data: dict, key: str) -> Optional[str]:
    entry = data.get(key)
    if isinstance(entry, dict):
        exc = entry.get("excerpt")
        if exc and str(exc).lower() not in {"null", "none", ""}:
            return str(exc)
    return None


def extract_categorical(carta_path: Path) -> Dict[str, Any]:
    text   = carta_path.read_text(encoding="utf-8")
    prompt = _load_prompt("categorical").replace("{texto}", text)
    raw    = _safe_parse(_call_llm(prompt))

    return {
        "tipo":            _extract_value(raw, "tipo"),
        "etiologia_toast": _extract_value(raw, "etiologia_toast"),
        "tratamento":      _extract_value(raw, "tratamento"),
        "territorio":      _extract_value(raw, "territorio"),
        "complicacoes":    _extract_value(raw, "complicacoes"),
        "_excerpts": {
            k: _extract_excerpt(raw, k)
            for k in ["tipo","etiologia_toast","tratamento","territorio","complicacoes"]
        }
    }


def extract_mortality(mortality_path: Path) -> Dict[str, Any]:
    text   = mortality_path.read_text(encoding="utf-8")
    prompt = _load_prompt("mortality").replace("{texto}", text)
    raw    = _safe_parse(_call_llm(prompt))

    vivo_raw = _extract_value(raw, "vivo_30_dias")
    if isinstance(vivo_raw, bool):
        vivo = vivo_raw
    elif isinstance(vivo_raw, str):
        vivo_lower = vivo_raw.lower()
        if vivo_lower in {"true", "sim", "yes", "vivo"}:
            vivo = True
        elif vivo_lower in {"false", "não", "nao", "no", "faleceu", "óbito", "obito"}:
            vivo = False
        else:
            vivo = None
    else:
        vivo = None

    dias_raw = _extract_value(raw, "dias_obito")
    try:
        dias = int(float(dias_raw)) if dias_raw is not None else None
    except (ValueError, TypeError):
        dias = None

    return {
        "vivo_30_dias": vivo,
        "dias_obito":   dias,
        "causa_obito":  _extract_value(raw, "causa_obito"),
    }


def extract_categorical_all(case_dir: Path) -> Dict[str, Any]:
    txt_files   = list(case_dir.glob("*.txt"))
    carta       = next((f for f in txt_files if "consulta" not in f.name and "mortalidade" not in f.name), None)
    mortalidade = next((f for f in txt_files if "mortalidade" in f.name), None)
    result: Dict[str, Any] = {}

    if carta:
        try:
            cat = extract_categorical(carta)
            result.update({k: v for k, v in cat.items() if not k.startswith("_")})
        except Exception as e:
            print(f"    ⚠️  Categóricas falharam ({carta.name}): {e}")

    if mortalidade:
        try:
            result.update(extract_mortality(mortalidade))
        except Exception as e:
            print(f"    ⚠️  Mortalidade falhou ({mortalidade.name}): {e}")
    else:
        result.update({"vivo_30_dias": None, "dias_obito": None, "causa_obito": None})

    return result