from datetime import datetime
from typing import Optional

"""Agente 2 — calcula métricas temporais derivadas a partir dos timestamps extraídos pelo Agente 1.
Lógica Python pura, sem LLM.

REGRAS CLÍNICAS:
- door_to_imaging: usa sempre a hora de admissão do HOSPITAL DE ORIGEM (door1_admission)
  quando disponível, porque a TC é feita no hospital de origem nos casos inter-hospitalares.
  Em casos pré/intra-hospitalares usa admission (Coimbra).
- door_to_needle: nos casos inter-hospitalares usa door1_admission (fibrinólise feita
  no hospital de origem); nos casos directos usa admission (Coimbra).
- door_to_puncture: usa sempre admission (Coimbra), porque a trombectomia é sempre em Coimbra.
- onset_to_door: usa sempre admission (Coimbra) como referência de chegada ao sistema final.
- door1_to_door2: admissão no hospital de origem → chegada a Coimbra (door2).
- door_in_door_out: admissão no hospital de origem → saída do hospital de origem (door1_departure).
"""


def _parse_dt(date_str: Optional[str], time_str: Optional[str]) -> Optional[datetime]:
    if not time_str or time_str in ("null", "NA", None):
        return None
    time_str = time_str.replace("h", ":").strip()
    try:
        if date_str and date_str not in ("null", None):
            return datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
        return datetime.strptime(time_str, "%H:%M")
    except ValueError:
        return None


def _minutes(t1: Optional[datetime], t2: Optional[datetime], max_minutes: int = 600) -> Optional[int]:
    if t1 and t2:
        m = int((t2 - t1).total_seconds() / 60)
        if m < 0 or m > max_minutes:
            return None
        return m
    return None


def _status(value: Optional[int], green: int, yellow: int) -> str:
    if value is None:
        return "unknown"
    if value <= green:
        return "green"
    if value <= yellow:
        return "yellow"
    return "red"


def calculate_metrics(timestamps: dict) -> dict:
    """
    Agente 2 — calcula métricas temporais derivadas.
    Não usa LLM — lógica Python pura.

    Benchmarks ESO/AHA 2023:
      door_to_imaging  → verde ≤25min, amarelo ≤45min
      door_to_needle   → verde ≤60min, amarelo ≤90min
      door_to_puncture → verde ≤90min, amarelo ≤120min
    """
    def dt(key):
        t = timestamps.get(key, {})
        return _parse_dt(t.get("date"), t.get("value"))

    onset     = dt("onset_uvb")
    admitted  = dt("admission")        # admissão em Coimbra (hospital final)
    imaging   = dt("imaging_ct")       # TC — sempre no hospital de origem
    thrombo   = dt("thrombolysis")
    puncture  = dt("femoral_puncture")
    recan     = dt("recanalization")
    door1_in  = dt("door1_admission")  # admissão no hospital de origem
    door1_out = dt("door1_departure")  # saída do hospital de origem
    door2     = dt("door2")            # chegada a Coimbra

    # Inter-hospitalar: tem door1_admission
    inter_hosp = door1_in is not None

    # Para door_to_imaging: usa door1_admission se inter-hospitalar,
    # caso contrário usa admission (pré/intra-hospitalar).
    door_for_imaging = door1_in if inter_hosp else admitted

    # Para door_to_needle: nos inter-hospitalares a fibrinólise é no hospital de origem
    door_for_needle = door1_in if inter_hosp else admitted

    return {
        "onset_to_door": {
            "value":  _minutes(onset, admitted, max_minutes=600),
            "unit":   "min",
            "status": "unknown"
        },
        "door_to_imaging": {
            # TC no hospital de origem → door1_admission; TC em Coimbra → admission
            "value":  _minutes(door_for_imaging, imaging),
            "unit":   "min",
            "status": _status(_minutes(door_for_imaging, imaging), 25, 45)
        },
        "door_to_needle": {
            # Inter-hosp: fibrinólise no hospital de origem → door1_admission
            # Directo: fibrinólise em Coimbra → admission
            "value":  _minutes(door_for_needle, thrombo),
            "unit":   "min",
            "status": _status(_minutes(door_for_needle, thrombo), 60, 90)
        },
        "door_to_puncture": {
            # Trombectomia sempre em Coimbra → admission
            "value":  _minutes(admitted, puncture),
            "unit":   "min",
            "status": _status(_minutes(admitted, puncture), 90, 120)
        },
        "onset_to_needle": {
            "value":  _minutes(onset, thrombo, max_minutes=600),
            "unit":   "min",
            "status": "unknown"
        },
        "onset_to_recan": {
            "value":  _minutes(onset, recan, max_minutes=600),
            "unit":   "min",
            "status": "unknown"
        },
        "door_in_door_out": {
            # Tempo no hospital de origem: admissão origem → saída origem
            "value":  _minutes(door1_in, door1_out),
            "unit":   "min",
            "status": "unknown"
        },
        "door1_to_door2": {
            # FIX: admissão origem → chegada Coimbra (door2)
            # (antes era door1_departure → door2, inconsistente com ground truth)
            "value":  _minutes(door1_in, door2, max_minutes=600),
            "unit":   "min",
            "status": "unknown"
        },
    }