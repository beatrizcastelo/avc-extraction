#!/usr/bin/env python3
"""
validate_all.py — Validação Automática dos 150 Casos
Tese de Mestrado IA & Ciência de Dados — FCTUC / ULS Coimbra
Orientador: Prof. Pedro Furtado

Uso:
    python validate_all.py --cases 5
    python validate_all.py --backend groq
    python validate_all.py --backend ollama
    python validate_all.py --use-cache
"""

import json, os, re, sys, time, argparse
from unittest import result
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Any

#importar caminho do metrics.py 
sys.path.insert(0, "streamlit/agents")
import metrics


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR      = Path(__file__).parent
DATA_DIR      = Path("/Users/beatrizcastelo/Documents/GitHub/groq-teste-processor/outputs_teste")
STREAMLIT_DIR = BASE_DIR / "streamlit"
OUTPUTS_DIR   = STREAMLIT_DIR / "outputs"
REPORT_DIR    = BASE_DIR / "validation_reports"
REPORT_DIR.mkdir(exist_ok=True)

TIMESTAMP_TOLERANCE_MIN = 1
METRIC_TOLERANCE_MIN    = 5

NULL_TOKENS = {"n/a","na","null","none","não aplicável","desconhecido",""}

TIMESTAMP_VARS   = ["sintomas","admissaoorigem","admissaocoimbra","tcce",
                    "fibrinolise","transferencia","puncaofemoral","recanalizacao"]
METRIC_VARS      = ["onset_to_door","door_to_imaging","door_to_needle",
                    "door_to_puncture","onset_to_recan","door_in_door_out","door1_to_door2"]
SCALE_VARS       = ["nihss_admissao_carta", "nihss_alta_carta", "mrs_previo_carta", 
                    "mrs_alta_carta", "mrs_3meses_carta",
                    "nihss_admissao_consulta", "nihss_alta_consulta", 
                    "mrs_previo_consulta", "mrs_alta_consulta", "mrs_3meses_consulta"]
CATEGORICAL_VARS = ["tipo","etiologia_toast","tratamento","territorio","complicacoes","causa_obito"]
BINARY_VARS      = ["vivo_30_dias"]
NUMERIC_VARS     = ["dias_obito"]

ALL_VARS = (TIMESTAMP_VARS + METRIC_VARS + SCALE_VARS +
            CATEGORICAL_VARS + BINARY_VARS + NUMERIC_VARS)


# ══════════════════════════════════════════════════════════════════════════════
# FLATTEN — converte estruturas aninhadas em dicts planos
# ══════════════════════════════════════════════════════════════════════════════

def flatten_extractor_output(raw: dict) -> dict:
    """
    Converte o output do extractor (aninhado, chaves inglês) → dict plano.

    Estrutura esperada de raw["scales"]:
      {
        "carta":   {"nihss": {"nihss_admissao": {"value": 14}, ...},
                    "mrs":   {"mrs_previo": {"value": 0}, ...}},
        "consulta": { ... }
      }
    """
    result = {}
    ts = raw.get("timestamps", {})

    def get_val(key):
        entry = ts.get(key, {})
        v = entry.get("value") if isinstance(entry, dict) else entry
        if v is None or str(v).strip().upper() in {"NA", "N/A", "NULL", "NONE", ""}:
            return None
        return str(v).strip()

    # ── Timestamps ────────────────────────────────────────────────────────────
    result["sintomas"]        = get_val("onset_uvb")
    result["admissaoorigem"]  = get_val("door1_admission")
    result["admissaocoimbra"] = get_val("admission")
    result["tcce"]            = get_val("imaging_ct")
    result["fibrinolise"]     = get_val("thrombolysis")
    result["transferencia"]   = get_val("door1_departure")
    result["puncaofemoral"]   = get_val("femoral_puncture")
    result["recanalizacao"]   = get_val("recanalization")

    # Bridging: door2 sobrescreve admissaocoimbra
    door2 = get_val("door2")
    if door2 is not None:
        result["admissaocoimbra"] = door2

    # ── Métricas (Python puro, sem LLM) ──────────────────────────────────────
    for k, v in raw.get("metricas_temporais", {}).items():
        if k in METRIC_VARS:
            result[k] = v

    metrics_raw = raw.get("metrics", {})
    for k, v in metrics_raw.items():
        if isinstance(v, dict) and v.get("value") is not None:
            result[k] = v["value"]

    # ── Escalas ───────────────────────────────────────────────────────────────
    # Estrutura de raw["scales"]:
    #   raw["scales"]["carta"]   = {"nihss": {"nihss_admissao": {"value": N}, ...},
    #                               "mrs":   {"mrs_previo":    {"value": N}, ...}}
    #   raw["scales"]["consulta"] = idem
    scales = raw.get("scales", {})

    for source in ["carta", "consulta"]:
        s = scales.get(source, {})

        # nihss
        nihss = s.get("nihss", {})
        result[f"nihss_admissao_{source}"] = _extract_scale_value(nihss, "nihss_admissao")
        result[f"nihss_alta_{source}"]     = _extract_scale_value(nihss, "nihss_alta")

        # mrs
        mrs = s.get("mrs", {})
        result[f"mrs_previo_{source}"]  = _extract_scale_value(mrs, "mrs_previo")
        result[f"mrs_alta_{source}"]    = _extract_scale_value(mrs, "mrs_alta")
        result[f"mrs_3meses_{source}"]  = _extract_scale_value(mrs, "mrs_3meses")

    return result


