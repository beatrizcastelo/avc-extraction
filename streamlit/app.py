import streamlit as st
from pathlib import Path
from main import run_pipeline

st.set_page_config(page_title="AVC — Extração Clínica", layout="wide")
st.title("🧠 Extração de Dados Clínicos — AVC Isquémico")
st.caption("Timestamps · Métricas · Escalas Clínicas · Variáveis Categóricas")

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuração")
    import os
    from dotenv import load_dotenv
    load_dotenv()
    model   = os.getenv("ACTIVE_MODEL", "não definido")
    backend = "Groq (API)" if os.getenv("GROQ_API_KEY") else "Ollama (local)"
    st.write(f"**Modelo:** `{model}`")
    st.write(f"**Backend:** {backend}")

# ── Escolha do método de input ─────────────────────────────────────────────
st.subheader("Carta de Alta")
metodo = st.radio("Como quer introduzir a carta?",
                  ["📁 Upload de ficheiro", "📋 Copiar e colar texto"],
                  horizontal=True)

letter_text = ""

if metodo == "📁 Upload de ficheiro":
    uploaded = st.file_uploader("Carregar carta (.txt)", type=["txt"])
    if uploaded:
        letter_text = uploaded.read().decode("utf-8")
        with st.expander("👁️ Ver carta"):
            st.text(letter_text)
else:
    letter_text = st.text_area(
        "Cole a carta aqui",
        height=300,
        placeholder="Cole aqui o texto completo da carta de alta..."
    )
    if letter_text:
        with st.expander("👁️ Ver carta"):
            st.text(letter_text)

# ── Execução ───────────────────────────────────────────────────────────────
if letter_text:
    if st.button("▶️ Executar Extração"):
        tmp = Path("outputs") / "_tmp_input.txt"
        tmp.write_text(letter_text, encoding="utf-8")

        with st.spinner("A processar... (pode demorar 1-2 min)"):
            result = run_pipeline(tmp, verbose=False)

        tmp.unlink()

        if result["status"] == "error":
            st.error(f"Erro: {result['detail']}")
        else:
            st.success(f"✅ Concluído em {result['duration_seconds']}s  |  Modelo: `{result['model']}`")

            ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⚪"}

            # ── Linha 1: Timestamps + Métricas ────────────────────────────
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📅 Timestamps Extraídos")
                found = False
                for campo, val in result["timestamps"].items():
                    if isinstance(val, dict) and val.get("value") not in (None, "null", "NA"):
                        found = True
                        label = f"**{campo}** — {val.get('date') or ''} {val['value']}"
                        with st.expander(label):
                            excerpt = val.get("excerpt", "")
                            if excerpt and excerpt != "null":
                                st.markdown(f"> *\"{excerpt}\"*")
                            else:
                                st.caption("Sem excerto disponível")
                if not found:
                    st.info("Nenhum timestamp extraído.")

            with col2:
                st.subheader("⏱️ Métricas Calculadas")
                found = False
                for metrica, val in result["metrics"].items():
                    if val.get("value") is not None:
                        found = True
                        icon = ICON.get(val.get("status", "unknown"), "⚪")
                        st.metric(
                            label=f"{icon} {metrica.replace('_', ' ').title()}",
                            value=f"{val['value']} min"
                        )
                if not found:
                    st.info("Sem métricas calculáveis.")

            st.divider()

            # ── Linha 2: Escalas + Categóricas ────────────────────────────
            col3, col4 = st.columns(2)

            with col3:
                st.subheader("📊 Escalas Clínicas")

                # Carta de alta
                st.markdown("**Carta de Alta**")
                carta = result.get("scales", {}).get("carta", {})
                nihss = carta.get("nihss", {})
                mrs   = carta.get("mrs", {})

                escalas = {
                    "NIHSS Admissão": nihss.get("nihss_admissao", {}),
                    "NIHSS Alta":     nihss.get("nihss_alta", {}),
                    "mRS Prévio":     mrs.get("mrs_previo", {}),
                    "mRS Alta":       mrs.get("mrs_alta", {}),
                    "mRS 3 Meses":    mrs.get("mrs_3meses", {}),
                }
                found_carta = False
                for label, entry in escalas.items():
                    v = entry.get("value") if isinstance(entry, dict) else entry
                    if v is not None:
                        found_carta = True
                        exc = entry.get("excerpt") if isinstance(entry, dict) else None
                        with st.expander(f"**{label}:** {v}"):
                            if exc and str(exc).lower() not in {"null", "none"}:
                                st.markdown(f"> *\"{exc}\"*")
                            else:
                                st.caption("Sem excerto disponível")
                if not found_carta:
                    st.caption("Nenhuma escala extraída da carta.")

                # Nota de consulta (se existir)
                consulta = result.get("scales", {}).get("consulta", {})
                if consulta:
                    st.markdown("**Nota de Consulta**")
                    nihss_c = consulta.get("nihss", {})
                    mrs_c   = consulta.get("mrs", {})
                    escalas_c = {
                        "NIHSS Admissão": nihss_c.get("nihss_admissao", {}),
                        "NIHSS Alta":     nihss_c.get("nihss_alta", {}),
                        "mRS Prévio":     mrs_c.get("mrs_previo", {}),
                        "mRS Alta":       mrs_c.get("mrs_alta", {}),
                        "mRS 3 Meses":    mrs_c.get("mrs_3meses", {}),
                    }
                    found_consulta = False
                    for label, entry in escalas_c.items():
                        v = entry.get("value") if isinstance(entry, dict) else entry
                        if v is not None:
                            found_consulta = True
                            exc = entry.get("excerpt") if isinstance(entry, dict) else None
                            with st.expander(f"**{label}:** {v}"):
                                if exc and str(exc).lower() not in {"null", "none"}:
                                    st.markdown(f"> *\"{exc}\"*")
                                else:
                                    st.caption("Sem excerto disponível")
                    if not found_consulta:
                        st.caption("Nenhuma escala extraída da consulta.")

            with col4:
                st.subheader("🏷️ Variáveis Categóricas")

                cat  = result.get("categorical", {})
                mort = result.get("mortality", {})

                # Mapa de labels legíveis
                CAT_LABELS = {
                    "tipo":           "Tipo de Episódio",
                    "etiologia_toast":"Etiologia TOAST",
                    "tratamento":     "Tratamento",
                    "territorio":     "Território Vascular",
                    "complicacoes":   "Complicações",
                }

                found_cat = False
                for key, label in CAT_LABELS.items():
                    v = cat.get(key)
                    if v is not None:
                        found_cat = True
                        st.markdown(f"**{label}:** {v}")
                if not found_cat:
                    st.info("Nenhuma variável categórica extraída.")

                st.markdown("---")
                st.markdown("**Seguimento / Mortalidade**")

                vivo = mort.get("vivo_30_dias")
                if vivo is True:
                    st.markdown("**Vivo aos 30 dias:** ✅ Sim")
                elif vivo is False:
                    st.markdown("**Vivo aos 30 dias:** ❌ Não")
                    dias = mort.get("dias_obito")
                    causa = mort.get("causa_obito")
                    if dias is not None:
                        st.markdown(f"**Dias até óbito:** {dias}")
                    if causa:
                        st.markdown(f"**Causa de óbito:** {causa}")
                else:
                    st.caption("Informação de mortalidade não disponível.")

            st.divider()

            # ── JSON completo ─────────────────────────────────────────────
            with st.expander("🔍 JSON completo"):
                st.json(result)
else:
    st.info("👆 Introduza uma carta para começar.")