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

def _call_ollama(prompt: str, model: str = "llama3.1:8b") -> str:
    """Chamada Ollama igual ao extractor.py"""
    backend = os.getenv("LLM_BACKEND", "ollama")
    
    if backend == "ollama":
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1}
        }
        resp = requests.post(url, json=payload)
        return resp.json()["response"].strip()
    
    elif backend == "groq":
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    
    raise ValueError(f"Backend {backend} não suportado")

def load_prompt(prompt_name: str) -> str:
    """Carrega prompt de prompts/"""
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{prompt_name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt não encontrado: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")

def extract_nihss(text: str) -> Dict[str, Any]:
    """Extrai NIHSS admissão + alta"""
    prompt = load_prompt("scales_nihss")
    full_prompt = prompt.format(texto=text)
    
    response = _call_ollama(full_prompt)
    
    try:
        result = json.loads(response)
        return result
    except:
        # Fallback se JSON malformado
        return {"error": "parse_failed", "raw": response}

def extract_mrs(text: str) -> Dict[str, Any]:
    """Extrai mRS prévio + alta + 3 meses"""
    prompt = load_prompt("scales_mrs")
    full_prompt = prompt.format(texto=text)
    
    response = _call_ollama(full_prompt)
    
    try:
        result = json.loads(response)
        return result
    except:
        return {"error": "parse_failed", "raw": response}

def extract_scales(text_path: Path) -> Dict[str, Any]:
    """Agente principal — extrai NIHSS + mRS"""
    text = text_path.read_text(encoding="utf-8")
    
    nihss = extract_nihss(text)
    mrs = extract_mrs(text)
    
    return {
        "nihss": nihss,
        "mrs": mrs,
        "source": text_path.name
    }
