#!/usr/bin/env python3
"""
process_batch.py — Processa casos em batch e guarda na base de dados.

Diferença do validate_all.py:
  - NÃO compara com ground truth
  - Guarda resultados na base de dados PostgreSQL
  - Mantém JSONs como backup em streamlit/outputs/

Uso:
  # Processar todos os casos numa pasta
  python process_batch.py --data /caminho/para/casos

  # Processar apenas os primeiros N casos
  python process_batch.py --data /caminho/para/casos --cases 10

  # Processar um caso específico
  python process_batch.py --data /caminho/para/casos --case caso_001

  # Usar cache (não volta a chamar o LLM para casos já processados)
  python process_batch.py --data /caminho/para/casos --use-cache
"""

import argparse
import os
import sys
import time
from pathlib import Path

# O script pode estar dentro de streamlit/ (Docker) ou na raiz (local)
# Detecta automaticamente onde está
_script_dir = Path(__file__).parent
if (_script_dir / "main.py").exists():
    # Está dentro de streamlit/
    STREAMLIT_DIR = _script_dir
else:
    # Está na raiz do projecto
    STREAMLIT_DIR = _script_dir / "streamlit"

sys.path.insert(0, str(STREAMLIT_DIR))
os.chdir(STREAMLIT_DIR)


def load_cached(case_dir: Path) -> bool:
    """Verifica se o caso já tem JSON gerado."""
    output = STREAMLIT_DIR / "outputs" / f"{case_dir.name}_output.json"
    return output.exists()


def find_carta(case_dir: Path) -> Path | None:
    """Encontra a carta de alta na pasta do caso."""
    for f in case_dir.glob("*.txt"):
        if "consulta" not in f.name.lower() and "mortalidade" not in f.name.lower():
            return f
    return None


def process_case(case_dir: Path, backend: str, use_cache: bool) -> dict:
    """Processa um caso e guarda na BD. Devolve o resultado."""
    from main import run_pipeline

    carta = find_carta(case_dir)
    if not carta:
        return {"status": "error", "detail": "Carta não encontrada"}

    # Se usar cache e o JSON já existe, recarrega e guarda só na BD
    if use_cache:
        output_file = STREAMLIT_DIR / "outputs" / f"{case_dir.name}_output.json"
        if output_file.exists():
            import json
            result = json.loads(output_file.read_text(encoding="utf-8"))
            # Normaliza status (JSONs antigos podem ter None)
            if result.get("status") is None:
                result["status"] = "ok"
            # Guarda na BD mesmo que venha do cache
            try:
                from database import save_episodio
                save_episodio(result)
            except Exception as e:
                pass
            return result

    # Corre o pipeline completo
    os.environ["LLM_BACKEND"] = backend
    return run_pipeline(carta, verbose=False)


def main():
    parser = argparse.ArgumentParser(
        description="Processa casos de AVC e guarda na base de dados."
    )
    parser.add_argument("--data",      required=True, type=str,
                        help="Caminho para a pasta com os casos")
    parser.add_argument("--backend",   default="ollama", choices=["groq", "ollama"],
                        help="Backend LLM a usar (default: ollama)")
    parser.add_argument("--cases",     type=int, default=0,
                        help="Processar apenas os primeiros N casos")
    parser.add_argument("--case",      type=str, default=None,
                        help="Processar um caso específico pelo nome")
    parser.add_argument("--use-cache", action="store_true",
                        help="Usar JSONs já gerados (não chama o LLM)")
    args = parser.parse_args()

    data_dir = Path(args.data)
    if not data_dir.exists():
        print(f"❌ Pasta não encontrada: {data_dir}")
        sys.exit(1)

    # Descobre casos
    all_dirs = sorted(d for d in data_dir.iterdir() if d.is_dir())

    if args.case:
        case_dirs = [d for d in all_dirs if args.case in d.name]
        if not case_dirs:
            print(f"❌ Caso não encontrado: {args.case}")
            sys.exit(1)
    else:
        case_dirs = all_dirs
        if args.cases:
            case_dirs = case_dirs[:args.cases]

    total   = len(case_dirs)
    success = 0
    errors  = []
    t0      = time.time()

    print(f"\n🔄 A processar {total} caso(s) | backend={args.backend}")
    print(f"   Dados: {data_dir}")
    print(f"   Cache: {'sim' if args.use_cache else 'não'}\n")

    for i, case_dir in enumerate(case_dirs, 1):
        carta = find_carta(case_dir)
        if not carta:
            print(f"  ⚠️  [{i:3d}/{total}] {case_dir.name} — sem carta, ignorado")
            errors.append(case_dir.name)
            continue

        try:
            result = process_case(case_dir, args.backend, args.use_cache)
            if result.get("status") == "ok":
                success += 1
                tipo = result.get("categorical", {}).get("tipo", "?")
                dtn  = result.get("metrics", {}).get("door_to_needle", {}).get("value", "—")
                print(f"  ✅ [{i:3d}/{total}] {case_dir.name} | tipo={tipo} | DTN={dtn}min")
            else:
                errors.append(case_dir.name)
                print(f"  ❌ [{i:3d}/{total}] {case_dir.name} — {result.get('detail', 'erro')}")
        except Exception as e:
            import traceback
            errors.append(case_dir.name)
            print(f"  ❌ [{i:3d}/{total}] {case_dir.name} — {e}")
            traceback.print_exc()

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  ✅ {success}/{total} casos processados e guardados na BD")
    print(f"  ⏱️  Tempo total: {elapsed:.1f}s")
    if errors:
        print(f"  ❌ {len(errors)} erro(s): {', '.join(errors[:5])}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()