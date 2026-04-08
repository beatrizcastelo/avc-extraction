import streamlit as st
from pathlib import Path
from main import run_pipeline
from styles import apply_theme
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Extracção Individual — AVC", page_icon="📋", layout="wide")
apply_theme()

st.title("📋 Extracção Individual")
st.caption("Processar uma nota clínica e visualizar os resultados")

# ── Carta de Alta ──────────────────────────────────────────────────────────
st.subheader("Carta de Alta *")
metodo = st.radio("Como quer introduzir?",
                  ["Upload de ficheiro", "Copiar e colar texto"],
                  horizontal=True, key="carta_metodo")

carta_text = ""
if metodo == "Upload de ficheiro":
    uploaded = st.file_uploader("Carregar carta (.txt)", type=["txt"], key="carta_upload")
    if uploaded:
        carta_text = uploaded.read().decode("utf-8")
        with st.expander("Ver carta"):
            st.text(carta_text)
else:
    carta_text = st.text_area("Cole o texto aqui", height=200,
                               placeholder="Cole aqui o texto da carta de alta...",
                               key="carta_texto")

# ── Documentos opcionais ───────────────────────────────────────────────────
with st.expander("Nota de Mortalidade 30 dias (opcional)"):
    metodo_mort = st.radio("Como quer introduzir?",
                           ["Upload de ficheiro", "Copiar e colar texto"],
                           horizontal=True, key="mort_metodo")
    mort_text = ""
    if metodo_mort == "Upload de ficheiro":
        f = st.file_uploader("Carregar nota (.txt)", type=["txt"], key="mort_upload")
        if f:
            mort_text = f.read().decode("utf-8")
    else:
        mort_text = st.text_area("Cole o texto aqui", height=150,
                                  placeholder="Cole aqui a nota de mortalidade...",
                                  key="mort_texto")

with st.expander("Nota de Consulta 3 meses (opcional)"):
    metodo_cons = st.radio("Como quer introduzir?",
                           ["Upload de ficheiro", "Copiar e colar texto"],
                           horizontal=True, key="cons_metodo")
    consulta_text = ""
    if metodo_cons == "Upload de ficheiro":
        f = st.file_uploader("Carregar nota (.txt)", type=["txt"], key="cons_upload")
        if f:
            consulta_text = f.read().decode("utf-8")
    else:
        consulta_text = st.text_area("Cole o texto aqui", height=150,
                                      placeholder="Cole aqui a nota de consulta...",
                                      key="cons_texto")

st.divider()

if not carta_text:
    st.info("Introduza a Carta de Alta para começar.")
