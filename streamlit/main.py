import json
import sys
from pathlib import Path
from datetime import datetime

from agents.extractor import extract_timestamps
from agents.metrics import calculate_metrics
from agents.scales import extract_scales
from agents.categorical import extract_categorical, extract_mortality

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


def run_pipeline(letter_path: str | Path, verbose: bool = True) -> dict:
    """
    Pipeline completo para uma carta de alta de AVC isquémico.

    Fase 1:  Extração de timestamps          (Agente 1 — LLM)
    Fase 1b: Cálculo de métricas temporais   (Agente 2 — Python puro)
    Fase 2:  Extração de escalas NIHSS + mRS (Agente 3 — LLM)
    Fase 3:  Extração de variáveis categóricas + mortalidade (Agente 4 — LLM)
    """
    letter_path = Path(letter_path)

    if not letter_path.exists():
        raise FileNotFoundError(f"Carta não encontrada: {letter_path}")

    if verbose:
        print(f"\n{'='*50}")
        print(f"  PIPELINE AVC — {letter_path.name}")
        print(f"{'='*50}")

    # ── FASE 1: Timestamps ────────────────────────────────────────────────────
    if verbose:
        print("\n[1/4] A extrair timestamps...")

    extraction_result = extract_timestamps(letter_path)

    if "_parse_error" in extraction_result.get("timestamps", {}):
        return {
            "status": "error",
            "stage": "extraction",
            "detail": extraction_result["timestamps"]["_parse_error"],
            "raw": extraction_result["timestamps"].get("_raw_response", "")
        }

    timestamps = extraction_result["timestamps"]

    if verbose:
        extracted = [k for k, v in timestamps.items()
                     if isinstance(v, dict) and v.get("value") not in (None, "null", "NA")]
        print(f"    ✓ {len(extracted)}/{len(timestamps)} timestamps extraídos")

    # ── FASE 1b: Métricas ─────────────────────────────────────────────────────
    if verbose:
        print("\n[2/4] A calcular métricas temporais...")

    metrics = calculate_metrics(timestamps)

    if verbose:
        calculated = [k for k, v in metrics.items() if v.get("value") is not None]
        print(f"    ✓ {len(calculated)}/{len(metrics)} métricas calculadas")

    # ── FASE 2: Escalas ───────────────────────────────────────────────────────
    if verbose:
        print("\n[3/4] A extrair escalas clínicas (NIHSS + mRS)...")

    scales_result = {}
    try:
        scales_result["carta"] = extract_scales(letter_path)
        # Consulta de seguimento (se existir na mesma pasta)
        consulta = _find_consulta(letter_path)
        if consulta:
            scales_result["consulta"] = extract_scales(consulta)
    except Exception as e:
        if verbose:
            print(f"    ⚠️  Escalas falharam: {e}")

    # ── FASE 3: Variáveis categóricas + mortalidade ───────────────────────────
    if verbose:
        print("\n[4/4] A extrair variáveis categóricas (RF6)...")

    categorical_result = {}
    try:
        categorical_result = extract_categorical(letter_path)
        if verbose:
            extracted_cat = [k for k, v in categorical_result.items() if v is not None]
            print(f"    ✓ {len(extracted_cat)} variáveis categóricas extraídas")
    except Exception as e:
        if verbose:
            print(f"    ⚠️  Categóricas falharam: {e}")

    mortality_result = {}
    try:
        mortality_note = _find_mortality(letter_path)
        if mortality_note:
            mortality_result = extract_mortality(mortality_note)
            if verbose:
                print(f"    ✓ Mortalidade extraída de {mortality_note.name}")
        else:
            mortality_result = {"vivo_30_dias": None, "dias_obito": None, "causa_obito": None}
    except Exception as e:
        if verbose:
            print(f"    ⚠️  Mortalidade falhou: {e}")

    # ── Consolidação ──────────────────────────────────────────────────────────
    output = {
        "status": "ok",
        "source_file": letter_path.name,
        "processed_at": datetime.now().isoformat(),
        "model": extraction_result.get("_meta", {}).get("model", "unknown"),
        "backend": extraction_result.get("_meta", {}).get("backend", "unknown"),
        "duration_seconds": extraction_result.get("_meta", {}).get("duration_seconds", 0),
        "timestamps":   timestamps,
        "metrics":      metrics,
        "scales":       scales_result,
        "categorical":  categorical_result,
        "mortality":    mortality_result,
        "binary":       {}   # Reservado para agente binário futuro
    }

    # Guarda JSON automaticamente
    out_file = OUTPUT_DIR / letter_path.with_suffix(".json").name
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"\n  Resultado guardado em: {out_file}")
        _print_summary(output)

    return output


# ── helpers de descoberta de ficheiros ────────────────────────────────────────

def _find_consulta(letter_path: Path) -> Path | None:
    """Procura nota de consulta na mesma pasta que a carta."""
    for f in letter_path.parent.glob("*.txt"):
        if "consulta" in f.name.lower():
            return f
    return None


def _find_mortality(letter_path: Path) -> Path | None:
    """Procura nota de mortalidade na mesma pasta que a carta."""
    for f in letter_path.parent.glob("*.txt"):
        if "mortalidade" in f.name.lower():
            return f
    return None


# ── resumo terminal ───────────────────────────────────────────────────────────

def _print_summary(result: dict):
    ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⚪"}

    print(f"\n{'─'*50}")
    print("  TIMESTAMPS")
    print(f"{'─'*50}")
    for campo, val in result["timestamps"].items():
        if isinstance(val, dict) and val.get("value") not in (None, "null", "NA"):
            data  = val.get("date") or ""
            hora  = val.get("value", "")
            print(f"  {campo:25s} → {data} {hora}")

    print(f"\n{'─'*50}")
    print("  MÉTRICAS")
    print(f"{'─'*50}")
    for metrica, val in result["metrics"].items():
        if val.get("value") is not None:
            icon = ICON.get(val.get("status", "unknown"), "⚪")
            print(f"  {icon} {metrica:25s} → {val['value']} min")

    print(f"\n{'─'*50}")
    print("  ESCALAS (carta)")
    print(f"{'─'*50}")
    for escala, val in result["scales"].get("carta", {}).get("nihss", {}).items():
        v = val.get("value") if isinstance(val, dict) else val
        if v is not None:
            print(f"  {escala:25s} → {v}")
    for escala, val in result["scales"].get("carta", {}).get("mrs", {}).items():
        v = val.get("value") if isinstance(val, dict) else val
        if v is not None:
            print(f"  {escala:25s} → {v}")

    print(f"\n{'─'*50}")
    print("  CATEGÓRICAS (RF6)")
    print(f"{'─'*50}")
    for var in ["tipo","etiologia_toast","tratamento","territorio","complicacoes"]:
        v = result["categorical"].get(var)
        if v is not None:
            print(f"  {var:25s} → {v}")

    print(f"\n{'─'*50}")
    print("  MORTALIDADE")
    print(f"{'─'*50}")
    for var in ["vivo_30_dias","dias_obito","causa_obito"]:
        v = result["mortality"].get(var)
        print(f"  {var:25s} → {v}")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python main.py <carta.txt>")
        sys.exit(1)
    run_pipeline(sys.argv[1])