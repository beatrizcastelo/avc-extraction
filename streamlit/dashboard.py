"""
dashboard.py — Página de estatísticas agregadas
Corre como página separada no Streamlit:
  streamlit run dashboard.py
Ou integra no app.py como segunda página.
"""

import streamlit as st
from database import get_estatisticas, get_episodios_recentes

st.set_page_config(page_title="AVC — Dashboard Clínico", layout="wide")
st.title("📊 Dashboard Clínico — AVC Isquémico")
st.caption("Estatísticas agregadas dos episódios processados")

stats = get_estatisticas()

if stats.get("total", 0) == 0:
    st.info("Ainda não existem episódios na base de dados. Processa cartas de alta no separador de extracção.")
    st.stop()

# ── Indicadores de topo ────────────────────────────────────────────────────
st.subheader("Visão Geral")
c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Total de Episódios", stats["total"])

if "nihss_admissao_medio" in stats:
    c2.metric("NIHSS Médio Admissão",
              f"{stats['nihss_admissao_medio']['media']}",
              help=f"n={stats['nihss_admissao_medio']['n']}")

if "mrs_alta_medio" in stats:
    c3.metric("mRS Médio Alta",
              f"{stats['mrs_alta_medio']['media']}",
              help=f"n={stats['mrs_alta_medio']['n']}")

if "door_to_needle" in stats:
    c4.metric("Door-to-Needle Médio",
              f"{stats['door_to_needle']['media']} min",
              help=f"n={stats['door_to_needle']['n']}")

if "mortalidade_30d" in stats:
    m = stats["mortalidade_30d"]
    pct = round(m["obitos"] / m["total"] * 100, 1) if m["total"] > 0 else 0
    c5.metric("Mortalidade 30 dias", f"{pct}%",
              help=f"{m['obitos']} óbitos em {m['total']} casos com seguimento")

st.divider()

# ── Linha 1: Tipo de episódio + Etiologia ─────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("Tipo de Episódio")
    if stats.get("por_tipo"):
        tipo_labels = {
            "fibrinolise_pre_hospitalar":     "Fibrinólise Pré-hosp.",
            "fibrinolise_pre_hospitalar_ace": "Fibrinólise Pré-hosp. (ACE)",
            "bridging":                       "Bridging",
            "tev_isolada_contraindicacao":    "TEV (contraindicação)",
            "tev_isolada_fora_janela":        "TEV (fora janela)",
            "fibrinolise_intra_hospitalar":   "Fibrinólise Intra-hosp.",
            "conservador_lacunar":            "Conservador Lacunar",
            "conservador_wake_up":            "Conservador Wake-up",
        }
        data = {tipo_labels.get(k, k): v for k, v in stats["por_tipo"].items()}
        st.bar_chart(data)
    else:
        st.caption("Sem dados.")

with col2:
    st.subheader("Etiologia TOAST")
    if stats.get("por_etiologia"):
        st.bar_chart(stats["por_etiologia"])
    else:
        st.caption("Sem dados.")

st.divider()

# ── Linha 2: Qualidade ESO + Métricas ─────────────────────────────────────
col3, col4 = st.columns(2)

with col3:
    st.subheader("Qualidade ESO — Door-to-Needle")
    if "qualidade_dtn" in stats:
        q = stats["qualidade_dtn"]
        total = q["total"]
        st.markdown(f"**Total com fibrinólise:** {total} casos")
        st.markdown(f"🟢 **≤ 60 min (verde):** {q['verde']} casos ({round(q['verde']/total*100)}%)")
        st.markdown(f"🟡 **61–90 min (amarelo):** {q['amarelo']} casos ({round(q['amarelo']/total*100)}%)")
        st.markdown(f"🔴 **> 90 min (vermelho):** {q['vermelho']} casos ({round(q['vermelho']/total*100)}%)")
        # Barra visual
        st.progress(q["verde"] / total if total > 0 else 0,
                    text=f"{round(q['verde']/total*100)}% dentro do target ESO")
    else:
        st.caption("Sem casos com door-to-needle calculado.")

with col4:
    st.subheader("Métricas Temporais Médias")
    METRIC_LABELS = {
        "onset_to_door":    "Onset-to-Door",
        "door_to_imaging":  "Door-to-Imaging",
        "door_to_needle":   "Door-to-Needle",
        "door_to_puncture": "Door-to-Puncture",
        "onset_to_recan":   "Onset-to-Recan",
    }
    TARGETS = {
        "door_to_imaging":  (25, 45),
        "door_to_needle":   (60, 90),
        "door_to_puncture": (90, 120),
    }
    for key, label in METRIC_LABELS.items():
        if key in stats:
            m = stats[key]
            target = TARGETS.get(key)
            if target:
                media = m["media"]
                if media <= target[0]:
                    icon = "🟢"
                elif media <= target[1]:
                    icon = "🟡"
                else:
                    icon = "🔴"
            else:
                icon = "⚪"
            st.metric(
                label=f"{icon} {label}",
                value=f"{m['media']} min",
                help=f"Min: {m['minimo']} | Máx: {m['maximo']} | n={m['n']}"
            )

st.divider()

# ── Episódios recentes ─────────────────────────────────────────────────────
st.subheader("Episódios Recentes")
recentes = get_episodios_recentes(10)
if recentes:
    import pandas as pd
    df = pd.DataFrame(recentes)
    df["vivo_30_dias"] = df["vivo_30_dias"].map({1: "✅ Sim", 0: "❌ Não"}).fillna("?")
    df = df.rename(columns={
        "id":               "ID",
        "source_file":      "Ficheiro",
        "processed_at":     "Processado em",
        "tipo":             "Tipo",
        "etiologia_toast":  "Etiologia",
        "door_to_needle":   "DTN (min)",
        "door_to_imaging":  "DTI (min)",
        "nihss_admissao":   "NIHSS Adm.",
        "mrs_alta":         "mRS Alta",
        "vivo_30_dias":     "Vivo 30d",
    })
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.caption("Sem episódios registados.")