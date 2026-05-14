#!/usr/bin/env python3
"""
test_single_variable.py — Testa extracção de variáveis categóricas uma a uma.

Compara o prompt actual (5 variáveis juntas) com prompts focados
numa só variável de cada vez, em 8 casos representativos.

Uso:
    python test_single_variable.py --model llama3.2:1b
    python test_single_variable.py --model llama3.1:8b  # para comparar
"""

import os
import re
import json
import argparse
import requests
from pathlib import Path

# ── Configuração ──────────────────────────────────────────────────────────
DATA_DIR = Path("/Users/beatrizcastelo/Documents/GitHub/groq-teste-processor/outputs_teste")

# 8 casos — um de cada tipo
EVAL_CASES = [
    "caso_001_fibrinolise_pre_hospitalar",
    "caso_016_fibrinolise_pre_hospitalar_ace",
    "caso_031_fibrinolise_intra_hospitalar",
    "caso_046_bridging",
    "caso_096_tev_isolada_contraindicacao",
    "caso_076_tev_isolada_fora_janela",
    "caso_116_conservador_lacunar",
    "caso_136_conservador_wake_up",
]

# Ground truth esperado para cada caso
GROUND_TRUTH = {
    "caso_001_fibrinolise_pre_hospitalar":    {"tipo": "fibrinolise_pre_hospitalar",    "etiologia_toast": "Cardioembólica"},
    "caso_016_fibrinolise_pre_hospitalar_ace":{"tipo": "fibrinolise_pre_hospitalar_ace","etiologia_toast": "Cardioembólica"},
    "caso_031_fibrinolise_intra_hospitalar":  {"tipo": "fibrinolise_intra_hospitalar",  "etiologia_toast": "Cardioembólica"},
    "caso_046_bridging":                      {"tipo": "bridging",                      "etiologia_toast": "Aterosclerose grandes vasos"},
    "caso_096_tev_isolada_contraindicacao":   {"tipo": "tev_isolada_contraindicacao",   "etiologia_toast": "Cardioembólica"},
    "caso_076_tev_isolada_fora_janela":       {"tipo": "tev_isolada_fora_janela",       "etiologia_toast": "Indeterminado"},
    "caso_116_conservador_lacunar":           {"tipo": "conservador_lacunar",           "etiologia_toast": "Oclusão pequenos vasos (lacunar)"},
    "caso_136_conservador_wake_up":           {"tipo": "conservador_wake_up",           "etiologia_toast": "Indeterminado"},
}

# ── Prompts focados numa variável ─────────────────────────────────────────
PROMPTS = {
    "tipo": """És um assistente médico especializado em AVC isquémico.
Lê a carta de alta e classifica o tipo de episódio.

Responde APENAS com um dos seguintes valores (sem mais nada):
- fibrinolise_pre_hospitalar
- fibrinolise_pre_hospitalar_ace
- fibrinolise_intra_hospitalar
- bridging
- tev_isolada_contraindicacao
- tev_isolada_fora_janela
- conservador_lacunar
- conservador_wake_up

REGRAS:
- "Inter-Hospitalar" = doente transferido de outro hospital → NÃO é fibrinolise_intra_hospitalar
- "Intra-Hospitalar" = AVC durante internamento no mesmo hospital → fibrinolise_intra_hospitalar
- bridging = transferido + fibrinólise na origem + trombectomia em Coimbra
- tev_isolada_contraindicacao = trombectomia sem fibrinólise por contraindicação
- tev_isolada_fora_janela = trombectomia sem fibrinólise por fora de janela

TEXTO:
{texto}

RESPOSTA (só o valor, sem mais nada):""",

    "etiologia_toast": """És um assistente médico especializado em AVC isquémico.
Lê a carta de alta e identifica a etiologia TOAST.

Responde APENAS com um dos seguintes valores (sem mais nada):
- Cardioembólica
- Aterosclerose grandes vasos
- Oclusão pequenos vasos (lacunar)
- Indeterminado

TEXTO:
{texto}

RESPOSTA (só o valor, sem mais nada):""",

    "territorio": """És um assistente médico especializado em AVC isquémico.
Lê a carta de alta e identifica o território vascular afectado.

Responde APENAS com o território vascular (ex: "ACM direita", "ACM esquerda", "ACI + ACM esquerda").
Sem mais nada.

TEXTO:
{texto}

RESPOSTA (só o território, sem mais nada):""",

    "tratamento": """És um assistente médico especializado em AVC isquémico.
Lê a carta de alta e identifica o tratamento de reperfusão realizado.

Responde de forma muito concisa (ex: "fibrinolise endovenosa", "TEV isolada", "conservador", "fibrinolise + TEV").
Sem mais nada.

TEXTO:
{texto}

RESPOSTA (só o tratamento, sem mais nada):""",

    "complicacoes": """És um assistente médico especializado em AVC isquémico.
Lê a carta de alta e identifica se houve complicações.

Responde APENAS com:
- "Nao ocorreram" se não houve complicações
- Descrição breve das complicações se houve

TEXTO:
{texto}

RESPOSTA (só as complicações, sem mais nada):""",
}