def _extract_scale_value(section: dict, key: str):
    """
    Lê o valor de uma escala de forma robusta.
    Aceita tanto {"nihss_admissao": {"value": 14}} como {"nihss_admissao": 14}.
    """
    entry = section.get(key)
    if entry is None:
        return None
    if isinstance(entry, dict):
        v = entry.get("value")
    else:
        v = entry
    if v is None or str(v).lower() in {"null", "none", "n/a", "na", ""}:
        return None
    try:
        num = float(v)
        return int(num) if num == int(num) else num
    except (ValueError, TypeError):
        return None


def flatten_ground_truth(raw: dict) -> dict:
    """
    Converte o ground truth (aninhado, chaves português) → dict plano.
    """
    result = {}

    # Timestamps
    ts = raw.get("timestamps", {})
    for gt_key, var in [("sintomas","sintomas"), ("admissao_coimbra","admissaocoimbra"),
                        ("admissao_origem","admissaoorigem"), ("tc_ce","tcce"),
                        ("fibrinolise","fibrinolise"), ("transferencia","transferencia"),
                        ("puncao_femoral","puncaofemoral"), ("recanalizacao","recanalizacao")]:
        v = ts.get(gt_key)
        result[var] = str(v).strip() if v is not None else None

    # Métricas temporais
    mt = raw.get("metricas_temporais", {})
    for gt_key, var in [("onset_to_door","onset_to_door"), ("door_to_imaging","door_to_imaging"),
                        ("door_to_needle","door_to_needle"), ("door_to_puncture","door_to_puncture"),
                        ("onset_to_recan","onset_to_recan"), ("door_in_door_out","door_in_door_out"),
                        ("door1_to_door2","door1_to_door2")]:
        v = mt.get(gt_key)
        result[var] = str(v).strip() if v is not None else None
    
    # Escalas da carta de alta
    result["nihss_admissao_carta"] = raw.get("nihss_admissao")
    result["nihss_alta_carta"]     = raw.get("nihss_alta")
    result["mrs_previo_carta"]     = raw.get("mrs_previo")
    result["mrs_alta_carta"]       = raw.get("mrs_alta")

    # Seguimento
    seg = raw.get("seguimento", {})
    result["vivo_30_dias"] = seg.get("vivo_30_dias")
    result["dias_obito"]   = seg.get("dias_obito")
    result["causa_obito"]  = seg.get("causa_obito")
    result["mrs_3meses"]   = seg.get("mrs_3_meses")

    # Variáveis de topo
    for var in ["nihss_admissao","nihss_alta","mrs_previo","mrs_alta",
                "tipo","etiologia_toast","tratamento","territorio","complicacoes"]:
        result[var] = raw.get(var)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE PARSING
# ══════════════════════════════════════════════════════════════════════════════

def is_null(value: Any) -> bool:
    return value is None or str(value).strip().lower() in NULL_TOKENS

def normalize_cat(value: Any) -> str:
    if value is None: return ""
    return str(value).strip().lower().replace("-"," ").replace("_"," ")

def parse_hhhmm(value: Any) -> int | None:
    if is_null(value): return None
    s = str(value).strip()
    m = re.match(r"^(\d+)[hH:](\d{2})$", s)
    if m: return int(m.group(1)) * 60 + int(m.group(2))
    if re.match(r"^\d+$", s): return int(s)
    return None

