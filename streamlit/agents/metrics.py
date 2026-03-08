from datetime import datetime
from typing import Optional


def _parse_dt(date_str: Optional[str], time_str: Optional[str]) -> Optional[datetime]:
    if not time_str or time_str in ("null", "NA", None):
        return None
    # Normaliza "15h55" → "15:55"
    time_str = time_str.replace("h", ":").strip()
    try:
        if date_str and date_str not in ("null", None):
            return datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
        return datetime.strptime(time_str, "%H:%M")
    except ValueError:
        return None


def _minutes(t1: Optional[datetime], t2: Optional[datetime]) -> Optional[int]:
    if t1 and t2:
        m = int((t2 - t1).total_seconds() / 60)
        return m if m >= 0 else None
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

    onset        = dt("onset_uvb")
    admitted     = dt("admission")
    imaging      = dt("imaging_ct")
    thrombo      = dt("thrombolysis")
    puncture     = dt("femoral_puncture")
    recan        = dt("recanalization")
    door1_in     = dt("door1_admission")
    door1_out    = dt("door1_departure")
    door2        = dt("door2")

    return {
        "onset_to_door": {
            "value":  _minutes(onset, admitted),
            "unit":   "min",
            "status": "unknown"
        },
        "door_to_imaging": {
            "value":  _minutes(admitted, imaging),
            "unit":   "min",
            "status": _status(_minutes(admitted, imaging), 25, 45)
        },
        "door_to_needle": {
            "value":  _minutes(admitted, thrombo),
            "unit":   "min",
            "status": _status(_minutes(admitted, thrombo), 60, 90)
        },
        "door_to_puncture": {
            "value":  _minutes(admitted, puncture),
            "unit":   "min",
            "status": _status(_minutes(admitted, puncture), 90, 120)
        },
        "onset_to_needle": {
            "value":  _minutes(onset, thrombo),
            "unit":   "min",
            "status": "unknown"
        },
        "onset_to_recan": {
            "value":  _minutes(onset, recan),
            "unit":   "min",
            "status": "unknown"
        },
        "door_in_door_out": {
            "value":  _minutes(door1_in, door1_out),
            "unit":   "min",
            "status": "unknown"
        },
        "door1_to_door2": {
            "value":  _minutes(door1_out, door2),
            "unit":   "min",
            "status": "unknown"
        },
    }
