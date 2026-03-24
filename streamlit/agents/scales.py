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
    """Parse JSON robusto que limpa tags markdown e força a conversão numérica."""
    cleaned = re.sub(r'```(?:json)?\s*\n?', '', response).strip()
    cleaned = re.sub(r'\n?\s*```$', '', cleaned).strip()
    cleaned = re.sub(r'^[\s\n\r\t]*', '', cleaned)
    
    data = {}
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        patterns = [r'\{(?:[^{}]|\{[^{}]*\})*\}', r'\{[^{}]*\}']
        for pattern in patterns:
            match = re.search(pattern, cleaned, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                    break
                except: continue

    # CORREÇÃO: Limpar e extrair o 'value' se o modelo devolver o formato dos teus prompts
    if isinstance(data, dict):
        cleaned_data = {}
        for k, v in data.items():
            # Trata o formato {"value": X, "excerpt": Y} definido nos teus ficheiros.txt
            val_to_clean = v["value"] if isinstance(v, dict) and "value" in v else v
            cleaned_data[k] = clean_numeric_value(val_to_clean)
        return cleaned_data
    return {}

def _call_ollama(prompt: str, model: str = "llama3.1:8b") -> str:
    """Chamada ao backend (Ollama ou Groq) [1]"""
    backend = os.getenv("LLM_BACKEND", "ollama")
    if backend == "ollama":
        url = "http://localhost:11434/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
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
        return response.choices.message.content.strip()
    raise ValueError(f"Backend {backend} não suportado")

def load_prompt(prompt_name: str) -> str:
    """Carrega prompt de streamlit/prompts/ """
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{prompt_name}.txt" 
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt não encontrado em: {prompt_path}") 
    return prompt_path.read_text(encoding="utf-8") 

def extract_nihss(text: str) -> Dict[str, Any]:
    prompt = load_prompt("scales_nihss")
    full_prompt = prompt.replace("{texto}", text) 
    response = _call_ollama(full_prompt)
    return safe_parse_json(response)

def extract_mrs(text: str) -> Dict[str, Any]:
    prompt = load_prompt("scales_mrs")
    full_prompt = prompt.replace("{texto}", text)
    response = _call_ollama(full_prompt)
    return safe_parse_json(response)

def extract_scales(text_path: Path) -> Dict[str, Any]:
    """Agente principal — Achata o dicionário e adiciona sufixos para o validador (RF8/RF9)."""
    text = text_path.read_text(encoding="utf-8")
    filename = text_path.name.lower()
    
    # Determinar o sufixo baseado no ficheiro clínico (essencial para o Ground Truth)
    suffix = ""
    if "admissao" in filename: suffix = "_admissao"
    elif "alta" in filename or "carta" in filename: suffix = "_carta"
    elif "consulta" in filename or "seguimento" in filename: suffix = "_consulta"

    raw_nihss = extract_nihss(text)
    raw_mrs = extract_mrs(text)
    
    # CORREÇÃO: Unir tudo num dicionário plano (FLAT) com chaves corretas
    final_scales = {}
    combined = {**raw_nihss, **raw_mrs}
    
    for key, val in combined.items():
        if key in ["excertos", "source", "justificacao"]:
            continue
        # Adiciona o sufixo necessário (ex: nihss_admissao -> nihss_admissao_carta)
        new_key = key if key.endswith(suffix) else f"{key}{suffix}"
        final_scales[new_key] = val
        
    return final_scales