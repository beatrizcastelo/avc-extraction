import json, pandas as pd
import sys
from pathlib import Path

from validate_all import flatten_extractor_output
sys.path.insert(0, "streamlit/agents")
from metrics import calculate_metrics

# 1. Carrega todos casos antigos
cases_dir = Path("outputs_teste")  # ou teu path
results = []

for case_dir in cases_dir.glob("caso_*"):
    try:
        with open(case_dir / "raw_output.json") as f:
            raw = json.load(f)
        # 2. Recalcula só métricas
        raw["metrics"] = calculate_metrics(raw.get("timestamps", {}))
        flattened = flatten_extractor_output(raw)
        results.append(flattened)
    except:
        continue

# 3. Salva novo relatório
df = pd.DataFrame(results)
df.to_csv("validation_metrics_fixed.csv", index=False)
print(f"✅ {len(results)} casos com métricas recalculadas!")