def parse_timestamp(value: Any) -> datetime | None:
    if is_null(value): return None
    s = str(value).strip()
    # Formato "10h15" ou "10H15" (usado no ground truth)
    m = re.match(r"^(\d{1,2})[hH](\d{2})$", s)
    if m:
        try: return datetime.strptime(f"{m.group(1)}:{m.group(2)}", "%H:%M")
        except ValueError: pass
    # Formatos standard
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M",
                "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M", "%H:%M"):
        try: return datetime.strptime(s, fmt)
        except ValueError: continue
    return None


# ══════════════════════════════════════════════════════════════════════════════
# COMPARADORES
# ══════════════════════════════════════════════════════════════════════════════

def compare_timestamp(pred, gt) -> dict:
    pn, gn = is_null(pred), is_null(gt)
    if gn and pn:       return {"tp":0,"fp":0,"fn":0,"tn":1,"mae_min":None}
    if gn and not pn:   return {"tp":0,"fp":1,"fn":0,"tn":0,"mae_min":None}
    if not gn and pn:   return {"tp":0,"fp":0,"fn":1,"tn":0,"mae_min":None}
    tp_dt = parse_timestamp(str(pred))
    gt_dt = parse_timestamp(str(gt))
    if tp_dt is None or gt_dt is None:
        return {"tp":0,"fp":1,"fn":1,"tn":0,"mae_min":None}
    diff = abs((tp_dt - gt_dt).total_seconds()) / 60
    hit  = diff <= TIMESTAMP_TOLERANCE_MIN
    return {"tp":int(hit),"fp":int(not hit),"fn":int(not hit),"tn":0,"mae_min":diff}

def compare_metric(pred, gt) -> dict:
    pn, gn = is_null(pred), is_null(gt)
    if gn and pn:       return {"tp":0,"fp":0,"fn":0,"tn":1,"mae_min":None}
    if gn and not pn:   return {"tp":0,"fp":1,"fn":0,"tn":0,"mae_min":None}
    if not gn and pn:   return {"tp":0,"fp":0,"fn":1,"tn":0,"mae_min":None}
    vp, vg = parse_hhhmm(str(pred)), parse_hhhmm(str(gt))
    if vp is None or vg is None:
        return {"tp":0,"fp":1,"fn":1,"tn":0,"mae_min":None}
    mae = abs(vp - vg)
    hit = mae <= METRIC_TOLERANCE_MIN
    return {"tp":int(hit),"fp":int(not hit),"fn":int(not hit),"tn":0,"mae_min":float(mae)}

def compare_scale(pred, gt) -> dict:
    pn, gn = is_null(pred), is_null(gt)
    if gn and pn:       return {"tp":0,"fp":0,"fn":0,"tn":1,"mae":None}
    if gn and pn:       return {"tp":0,"fp":0,"fn":0,"tn":1,"mae":None}
    if gn and not pn:   return {"tp":0,"fp":1,"fn":0,"tn":0,"mae":None}
    if not gn and pn:   return {"tp":0,"fp":0,"fn":1,"tn":0,"mae":None}
    try:
        vp, vg = float(pred), float(gt)
        mae = abs(vp - vg)
        return {"tp":int(mae==0),"fp":int(mae!=0),"fn":int(mae!=0),"tn":0,"mae":mae}
    except (ValueError,TypeError):
        return {"tp":0,"fp":1,"fn":1,"tn":0,"mae":None}

def compare_categorical(pred, gt) -> dict:
    pn, gn = is_null(pred), is_null(gt)
    if gn and pn:       return {"tp":0,"fp":0,"fn":0,"tn":1}
    if gn and not pn:   return {"tp":0,"fp":1,"fn":0,"tn":0}
    if not gn and pn:   return {"tp":0,"fp":0,"fn":1,"tn":0}
    hit = normalize_cat(pred) == normalize_cat(gt)
    return {"tp":int(hit),"fp":int(not hit),"fn":int(not hit),"tn":0}

COMPARATORS = {
    **{v: compare_timestamp   for v in TIMESTAMP_VARS},
    **{v: compare_metric      for v in METRIC_VARS},
    **{v: compare_scale       for v in SCALE_VARS + NUMERIC_VARS},
    **{v: compare_categorical for v in CATEGORICAL_VARS + BINARY_VARS},
}


# ══════════════════════════════════════════════════════════════════════════════
# CARREGAMENTO DE DADOS
# ══════════════════════════════════════════════════════════════════════════════

def load_ground_truth(case_dir: Path) -> dict | None:
    gt_files = list(case_dir.glob("*ground_truth*.json"))
    if not gt_files:
        print(f"  ⚠️  Sem ground truth em: {case_dir.name}")
        return None
    raw = json.loads(gt_files[0].read_text(encoding="utf-8"))
    return flatten_ground_truth(raw)

