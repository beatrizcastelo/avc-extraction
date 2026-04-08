CLINICAL_CSS = """
<style>
    /* Sidebar azul escuro */
    [data-testid="stSidebar"] {
        background-color: #1B3A6B;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] a {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] code {
        color: #93C5FD !important;
        background: rgba(255,255,255,0.1) !important;
    }

    /* Métricas */
    [data-testid="stMetric"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px;
    }

    /* Expanders */
    [data-testid="stExpander"] {
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
    }

    /* Botão primário */
    .stButton > button[kind="primary"] {
        background-color: #1B3A6B !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #2D5A9E !important;
    }
</style>
"""


def apply_theme():
    import streamlit as st
    st.markdown(CLINICAL_CSS, unsafe_allow_html=True)