import json
import sys
from pathlib import Path
from datetime import datetime

from agents.extractor import extract_timestamps
from agents.metrics import calculate_metrics

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


def run_pipeline(letter_path: str | Path, verbose: bool = True) -> dict:
    """
    Pipeline completo para uma carta de alta de AVC isquémico.

    Fase 1:  Extração de timestamps (Agente 1 — LLM)
    Fase 1b: Cálculo de métricas temporais (Agente 2 — Python puro)
    """
    letter_path = Path(letter_path)

    if not letter_path.exists():
        raise FileNotFoundError(f"Carta não encontrada: {letter_path}")

    if verbose:
        print(f"\n{'='*50}")
        print(f"  PIPELINE AVC — {letter_path.name}")
        print(f"{'='*50}")

    # ── FASE 1: Extração de timestamps via LLM ─────────────────────────────
    if verbose:
        print("\n[1/2] A extrair timestamps...")

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

    # ── FASE 1b: Cálculo de métricas (sem LLM) ────────────────────────────
    if verbose:
        print("\n[2/2] A calcular métricas temporais...")

    metrics = calculate_metrics(timestamps)

    if verbose:
        calculated = [k for k, v in metrics.items() if v.get("value") is not None]
        print(f"    ✓ {len(calculated)}/{len(metrics)} métricas calculadas")

    # ── Consolidação final ─────────────────────────────────────────────────
    output = {
        "status": "ok",
        "source_file": letter_path.name,
        "processed_at": datetime.now().isoformat(),
        "model": extraction_result.get("_meta", {}).get("model", "unknown"),
        "backend": extraction_result.get("_meta", {}).get("backend", "unknown"),
        "duration_seconds": extraction_result.get("_meta", {}).get("duration_seconds", 0),
        "timestamps": timestamps,
        "metrics": metrics
    }

    # Guarda JSON automaticamente
    out_file = OUTPUT_DIR / letter_path.with_suffix(".json").name
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"\n  Resultado guardado em: {out_file}")
        _print_summary(output)

    return output


def _print_summary(result: dict):
    """Resumo no terminal para debug."""
    ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⚪"}

    print(f"\n{'─'*50}")
    print("  TIMESTAMPS EXTRAÍDOS")
    print(f"{'─'*50}")
    for campo, val in result["timestamps"].items():
        if isinstance(val, dict) and val.get("value") not in (None, "null", "NA"):
            data = val.get("date") or ""
            hora = val.get("value", "")
            print(f"  {campo:25s} → {data} {hora}")
            excerpt = val.get("excerpt", "")
            if excerpt and excerpt != "null":
                print(f"  {'':25s}   \"{excerpt[:70]}\"")

    print(f"\n{'─'*50}")
    print("  MÉTRICAS CALCULADAS")
    print(f"{'─'*50}")
    for metrica, val in result["metrics"].items():
        if val.get("value") is not None:
            icon = ICON.get(val.get("status", "unknown"), "⚪")
            print(f"  {icon} {metrica:25s} → {val['value']} min")


# ── Quando corrido directamente no terminal ────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python main.py <carta.txt>")
        print("Exemplo: python main.py ../data/caso001.txt")
        sys.exit(1)

    run_pipeline(sys.argv[1])
