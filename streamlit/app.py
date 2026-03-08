import streamlit as st
from pathlib import Path
from main import run_pipeline

st.set_page_config(page_title="AVC — Extração Clínica", layout="wide")
st.title("🧠 Extração de Dados Clínicos — AVC Isquémico")
st.caption("Fase 1: Timestamps e Métricas Temporais")

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuração")
    import os
    from dotenv import load_dotenv
    load_dotenv()
    model = os.getenv("ACTIVE_MODEL", "não definido")
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

        with st.spinner("A processar..."):
            result = run_pipeline(tmp, verbose=False)

        tmp.unlink()

        if result["status"] == "error":
            st.error(f"Erro: {result['detail']}")
        else:
            st.success(f"✅ Concluído em {result['duration_seconds']}s  |  Modelo: `{result['model']}`")

            col1, col2 = st.columns(2)
            ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⚪"}

            # ── Timestamps ────────────────────────────────────────────────
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

            # ── Métricas ──────────────────────────────────────────────────
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

            # ── JSON completo ─────────────────────────────────────────────
            with st.expander("🔍 JSON completo"):
                st.json(result)
else:
    st.info("👆 Introduza uma carta para começar.")
