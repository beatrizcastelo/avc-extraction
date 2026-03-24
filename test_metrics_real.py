import sys
import os
sys.path.insert(0, "streamlit/agents")

from metrics import calculate_metrics

# Timestamps reais do meu relatório (caso típico Coimbra)
timestamps = {
    "admission": {"date": "15/03/2026", "value": "15:00"},      # admissaocoimbra
    "imaging_ct": {"date": "15/03/2026", "value": "15:22"},     # tcce  
    "thrombolysis": {"date": "15/03/2026", "value": "15:58"},   # fibrinolise
    "femoral_puncture": {"date": "15/03/2026", "value": "16:25"}, # puncaofemoral
    "onset_uvb": {"date": "15/03/2026", "value": "14:30"}       # sintomas
}

# Teste
metrics = calculate_metrics(timestamps)
print("✅ MÉTRICAS CALCULADAS:")
for nome, dados in metrics.items():
    print(f"  {nome}: {dados['value']}min → {dados['status']}")