def load_cached_output(case_dir: Path) -> dict | None:
    cache = OUTPUTS_DIR / f"{case_dir.name}_output.json"
    if cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        return flatten_extractor_output(raw)
    return None

def save_cached_output(case_dir: Path, raw: dict):
    OUTPUTS_DIR.mkdir(exist_ok=True)
    cache = OUTPUTS_DIR / f"{case_dir.name}_output.json"
    cache.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# AGENTES LLM
# ══════════════════════════════════════════════════════════════════════════════

def run_agent_on_case(case_dir: Path, backend: str = "groq") -> dict:
    if str(STREAMLIT_DIR) not in sys.path:
        sys.path.insert(0, str(STREAMLIT_DIR))
    os.environ["LLM_BACKEND"] = backend
    original_dir = os.getcwd()
    os.chdir(STREAMLIT_DIR)
    try:
        from agents.extractor import extract_timestamps
        
        txt_files = list(case_dir.glob("*.txt"))
        carta = next((f for f in txt_files
                      if "consulta" not in f.name
                      and "mortalidade" not in f.name), None)
        if not carta:
            return {}

        # AGENTE 1: Timestamps
        raw = extract_timestamps(carta)
        
        # AGENTE 2: Métricas derivadas (Python puro)
        sys.path.insert(0, str(STREAMLIT_DIR / "agents"))
        from metrics import calculate_metrics
        raw["metrics"] = calculate_metrics(raw.get("timestamps", {}))

        # Guarda cache só com timestamps+metrics (antes das escalas, que são mais lentas)
        save_cached_output(case_dir, raw)

        # AGENTE 3: Escalas — isolado em try/except para não quebrar timestamps+metrics
        raw["scales"] = {}
        try:
            from agents.scales import extract_scales
            consulta = next((f for f in txt_files if "consulta" in f.name), None)

            raw["scales"]["carta"] = extract_scales(carta)
            if consulta:
                raw["scales"]["consulta"] = extract_scales(consulta)
        except Exception as e:
            print(f"    ⚠️  Escalas falharam em {case_dir.name}: {e}")
            # Continua sem escalas — timestamps e métricas ficam válidos

        return flatten_extractor_output(raw)
    finally:
        os.chdir(original_dir)


# ══════════════════════════════════════════════════════════════════════════════
# AVALIAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_case(predicted: dict, ground_truth: dict) -> dict:
    results = {}
    for var in ALL_VARS:
        comparator = COMPARATORS.get(var, compare_categorical)
        results[var] = comparator(predicted.get(var), ground_truth.get(var))
    return results

def aggregate_metrics(case_results: list[dict]) -> pd.DataFrame:
    agg = defaultdict(lambda: {"tp":0,"fp":0,"fn":0,"tn":0,"mae_vals":[]})
    for cr in case_results:
        for var, res in cr.items():
            agg[var]["tp"] += res.get("tp", 0)
            agg[var]["fp"] += res.get("fp", 0)
            agg[var]["fn"] += res.get("fn", 0)
            agg[var]["tn"] += res.get("tn", 0)
            for key in ("mae_min","mae"):
                v = res.get(key)
                if v is not None: agg[var]["mae_vals"].append(v)
    rows = []
    for var, a in agg.items():
        tp, fp, fn = a["tp"], a["fp"], a["fn"]
        prec   = tp/(tp+fp) if (tp+fp)>0 else None
        recall = tp/(tp+fn) if (tp+fn)>0 else None
        f1     = (2*prec*recall/(prec+recall)
                  if (prec is not None and recall is not None and (prec+recall)>0) else None)
        mae    = sum(a["mae_vals"])/len(a["mae_vals"]) if a["mae_vals"] else None
        group  = ("timestamp" if var in TIMESTAMP_VARS else "metric" if var in METRIC_VARS
                  else "scale" if var in SCALE_VARS else "binary" if var in BINARY_VARS
                  else "numeric" if var in NUMERIC_VARS else "categorical")
        rows.append({
            "variable": var, "group": group,
            "TP": tp, "FP": fp, "FN": fn, "TN": a["tn"],
            "precision": round(prec,4)   if prec   is not None else None,
            "recall":    round(recall,4) if recall is not None else None,
            "F1":        round(f1,4)     if f1     is not None else None,
            "MAE":       round(mae,2)    if mae    is not None else None,
            "n_compared": tp+fp+fn+a["tn"],
        })
    df = pd.DataFrame(rows).set_index("variable")
    order = {"timestamp":0,"metric":1,"scale":2,"binary":3,"numeric":4,"categorical":5}
    df["_ord"] = df["group"].map(order)
    return df.sort_values(["_ord","variable"]).drop(columns="_ord")


