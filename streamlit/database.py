"""
database.py — Gestão da base de dados PostgreSQL
Guarda os resultados de extracção de cada episódio de AVC.
"""

import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Cria ligação ao PostgreSQL com as variáveis do .env"""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "avc_extraction"),
        user=os.getenv("POSTGRES_USER", "avc_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def init_db():
    """Cria as tabelas se não existirem."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS episodios (
            id                      SERIAL PRIMARY KEY,
            source_file             TEXT,
            processed_at            TIMESTAMP,
            model                   TEXT,
            backend                 TEXT,

            -- Tipo de episódio
            tipo                    TEXT,
            etiologia_toast         TEXT,
            tratamento              TEXT,
            territorio              TEXT,
            complicacoes            TEXT,

            -- Timestamps (HH:MM)
            ts_sintomas             TEXT,
            ts_admissao             TEXT,
            ts_admissao_origem      TEXT,
            ts_tcce                 TEXT,
            ts_fibrinolise          TEXT,
            ts_puncao_femoral       TEXT,
            ts_recanalizacao        TEXT,
            ts_transferencia        TEXT,

            -- Métricas temporais (minutos)
            onset_to_door           INTEGER,
            door_to_imaging         INTEGER,
            door_to_needle          INTEGER,
            door_to_puncture        INTEGER,
            onset_to_needle         INTEGER,
            onset_to_recan          INTEGER,
            door_in_door_out        INTEGER,
            door1_to_door2          INTEGER,

            -- Escalas clínicas
            nihss_admissao          INTEGER,
            nihss_alta              INTEGER,
            mrs_previo              INTEGER,
            mrs_alta                INTEGER,
            mrs_3meses              INTEGER,

            -- Mortalidade
            vivo_30_dias            BOOLEAN,
            dias_obito              INTEGER,
            causa_obito             TEXT,

            -- JSON completo para auditoria
            raw_json                JSONB
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


def _safe_int(val) -> Optional[int]:
    try:
        return int(val) if val is not None else None
    except (ValueError, TypeError):
        return None


def _get_ts(timestamps: dict, key: str) -> Optional[str]:
    entry = timestamps.get(key, {})
    if not isinstance(entry, dict):
        return None
    v = entry.get("value")
    if v in (None, "null", "NA"):
        return None
    return str(v)


def _get_metric(metrics: dict, key: str) -> Optional[int]:
    entry = metrics.get(key, {})
    if not isinstance(entry, dict):
        return None
    return _safe_int(entry.get("value"))


def _get_scale(scales: dict, source: str, group: str, key: str) -> Optional[int]:
    entry = scales.get(source, {}).get(group, {}).get(key, {})
    if isinstance(entry, dict):
        return _safe_int(entry.get("value"))
    return _safe_int(entry)


