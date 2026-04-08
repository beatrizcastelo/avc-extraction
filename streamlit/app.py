import streamlit as st
import os
from dotenv import load_dotenv
from styles import apply_theme

load_dotenv()

st.set_page_config(
    page_title="AVC — Extração Clínica",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_theme()

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 AVC Extração")
    st.markdown("*Sistema de Extracção Clínica*")
    st.divider()
    model   = os.getenv("ACTIVE_MODEL", "não definido")
    backend = "Groq (API)" if os.getenv("LLM_BACKEND", "ollama").lower() == "groq" else "Ollama (local)"
    st.markdown(f"**Modelo:** `{model}`")
    st.markdown(f"**Backend:** {backend}")

# ── Página inicial ─────────────────────────────────────────────────────────
st.title("Extração de Dados Clínicos — AVC Isquémico")
st.caption("Sistema de suporte à monitorização da qualidade assistencial · ULS Coimbra")
st.divider()

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div style="
        background: #F0F7FF;
        border: 1.5px solid #2D5A9E;
        border-radius: 12px;
        padding: 28px 24px;
        text-align: center;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    ">
        <div style="font-size: 2.5rem; margin-bottom: 10px;">📋</div>
        <div style="font-size: 1.1rem; font-weight: 700; color: #1B3A6B; margin-bottom: 8px;">Extracção Individual</div>
        <div style="font-size: 0.85rem; color: #475569;">Processar uma carta de alta e ver os resultados imediatamente</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir →", key="btn_extracao", use_container_width=True):
        st.switch_page("pages/1_Extracao_Individual.py")

with col2:
    st.markdown("""
    <div style="
        background: #FFF7F0;
        border: 1.5px solid #EA580C;
        border-radius: 12px;
        padding: 28px 24px;
        text-align: center;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    ">
        <div style="font-size: 2.5rem; margin-bottom: 10px;">📊</div>
        <div style="font-size: 1.1rem; font-weight: 700; color: #9A3412; margin-bottom: 8px;">Dashboard Clínico</div>
        <div style="font-size: 0.85rem; color: #475569;">Estatísticas agregadas e indicadores de qualidade assistencial</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir →", key="btn_dashboard", use_container_width=True):
        st.switch_page("pages/2_Dashboard.py")

st.divider()
st.markdown("""
<div style="text-align: center; color: #94A3B8; font-size: 0.8rem; padding: 12px 0;">
    🔒 Todo o processamento é local — nenhum dado clínico sai da rede hospitalar
</div>
""", unsafe_allow_html=True)