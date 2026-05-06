#!/usr/bin/env python3
"""
recalculate_metrics.py — Script de uso único.
Recalcula as métricas temporais em todos os JSONs de cache
sem chamar o LLM — usa o metrics.py actualizado.

Apagar depois de correr.

Uso:
    cd /Users/beatrizcastelo/Documents/GitHub/avc-extraction
    python recalculate_metrics.py
"""

import json
import sys
from pathlib import Path

BASE_DIR      = Path(__file__).parent
STREAMLIT_DIR = BASE_DIR / "streamlit"
OUTPUTS_DIR   = STREAMLIT_DIR / "outputs"

sys.path.insert(0, str(STREAMLIT_DIR))
sys.path.insert(0, str(STREAMLIT_DIR / "agents"))

from agents.metrics import calculate_metrics

json_files = sorted(OUTPUTS_DIR.glob("*_output.json"))
print(f"\n🔄 A recalcular métricas em {len(json_files)} ficheiros...\n")

updated = 0
errors  = 0

for f in json_files:
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
        timestamps = raw.get("timestamps", {})
        if not timestamps:
            print(f"  ⚠️  {f.name} — sem timestamps, ignorado")
            continue

        raw["metrics"] = calculate_metrics(timestamps)
        f.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        updated += 1
        print(f"  ✅ {f.name}")
    except Exception as e:
        errors += 1
        print(f"  ❌ {f.name} — {e}")

print(f"\n{'='*50}")
print(f"  ✅ Actualizados: {updated}")
print(f"  ❌ Erros:        {errors}")
print(f"{'='*50}")
print("\nPodes apagar este script agora. Corre o validate_all.py com --use-cache.\n")