# ── Prompts para Timestamps ──────────────────────────────────────────────
PROMPTS_TIMESTAMPS = {
    "sintomas": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico e extrai APENAS a hora de início dos sintomas ou última vez visto bem (UVB).
Responde APENAS com a hora no formato HH:MM (ex: "10:15"). Se não estiver presente, responde "null".

TEXTO:
{texto}

RESPOSTA (só HH:MM ou null):""",

    "admissaocoimbra": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico e extrai APENAS a hora de admissão hospitalar em Coimbra/CHUC.
Se houver duas admissões (inter-hospitalar), extrai a de Coimbra (a segunda).
Responde APENAS com a hora no formato HH:MM (ex: "13:30"). Se não estiver presente, responde "null".

TEXTO:
{texto}

RESPOSTA (só HH:MM ou null):""",

    "tcce": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico e extrai APENAS a hora de realização da TC-CE (tomografia computorizada cranioencefálica).
Responde APENAS com a hora no formato HH:MM (ex: "11:00"). Se não estiver presente, responde "null".

TEXTO:
{texto}

RESPOSTA (só HH:MM ou null):""",

    "fibrinolise": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico e extrai APENAS a hora de administração da fibrinólise (rt-PA, alteplase, tenecteplase).
Responde APENAS com a hora no formato HH:MM (ex: "11:30"). Se não foi feita fibrinólise, responde "NA".

TEXTO:
{texto}

RESPOSTA (só HH:MM, NA ou null):""",

    "puncaofemoral": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico e extrai APENAS a hora de punção femoral (início da trombectomia mecânica).
Responde APENAS com a hora no formato HH:MM (ex: "14:00"). Se não foi feita trombectomia, responde "NA".

TEXTO:
{texto}

RESPOSTA (só HH:MM, NA ou null):""",

    "recanalizacao": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico e extrai APENAS a hora de recanalização (fim da trombectomia).
Responde APENAS com a hora no formato HH:MM (ex: "14:45"). Se não foi feita trombectomia, responde "NA".

TEXTO:
{texto}

RESPOSTA (só HH:MM, NA ou null):""",
}

# ── Prompts para Escalas ──────────────────────────────────────────────────
PROMPTS_ESCALAS = {
    "nihss_admissao": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico e extrai APENAS o valor do NIHSS à admissão (entrada).
Responde APENAS com o número (ex: "14"). Se não estiver presente, responde "null".

TEXTO:
{texto}

RESPOSTA (só o número ou null):""",

    "nihss_alta": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico e extrai APENAS o valor do NIHSS à alta hospitalar.
Responde APENAS com o número (ex: "6"). Se não estiver presente, responde "null".

TEXTO:
{texto}

RESPOSTA (só o número ou null):""",

    "mrs_previo": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico e extrai APENAS o valor do mRS prévio (condição funcional antes do AVC, pré-mórbido).
Responde APENAS com o número de 0 a 6 (ex: "0"). Se não estiver presente, responde "null".

TEXTO:
{texto}

RESPOSTA (só o número 0-6 ou null):""",

    "mrs_alta": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico e extrai APENAS o valor do mRS à alta hospitalar.
Responde APENAS com o número de 0 a 6 (ex: "2"). Se não estiver presente, responde "null".

TEXTO:
{texto}

RESPOSTA (só o número 0-6 ou null):""",

    "mrs_3meses": """És um assistente médico especializado em AVC isquémico.
Lê o texto clínico (nota de consulta de seguimento aos 3 meses) e extrai APENAS o valor do mRS aos 3 meses.
Responde APENAS com o número de 0 a 6 (ex: "1"). Se não estiver presente, responde "null".

TEXTO:
{texto}

RESPOSTA (só o número 0-6 ou null):""",
}