def save_episodio(result: dict) -> int:
    """
    Guarda o resultado do pipeline na base de dados.
    Devolve o ID do registo inserido.
    """
    init_db()

    ts   = result.get("timestamps", {})
    mt   = result.get("metrics", {})
    sc   = result.get("scales", {})
    cat  = result.get("categorical", {})
    mort = result.get("mortality", {})

    # vivo_30_dias: bool ou None
    vivo_raw = mort.get("vivo_30_dias")
    if isinstance(vivo_raw, bool):
        vivo = vivo_raw
    elif isinstance(vivo_raw, int):
        vivo = bool(vivo_raw)
    else:
        vivo = None

    # processed_at: converte string para datetime
    processed_at_raw = result.get("processed_at")
    try:
        processed_at = datetime.fromisoformat(processed_at_raw) if processed_at_raw else datetime.now()
    except Exception:
        processed_at = datetime.now()

    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO episodios (
            source_file, processed_at, model, backend,
            tipo, etiologia_toast, tratamento, territorio, complicacoes,
            ts_sintomas, ts_admissao, ts_admissao_origem, ts_tcce,
            ts_fibrinolise, ts_puncao_femoral, ts_recanalizacao, ts_transferencia,
            onset_to_door, door_to_imaging, door_to_needle, door_to_puncture,
            onset_to_needle, onset_to_recan, door_in_door_out, door1_to_door2,
            nihss_admissao, nihss_alta, mrs_previo, mrs_alta, mrs_3meses,
            vivo_30_dias, dias_obito, causa_obito,
            raw_json
        ) VALUES (
            %s,%s,%s,%s,
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s
        ) RETURNING id
    """, (
        result.get("source_file"),
        processed_at,
        result.get("model"),
        result.get("backend"),

        cat.get("tipo"),
        cat.get("etiologia_toast"),
        cat.get("tratamento"),
        cat.get("territorio"),
        cat.get("complicacoes"),

        _get_ts(ts, "onset_uvb"),
        _get_ts(ts, "admission"),
        _get_ts(ts, "door1_admission"),
        _get_ts(ts, "imaging_ct"),
        _get_ts(ts, "thrombolysis"),
        _get_ts(ts, "femoral_puncture"),
        _get_ts(ts, "recanalization"),
        _get_ts(ts, "door1_departure"),

        _get_metric(mt, "onset_to_door"),
        _get_metric(mt, "door_to_imaging"),
        _get_metric(mt, "door_to_needle"),
        _get_metric(mt, "door_to_puncture"),
        _get_metric(mt, "onset_to_needle"),
        _get_metric(mt, "onset_to_recan"),
        _get_metric(mt, "door_in_door_out"),
        _get_metric(mt, "door1_to_door2"),

        _get_scale(sc, "carta", "nihss", "nihss_admissao"),
        _get_scale(sc, "carta", "nihss", "nihss_alta"),
        _get_scale(sc, "carta", "mrs",   "mrs_previo"),
        _get_scale(sc, "carta", "mrs",   "mrs_alta"),
        _get_scale(sc, "carta", "mrs",   "mrs_3meses"),

        vivo,
        _safe_int(mort.get("dias_obito")),
        mort.get("causa_obito"),

        json.dumps(result, ensure_ascii=False),
    ))
    episodio_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return episodio_id


def get_estatisticas() -> dict:
    """Devolve estatísticas agregadas para o dashboard."""
    init_db()
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    stats = {}

    # Total
    cur.execute("SELECT COUNT(*) as n FROM episodios")
    stats["total"] = cur.fetchone()["n"]

    # Por tipo
    cur.execute("""
        SELECT tipo, COUNT(*) as n FROM episodios
        WHERE tipo IS NOT NULL GROUP BY tipo ORDER BY n DESC
    """)
    stats["por_tipo"] = {r["tipo"]: r["n"] for r in cur.fetchall()}

    # Por etiologia
    cur.execute("""
        SELECT etiologia_toast, COUNT(*) as n FROM episodios
        WHERE etiologia_toast IS NOT NULL GROUP BY etiologia_toast ORDER BY n DESC
    """)
    stats["por_etiologia"] = {r["etiologia_toast"]: r["n"] for r in cur.fetchall()}

    # Métricas temporais
    for metrica in ["door_to_needle", "door_to_imaging", "door_to_puncture",
                    "onset_to_door", "onset_to_recan"]:
        cur.execute(f"""
            SELECT ROUND(AVG({metrica})::numeric, 1) as media,
                   MIN({metrica}) as minimo, MAX({metrica}) as maximo,
                   COUNT({metrica}) as n
            FROM episodios WHERE {metrica} IS NOT NULL
        """)
        r = cur.fetchone()
        if r and r["n"] > 0:
            stats[metrica] = dict(r)

    # Qualidade ESO — door_to_needle
    cur.execute("""
        SELECT
            SUM(CASE WHEN door_to_needle <= 60 THEN 1 ELSE 0 END)::int as verde,
            SUM(CASE WHEN door_to_needle BETWEEN 61 AND 90 THEN 1 ELSE 0 END)::int as amarelo,
            SUM(CASE WHEN door_to_needle > 90 THEN 1 ELSE 0 END)::int as vermelho,
            COUNT(door_to_needle)::int as total
        FROM episodios WHERE door_to_needle IS NOT NULL
    """)
    r = cur.fetchone()
    if r and r["total"] > 0:
        stats["qualidade_dtn"] = dict(r)

    # Mortalidade 30 dias
    cur.execute("""
        SELECT
            SUM(CASE WHEN vivo_30_dias = TRUE  THEN 1 ELSE 0 END)::int as vivos,
            SUM(CASE WHEN vivo_30_dias = FALSE THEN 1 ELSE 0 END)::int as obitos,
            COUNT(*)::int as total
        FROM episodios WHERE vivo_30_dias IS NOT NULL
    """)
    r = cur.fetchone()
    if r and r["total"] > 0:
        stats["mortalidade_30d"] = dict(r)

    # NIHSS médio
    cur.execute("SELECT ROUND(AVG(nihss_admissao)::numeric,1) as media, COUNT(*) as n FROM episodios WHERE nihss_admissao IS NOT NULL")
    r = cur.fetchone()
    if r and r["n"] > 0:
        stats["nihss_admissao_medio"] = dict(r)

    # mRS alta médio
    cur.execute("SELECT ROUND(AVG(mrs_alta)::numeric,1) as media, COUNT(*) as n FROM episodios WHERE mrs_alta IS NOT NULL")
    r = cur.fetchone()
    if r and r["n"] > 0:
        stats["mrs_alta_medio"] = dict(r)

    cur.close()
    conn.close()
    return stats


def get_episodios_recentes(n: int = 10) -> list:
    """Devolve os N episódios mais recentes."""
    init_db()
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, source_file, processed_at, tipo, etiologia_toast,
               door_to_needle, door_to_imaging, nihss_admissao, mrs_alta, vivo_30_dias
        FROM episodios ORDER BY id DESC LIMIT %s
    """, (n,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows