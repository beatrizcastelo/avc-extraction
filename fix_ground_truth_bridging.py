#!/usr/bin/env python3
"""
fix_ground_truth_bridging.py
Corrige o campo door_to_imaging nos ground truths dos casos bridging.

Problema: foi calculado como admissao_coimbra → tc_ce (errado)
Correcto:  admissao_origem → tc_ce (TC feita no hospital de origem)

Também corrige onset_to_door: deve ser admissao_origem → sintomas
(o doente chega ao sistema de saúde no hospital de origem, não em Coimbra)
"""

import json
import re
import shutil
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("/Users/beatrizcastelo/Documents/GitHub/groq-teste-processor/outputs_teste")


def parse_hhmm(s: str) -> int | None:
    """Converte '10h15' ou '10:15' para minutos desde meia-noite."""
    if not s or str(s).lower() in {"null", "none", "n/a"}:
        return None
    s = str(s).strip()
    m = re.match(r"^(\d{1,2})[hH:](\d{2})$", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def minutes_to_hhmm(minutes: int) -> str:
    """Converte minutos para formato 'HHhMM'."""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}h{m:02d}"


def fix_bridging_case(gt_path: Path, dry_run: bool = False) -> dict:
    """
    Corrige um ground truth de caso bridging.
    Devolve dict com as alterações feitas.
    """
    raw = json.loads(gt_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        raw = raw[0]

    tipo = raw.get("tipo", "")
    if tipo != "bridging":
        return {"skipped": True, "reason": f"tipo={tipo}"}

    ts = raw.get("timestamps", {})
    mt = raw.get("metricas_temporais", {})

    admissao_origem  = parse_hhmm(ts.get("admissao_origem"))
    admissao_coimbra = parse_hhmm(ts.get("admissao_coimbra"))
    tc_ce            = parse_hhmm(ts.get("tc_ce"))
    sintomas         = parse_hhmm(ts.get("sintomas"))

    changes = {}

    # ── door_to_imaging: admissao_origem → tc_ce ──────────────────────────
    if admissao_origem is not None and tc_ce is not None:
        novo_dti = tc_ce - admissao_origem
        if novo_dti < 0:
            novo_dti += 24 * 60  # passa meia-noite (raro mas possível)
        antigo_dti = mt.get("door_to_imaging")
        novo_dti_str = minutes_to_hhmm(novo_dti)
        if antigo_dti != novo_dti_str:
            changes["door_to_imaging"] = {"antigo": antigo_dti, "novo": novo_dti_str}
            if not dry_run:
                raw["metricas_temporais"]["door_to_imaging"] = novo_dti_str

    # ── onset_to_door: sintomas → admissao_coimbra (chegada ao sistema final)
    # Mantém admissao_coimbra como referência para onset_to_door
    # porque é a métrica clínica "tempo até ao hospital que vai tratar"
    # (não alteramos este campo — já está correcto)

    # ── door_in_door_out: admissao_origem → transferencia ─────────────────
    transferencia = parse_hhmm(ts.get("transferencia"))
    if admissao_origem is not None and transferencia is not None:
        novo_dido = transferencia - admissao_origem
        if novo_dido < 0:
            novo_dido += 24 * 60
        antigo_dido = mt.get("door_in_door_out")
        novo_dido_str = minutes_to_hhmm(novo_dido)
        if antigo_dido != novo_dido_str:
            changes["door_in_door_out"] = {"antigo": antigo_dido, "novo": novo_dido_str}
            if not dry_run:
                raw["metricas_temporais"]["door_in_door_out"] = novo_dido_str

    # ── door1_to_door2: transferencia → admissao_coimbra ──────────────────
    if transferencia is not None and admissao_coimbra is not None:
        novo_d1d2 = admissao_coimbra - transferencia
        if novo_d1d2 < 0:
            novo_d1d2 += 24 * 60
        antigo_d1d2 = mt.get("door1_to_door2")
        novo_d1d2_str = minutes_to_hhmm(novo_d1d2)
        if antigo_d1d2 != novo_d1d2_str:
            changes["door1_to_door2"] = {"antigo": antigo_d1d2, "novo": novo_d1d2_str}
            if not dry_run:
                raw["metricas_temporais"]["door1_to_door2"] = novo_d1d2_str

    # ── Guarda backup e escreve ───────────────────────────────────────────
    if changes and not dry_run:
        backup = gt_path.with_suffix(".json.bak")
        shutil.copy2(gt_path, backup)
        gt_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"changes": changes, "caso": gt_path.parent.name}


def main():
    gt_files = sorted(DATA_DIR.rglob("*ground_truth*.json"))
    def get_tipo(f):
        d = json.loads(f.read_text())
        if isinstance(d, list):
            d = d[0]
        return d.get("tipo", "")

    bridging = [f for f in gt_files
                if "bak" not in f.suffix
                and get_tipo(f) == "bridging"]

    print(f"Casos bridging encontrados: {len(bridging)}\n")

    # Dry run primeiro
    print("── DRY RUN (sem alterações) ──────────────────────────────────")
    total_changes = 0
    for f in bridging:
        result = fix_bridging_case(f, dry_run=True)
        if result.get("changes"):
            total_changes += 1
            print(f"  {result['caso']}:")
            for field, vals in result["changes"].items():
                print(f"    {field}: {vals['antigo']} → {vals['novo']}")

    print(f"\nTotal de casos a corrigir: {total_changes}/{len(bridging)}")

    if total_changes == 0:
        print("Nada a corrigir.")
        return

    confirm = input("\nAplicar correcções? (s/n): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        return

    print("\n── A APLICAR CORRECÇÕES ──────────────────────────────────────")
    for f in bridging:
        result = fix_bridging_case(f, dry_run=False)
        if result.get("changes"):
            print(f"  ✅ {result['caso']}: {list(result['changes'].keys())}")
        elif result.get("skipped"):
            pass
        else:
            print(f"  — {result['caso']}: sem alterações necessárias")

    print("\nDone. Backups guardados como .json.bak")


if __name__ == "__main__":
    main()