def call_ollama(prompt: str, model: str) -> str:
    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/generate"
    resp = requests.post(
        url,
        json={"model": model, "prompt": prompt, "stream": False,
              "options": {"temperature": 0.0}},
        timeout=300
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def find_carta(case_dir: Path) -> Path | None:
    for f in case_dir.glob("*.txt"):
        if "consulta" not in f.name and "mortalidade" not in f.name:
            return f
    return None


def load_ground_truth(caso: str) -> dict:
    """Carrega ground truth real do ficheiro JSON."""
    case_dir = DATA_DIR / caso
    gt_files = list(case_dir.glob("*ground_truth.json"))
    if not gt_files:
        return GROUND_TRUTH.get(caso, {})
    raw = json.loads(gt_files[0].read_text(encoding="utf-8"))
    ts = raw.get("timestamps", {})
    seg = raw.get("seguimento", {})
    return {
        # Categóricas
        "tipo":            raw.get("tipo"),
        "etiologia_toast": raw.get("etiologia_toast"),
        "territorio":      raw.get("territorio"),
        "tratamento":      raw.get("tratamento"),
        "complicacoes":    raw.get("complicacoes"),
        # Timestamps
        "sintomas":        ts.get("sintomas"),
        "admissaocoimbra": ts.get("admissao_coimbra"),
        "tcce":            ts.get("tc_ce"),
        "fibrinolise":     ts.get("fibrinolise"),
        "puncaofemoral":   ts.get("puncao_femoral"),
        "recanalizacao":   ts.get("recanalizacao"),
        # Escalas
        "nihss_admissao":  raw.get("nihss_admissao"),
        "nihss_alta":      raw.get("nihss_alta"),
        "mrs_previo":      raw.get("mrs_previo"),
        "mrs_alta":        raw.get("mrs_alta"),
        "mrs_3meses":      seg.get("mrs_3_meses"),
    }


def normalize(value: str) -> str:
    if not value:
        return ""
    s = value.strip()
    # Remove conteúdo entre parênteses
    s = re.sub(r'\([^)]*\)', '', s)
    # Remove pontuação final
    s = s.strip('.,:;!?').strip()
    # Lowercase e remove acentos
    s = s.lower()
    for a, b in [("á","a"),("à","a"),("â","a"),("ã","a"),("é","e"),("ê","e"),
                 ("í","i"),("ó","o"),("ô","o"),("õ","o"),("ú","u"),("ç","c")]:
        s = s.replace(a, b)
    # Normaliza espaços
    s = re.sub(r'\s+', ' ', s).strip()
    return s.replace("-"," ").replace("_"," ")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2:1b")
    args = parser.parse_args()

    print(f"\n{'='*65}")
    print(f"  TESTE VARIÁVEL A VARIÁVEL | modelo={args.model}")
    print(f"  {len(EVAL_CASES)} casos × {len(PROMPTS)} variáveis")
    print(f"{'='*65}\n")

    resultados = {}

    for caso in EVAL_CASES:
        case_dir = DATA_DIR / caso
        carta = find_carta(case_dir)
        if not carta:
            print(f"  ⚠️  {caso} — carta não encontrada")
            continue

        texto = carta.read_text(encoding="utf-8")
        gt = load_ground_truth(caso)
        resultados[caso] = {}

        # Consulta dos 3 meses (para mrs_3meses)
        consulta = next((f for f in case_dir.glob("*.txt") if "consulta" in f.name), None)
        texto_consulta = consulta.read_text(encoding="utf-8") if consulta else texto

        print(f"\n📋 {caso}")
        print(f"   {'Variável':<25} {'GT':<20} {'Extraído':<20} {'✓'}")
        print(f"   {'-'*75}")

        # Categóricas
        print(f"   --- CATEGÓRICAS ---")
        for var, prompt_template in PROMPTS.items():
            prompt = prompt_template.replace("{texto}", texto)
            try:
                resposta = call_ollama(prompt, args.model).strip().strip('"\'').split('\n')[0].strip()
                gt_val = str(gt.get(var, "")) if gt.get(var) else "—"
                correcto = normalize(resposta) == normalize(gt_val)
                icon = "✅" if correcto else "❌"
                print(f"   {var:<25} {gt_val:<20} {resposta:<20} {icon}")
                resultados[caso][var] = {"gt": gt_val, "extraido": resposta, "correcto": correcto}
            except Exception as e:
                print(f"   {var:<25} ERRO: {e}")
                resultados[caso][var] = {"gt": gt.get(var, ""), "extraido": "ERRO", "correcto": False}

        # Timestamps
        print(f"   --- TIMESTAMPS ---")
        for var, prompt_template in PROMPTS_TIMESTAMPS.items():
            prompt = prompt_template.replace("{texto}", texto)
            try:
                resposta = call_ollama(prompt, args.model).strip().strip('"\'').split('\n')[0].strip()
                gt_raw = gt.get(var)
                gt_val = str(gt_raw) if gt_raw else "—"
                # Normaliza formato HH:MM vs HHhMM
                def norm_time(v):
                    if not v or v.lower() in ("null","na","—"): return v
                    return v.replace("h",":").replace("H",":")
                correcto = norm_time(normalize(resposta)) == norm_time(normalize(gt_val))
                icon = "✅" if correcto else "❌"
                print(f"   {var:<25} {gt_val:<20} {resposta:<20} {icon}")
                resultados[caso][var] = {"gt": gt_val, "extraido": resposta, "correcto": correcto}
            except Exception as e:
                print(f"   {var:<25} ERRO: {e}")
                resultados[caso][var] = {"gt": "", "extraido": "ERRO", "correcto": False}

        # Escalas
        print(f"   --- ESCALAS ---")
        for var, prompt_template in PROMPTS_ESCALAS.items():
            txt = texto_consulta if var == "mrs_3meses" else texto
            prompt = prompt_template.replace("{texto}", txt)
            try:
                resposta = call_ollama(prompt, args.model).strip().strip('"\'').split('\n')[0].strip()
                gt_raw = gt.get(var)
                gt_val = str(gt_raw) if gt_raw is not None else "—"
                correcto = normalize(resposta) == normalize(gt_val)
                icon = "✅" if correcto else "❌"
                print(f"   {var:<25} {gt_val:<20} {resposta:<20} {icon}")
                resultados[caso][var] = {"gt": gt_val, "extraido": resposta, "correcto": correcto}
            except Exception as e:
                print(f"   {var:<25} ERRO: {e}")
                resultados[caso][var] = {"gt": "", "extraido": "ERRO", "correcto": False}

    # ── Resumo ─────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  RESUMO — {args.model}")
    print(f"{'='*65}")
    print(f"\n  {'Variável':<25} {'Acertos':<10} {'Total':<10} {'%'}")
    print(f"  {'-'*50}")

    todas_vars = list(PROMPTS.keys()) + list(PROMPTS_TIMESTAMPS.keys()) + list(PROMPTS_ESCALAS.keys())
    grupos = [
        ("CATEGÓRICAS", PROMPTS.keys()),
        ("TIMESTAMPS", PROMPTS_TIMESTAMPS.keys()),
        ("ESCALAS", PROMPTS_ESCALAS.keys()),
    ]
    for grupo, vars_grupo in grupos:
        print(f"  --- {grupo} ---")
        for var in vars_grupo:
            acertos = sum(1 for c in resultados.values() if c.get(var, {}).get("correcto", False))
            total = sum(1 for c in resultados.values() if var in c)
            pct = round(acertos/total*100) if total > 0 else 0
            icon = "🟢" if pct >= 75 else ("🟡" if pct >= 50 else "🔴")
            print(f"  {icon} {var:<23} {acertos:<10} {total:<10} {pct}%")

    total_acertos = sum(
        r.get("correcto", False)
        for c in resultados.values()
        for r in c.values()
    )
    total_geral = sum(len(c) for c in resultados.values())
    print(f"\n  TOTAL: {total_acertos}/{total_geral} = {round(total_acertos/total_geral*100)}%")
    print(f"\n{'='*65}\n")

    # Guarda resultados
    output = Path(f"test_single_var_{args.model.replace(':','_').replace('.','_')}.json")
    output.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📄 Resultados guardados em: {output}\n")


if __name__ == "__main__":
    main()