else:
    if st.button("Executar Extracção", type="primary"):

        tmp_dir = Path("outputs") / "_tmp_case"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        tmp_carta    = tmp_dir / f"_carta_{int(__import__('time').time()*1000000)}.txt"
        tmp_mort     = tmp_dir / "_tmp_mortalidade.txt"
        tmp_consulta = tmp_dir / "_tmp_consulta.txt"

        tmp_carta.write_text(carta_text, encoding="utf-8")
        if mort_text:
            tmp_mort.write_text(mort_text, encoding="utf-8")
        elif tmp_mort.exists():
            tmp_mort.unlink()
        if consulta_text:
            tmp_consulta.write_text(consulta_text, encoding="utf-8")
        elif tmp_consulta.exists():
            tmp_consulta.unlink()

        with st.spinner("A processar... (pode demorar 1-2 min)"):
            result = run_pipeline(tmp_carta, verbose=False)

        for f in tmp_dir.glob("*.txt"):
            f.unlink()

        if result["status"] == "error":
            st.error(f"Erro: {result['detail']}")
            st.stop()

        st.success(f"Concluído em {result['duration_seconds']}s  |  Modelo: `{result['model']}`")

        ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⚪"}
        TIMESTAMP_LABELS = {
            "onset_uvb":        "Início dos Sintomas / UVB",
            "admission":        "Admissão Hospitalar",
            "imaging_ct":       "TC-CE",
            "thrombolysis":     "Fibrinólise",
            "femoral_puncture": "Punção Femoral",
            "recanalization":   "Recanalização",
            "door1_admission":  "Admissão Hospital Origem",
            "door1_departure":  "Saída Hospital Origem",
            "door2":            "Chegada Hospital Final",
        }

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Timestamps")
            found = False
            for campo, val in result["timestamps"].items():
                if isinstance(val, dict) and val.get("value") not in (None, "null", "NA"):
                    found = True
                    lbl = TIMESTAMP_LABELS.get(campo, campo)
                    with st.expander(f"{lbl} — {val.get('date') or ''} {val['value']}"):
                        exc = val.get("excerpt", "")
                        if exc and exc != "null":
                            st.markdown(f"> *\"{exc}\"*")
                        else:
                            st.caption("Sem excerto disponível")
            if not found:
                st.caption("Nenhum timestamp extraído.")

            st.divider()

            st.subheader("Escalas Clínicas")
            carta_scales = result.get("scales", {}).get("carta", {})
            nihss = carta_scales.get("nihss", {})
            mrs   = carta_scales.get("mrs", {})
            escalas = {
                "NIHSS Admissão": nihss.get("nihss_admissao", {}),
                "NIHSS Alta":     nihss.get("nihss_alta", {}),
                "mRS Prévio":     mrs.get("mrs_previo", {}),
                "mRS Alta":       mrs.get("mrs_alta", {}),
                "mRS 3 Meses":    mrs.get("mrs_3meses", {}),
            }
            found = False
            for lbl, entry in escalas.items():
                v = entry.get("value") if isinstance(entry, dict) else entry
                if v is not None:
                    found = True
                    exc = entry.get("excerpt") if isinstance(entry, dict) else None
                    with st.expander(f"{lbl}: {v}"):
                        if exc and str(exc).lower() not in {"null", "none"}:
                            st.markdown(f"> *\"{exc}\"*")
                        else:
                            st.caption("Sem excerto disponível")
            if not found:
                st.caption("Nenhuma escala extraída.")

            consulta_scales = result.get("scales", {}).get("consulta", {})
            if consulta_scales:
                st.markdown("**Consulta de Seguimento**")
                nihss_c = consulta_scales.get("nihss", {})
                mrs_c   = consulta_scales.get("mrs", {})
                escalas_c = {
                    "NIHSS Admissão": nihss_c.get("nihss_admissao", {}),
                    "NIHSS Alta":     nihss_c.get("nihss_alta", {}),
                    "mRS Prévio":     mrs_c.get("mrs_previo", {}),
                    "mRS Alta":       mrs_c.get("mrs_alta", {}),
                    "mRS 3 Meses":    mrs_c.get("mrs_3meses", {}),
                }
                for lbl, entry in escalas_c.items():
                    v = entry.get("value") if isinstance(entry, dict) else entry
                    if v is not None:
                        exc = entry.get("excerpt") if isinstance(entry, dict) else None
                        with st.expander(f"{lbl}: {v}"):
                            if exc and str(exc).lower() not in {"null", "none"}:
                                st.markdown(f"> *\"{exc}\"*")
                            else:
                                st.caption("Sem excerto disponível")

        with col2:
            st.subheader("Métricas Temporais")
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
                st.caption("Sem métricas calculáveis.")

            st.divider()

            st.subheader("Variáveis Categóricas")
            cat  = result.get("categorical", {})
            mort = result.get("mortality", {})
            CAT_LABELS = {
                "tipo":            "Tipo de Episódio",
                "etiologia_toast": "Etiologia TOAST",
                "tratamento":      "Tratamento",
                "territorio":      "Território Vascular",
                "complicacoes":    "Complicações",
            }
            found = False
            for key, lbl in CAT_LABELS.items():
                v = cat.get(key)
                if v is not None:
                    found = True
                    st.markdown(f"**{lbl}:** {v}")
            if not found:
                st.caption("Nenhuma variável categórica extraída.")

            st.divider()

            st.subheader("Seguimento / Mortalidade")
            vivo = mort.get("vivo_30_dias")
            if vivo is True:
                st.markdown("**Vivo aos 30 dias:** ✅ Sim")
            elif vivo is False:
                st.markdown("**Vivo aos 30 dias:** ❌ Não")
                dias  = mort.get("dias_obito")
                causa = mort.get("causa_obito")
                if dias is not None:
                    st.markdown(f"**Dias até óbito:** {dias}")
                if causa:
                    st.markdown(f"**Causa de óbito:** {causa}")
            else:
                st.caption("Nota de mortalidade não introduzida." if not mort_text
                           else "Informação de mortalidade não encontrada.")

        st.divider()
        with st.expander("JSON completo"):
            st.json(result)