# ══════════════════════════════════════════════════════════════════════════════
# RELATÓRIO
# ══════════════════════════════════════════════════════════════════════════════

def print_report(df: pd.DataFrame, n_cases: int, elapsed: float):
    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  RELATÓRIO DE VALIDAÇÃO — {n_cases} casos  |  {elapsed:.1f}s")
    print(sep)
    for group in ["timestamp","metric","scale","binary","numeric","categorical"]:
        sub = df[df["group"]==group]
        if sub.empty: continue
        print(f"\n▶ {group.upper()}")
        print(f"  {'Variável':<25} {'Prec':>6} {'Rec':>6} {'F1':>6} {'MAE':>8} {'TP':>5} {'FP':>5} {'FN':>5}")
        print("  " + "-"*68)
        for var, row in sub.iterrows():
            p_s   = f"{row.precision:>6.3f}" if row.precision is not None else "   n/a"
            r_s   = f"{row.recall:>6.3f}"    if row.recall    is not None else "   n/a"
            f1_s  = f"{row.F1:>6.3f}"        if row.F1        is not None else "   n/a"
            mae_s = f"{row.MAE:>8.2f}"       if row.MAE       is not None else "     n/a"
            print(f"  {var:<25} {p_s} {r_s} {f1_s} {mae_s} {row.TP:>5} {row.FP:>5} {row.FN:>5}")
    print(f"\n{sep}\n")

def save_report(df: pd.DataFrame, n_cases: int, backend: str):
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = REPORT_DIR / f"validation_{backend}_{n_cases}casos_{ts}"
    df.to_csv(f"{stem}.csv")
    try:
        with pd.ExcelWriter(f"{stem}.xlsx", engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Métricas")
            from openpyxl.styles import PatternFill
            ws     = writer.sheets["Métricas"]
            green  = PatternFill("solid", fgColor="C6EFCE")
            yellow = PatternFill("solid", fgColor="FFEB9C")
            red    = PatternFill("solid", fgColor="FFC7CE")
            f1_col = list(df.columns).index("F1") + 2
            for row_idx in range(2, len(df)+2):
                cell = ws.cell(row=row_idx, column=f1_col)
                val  = cell.value
                if not isinstance(val, (int, float)): continue
                cell.fill = green if val>=0.9 else (yellow if val>=0.7 else red)
    except Exception as e:
        print(f"  ⚠️  Excel não gerado ({e}) — CSV disponível.")
    print(f"\n📄 Relatório guardado em:\n   {stem}.csv\n   {stem}.xlsx")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend",   default="groq", choices=["groq","ollama"])
    parser.add_argument("--use-cache", action="store_true")
    parser.add_argument("--cases",     type=int, default=0)
    args = parser.parse_args()

    if not DATA_DIR.exists():
        print(f"❌ Pasta de dados não encontrada:\n   {DATA_DIR}")
        sys.exit(1)

    case_dirs = sorted(d for d in DATA_DIR.iterdir() if d.is_dir())
    if args.cases:
        case_dirs = case_dirs[:args.cases]

    print(f"\n🔍 A validar {len(case_dirs)} casos | backend={args.backend}")
    print(f"   Dados: {DATA_DIR}\n")
    t0 = time.time()

    case_results, errors = [], []

    for i, case_dir in enumerate(case_dirs, 1):
        gt = load_ground_truth(case_dir)
        if gt is None:
            errors.append({"case": case_dir.name, "error": "missing_gt"})
            continue

        pred = load_cached_output(case_dir) if args.use_cache else None
        if pred is None:
            try:
                pred = run_agent_on_case(case_dir, backend=args.backend)
            except Exception as e:
                print(f"  ❌ [{i:3d}] {case_dir.name}: {e}")
                errors.append({"case": case_dir.name, "error": str(e)})
                continue

        case_results.append(evaluate_case(pred, gt))
        print(f"  ✅ [{i:3d}/{len(case_dirs)}] {case_dir.name}")

    elapsed = time.time() - t0

    if not case_results:
        print("❌ Nenhum resultado para agregar.")
        sys.exit(1)

    df = aggregate_metrics(case_results)
    print_report(df, len(case_results), elapsed)
    save_report(df, len(case_results), args.backend)

    if errors:
        err_path = REPORT_DIR / "validation_errors.json"
        err_path.write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"⚠️  {len(errors)} erros em:\n   {err_path}")

if __name__ == "__main__":
    main()