import os
import streamlit as st
from dotenv import load_dotenv
from styles import apply_theme

load_dotenv()

st.set_page_config(page_title="Parse", page_icon="🔍", layout="wide")
apply_theme()

_PARSE_URL = os.getenv("PARSE_URL", "").rstrip("/")

if not _PARSE_URL:
    st.error("Define PARSE_URL no .env")
    st.stop()

st.title("Parse Dashboard")
st.markdown("Clica para abrir o Parse Dashboard numa nova aba.")
st.link_button("Abrir Parse Dashboard ↗", _PARSE_URL)
