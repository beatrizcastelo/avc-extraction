"""
Agente 3 — Extrai escalas NIHSS + mRS (RF5)
Input: texto carta/consulta
Output: JSON com valores + excertos
"""

import os
import json
from pathlib import Path
from typing import Dict, Any
import requests
import re 

def clean_numeric_value(val):
    """Garante que o valor é um número (int/float) ou None para evitar NaNs."""
    if val is None or str(val).lower() in ["null", "n/a", "none", ""]:
        return None
    try:
        num = float(val)
        return int(num) if num.is_integer() else num
    except (ValueError, TypeError):
        match = re.search(r"(\d+(?:\.\d+)?)", str(val))
        if match:
            num = float(match.group(1))
            return int(num) if num.is_integer() else num
        return None

def safe_parse_json(response: str) -> dict:
    """Parse JSON robusto que extrai o campo 'value' e limpa números."""
    cleaned = re.sub(r'```(?:json)?\s*\n?', '', response).strip()
    cleaned = re.sub(r'\n?\s*```$', '', cleaned).strip()
    cleaned = re.sub(r'^[\s\n\r\t]*', '', cleaned)
    
    data = {}
    try:
        data = json.loads(cleaned)
    except:
        match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', cleaned, re.DOTALL)
        if match:
            try: data = json.loads(match.group())
            except: data = {}

    # Extrai o 'value' do formato {"nihss_admissao": {"value": 14, ...}}
    # e limpa para número puro.
    if isinstance(data, dict):
        cleaned_data = {}
        for k, v in data.items():
            val_final = v["value"] if isinstance(v, dict) and "value" in v else v
            cleaned_data[k] = clean_numeric_value(val_final)
        return cleaned_data
    return {}

def _call_llm(prompt: str) -> str:
    """Chamada ao backend (Ollama ou Groq) — corrigido bug response.choices[0]"""
    backend = os.getenv("LLM_BACKEND", "ollama")
    model   = os.getenv("ACTIVE_MODEL", "llama3.1:8b")

    if backend == "ollama":
        url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1}
        }
        resp = requests.post(url, json=payload, timeout=180)
        resp.raise_for_status()
        return resp.json()["response"].strip()

    elif backend == "groq":
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()

    raise ValueError(f"Backend '{backend}' não suportado")

def load_prompt(prompt_name: str) -> str:
    """Carrega prompt de prompts/"""
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{prompt_name}.txt" 
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt não encontrado em: {prompt_path}") 
    return prompt_path.read_text(encoding="utf-8") 

def extract_nihss(text: str) -> Dict[str, Any]:
    prompt = load_prompt("scales_nihss")
    full_prompt = prompt.replace("{texto}", text) 
    response = _call_llm(full_prompt)
    return safe_parse_json(response)

def extract_mrs(text: str) -> Dict[str, Any]:
    prompt = load_prompt("scales_mrs")
    full_prompt = prompt.replace("{texto}", text)
    response = _call_llm(full_prompt)
    return safe_parse_json(response)

def extract_scales(text_path: Path) -> Dict[str, Any]:
    """
    Agente principal — devolve dict ANINHADO compatível com validate_all.py:
    {
        "nihss": {"nihss_admissao": {"value": 14}, "nihss_alta": {"value": 3}},
        "mrs":   {"mrs_previo": {"value": 0}, "mrs_alta": {"value": 2}, "mrs_3meses": {"value": 1}}
    }
    """
    text = text_path.read_text(encoding="utf-8")

    raw_nihss = extract_nihss(text)   # {"nihss_admissao": 14, "nihss_alta": 3}
    raw_mrs   = extract_mrs(text)     # {"mrs_previo": 0, "mrs_alta": 2, "mrs_3meses": 1}

    # Constrói estrutura aninhada esperada pelo validate_all.py (flatten_extractor_output)
    nihss_nested = {k: {"value": v} for k, v in raw_nihss.items()}
    mrs_nested   = {k: {"value": v} for k, v in raw_mrs.items()}

    return {
        "nihss": nihss_nested,
        "mrs":   mrs_nested,
    }