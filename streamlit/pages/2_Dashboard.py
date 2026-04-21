"""
2_Dashboard.py — Dashboard Clínico AVC
Compatível com: tema claro, psycopg2 directo, pandas ≥ 2.0
Requer: plotly (adicionar ao requirements.txt)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database import get_connection, init_db
from styles import apply_theme

st.set_page_config(
    page_title="Dashboard Clínico — AVC",
    page_icon="📊",
    layout="wide",
)
apply_theme()

# ── Paleta — tema claro, azul #1B3A6B como primário ──────────────────────
PRIMARY  = "#1B3A6B"
PRIMARY_L= "#2D5A9E"
BG_CARD  = "#F8FAFC"
BORDER   = "#E2E8F0"
TEXT_MAIN= "#1E293B"
TEXT_SUB = "#64748B"

C_GREEN  = "#16a34a"
C_YELLOW = "#ca8a04"
C_RED    = "#dc2626"

MRS_COLORS   = ["#16a34a", "#86efac", "#ca8a04", "#f97316", "#dc2626", "#7f1d1d"]
TOAST_COLORS = [PRIMARY, PRIMARY_L, "#0891b2", "#f97316", "#6b7280"]
TIPO_COLORS  = [PRIMARY, PRIMARY_L, "#0369a1", "#0891b2", "#14b8a6",
                "#16a34a", "#ca8a04", "#dc2626"]

PLOTLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT_MAIN, size=12),
    margin=dict(l=10, r=10, t=30, b=10),
)

TIPO_LABELS = {
    "fibrinolise_pre_hospitalar":     "Fibrinólise Pré-hosp.",
    "fibrinolise_pre_hospitalar_ace": "Fibrinólise Pré-hosp. (ACE)",
    "bridging":                       "Bridging",
    "tev_isolada_contraindicacao":    "TEV (contraindicação)",
    "tev_isolada_fora_janela":        "TEV (fora janela)",
    "fibrinolise_intra_hospitalar":   "Fibrinólise Intra-hosp.",
    "conservador_lacunar":            "Conservador Lacunar",
    "conservador_wake_up":            "Conservador Wake-up",
}

# ── CSS extra (tema claro) ────────────────────────────────────────────────
st.markdown(f"""
<style>
.kpi-card {{
    background:{BG_CARD}; border:1.5px solid {BORDER};
    border-radius:10px; padding:20px 22px;
}}
.kpi-label {{
    font-size:0.75rem; color:{TEXT_SUB};
    text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px;
}}
.kpi-value {{ font-size:2rem; font-weight:700; color:{TEXT_MAIN}; line-height:1.1; }}
.kpi-sub   {{ font-size:0.8rem; color:{TEXT_SUB}; margin-top:4px; }}
.kpi-badge {{
    font-size:0.72rem; font-weight:600; padding:2px 8px;
    border-radius:20px; display:inline-block; margin-top:8px;
}}
.badge-green  {{ background:#dcfce7; color:#15803d; }}
.badge-blue   {{ background:#dbeafe; color:#1d4ed8; }}
.badge-orange {{ background:#ffedd5; color:#c2410c; }}
.badge-red    {{ background:#fee2e2; color:#b91c1c; }}
.section-title {{ font-size:0.95rem; font-weight:600; color:{TEXT_MAIN}; margin-bottom:10px; }}
</style>
""", unsafe_allow_html=True)


# ── Carregar dados (psycopg2 directo — sem pd.read_sql) ───────────────────
@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    init_db()
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM episodios ORDER BY id DESC")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return pd.DataFrame(rows, columns=cols)


df_all = load_data()

if df_all.empty:
    st.info("Ainda não existem episódios na base de dados. "
            "Processa cartas de alta na página de Extracção ou em batch.")
    st.stop()

# ── Sidebar — Filtros ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔽 Filtros Avançados")
    st.divider()

    etiologias    = ["Todas"] + sorted(df_all["etiologia_toast"].dropna().unique().tolist())
    etiologia_sel = st.selectbox("Etiologia TOAST", etiologias)

    st.markdown("**Tipo de tratamento**")
    filtro_fib = st.checkbox("Fibrinólise IV")
    filtro_tev = st.checkbox("Trombectomia")

    nihss_vals = df_all["nihss_admissao"].dropna()
    if not nihss_vals.empty:
        nihss_range = st.slider(
            "NIHSS Admissão",
            min_value=int(nihss_vals.min()),
            max_value=int(nihss_vals.max()),
            value=(int(nihss_vals.min()), int(nihss_vals.max())),
        )
    else:
        nihss_range = (0, 42)

    st.button("Aplicar Filtros", use_container_width=True, type="primary")

    st.divider()
    st.markdown("### 📊 Qualidade dos Dados")
    total_all = len(df_all)
    completos = df_all[["nihss_admissao", "door_to_needle", "mrs_alta"]].notna().all(axis=1).sum()
    pct_comp  = round(completos / total_all * 100) if total_all > 0 else 0
    st.progress(pct_comp / 100, text=f"Dados completos: {pct_comp}%")
    st.markdown(f"✅ {completos} episódios com campos completos")
    st.markdown(f"⚠️ {total_all - completos} com campos em falta")

# ── Aplicar filtros ───────────────────────────────────────────────────────
df = df_all.copy()
if etiologia_sel != "Todas":
    df = df[df["etiologia_toast"] == etiologia_sel]
if filtro_fib:
    df = df[df["tipo"].str.contains("fibrinolise", na=False)]
if filtro_tev:
    df = df[df["tipo"].str.contains("tev|bridging", na=False)]
df = df[df["nihss_admissao"].isna() |
        df["nihss_admissao"].between(nihss_range[0], nihss_range[1])]

# ── Cabeçalho ─────────────────────────────────────────────────────────────
st.title("📊 Dashboard Clínico — AVC Isquémico")
st.caption(f"Estatísticas agregadas dos episódios processados · {len(df)} episódio(s) filtrado(s)")
st.divider()

# ── KPI cards ─────────────────────────────────────────────────────────────
total    = len(df)
n_fib    = df["tipo"].str.contains("fibrinolise", na=False).sum()
pct_fib  = round(n_fib / total * 100, 1) if total > 0 else 0
n_tev    = df["tipo"].str.contains("tev|bridging", na=False).sum()
pct_tev  = round(n_tev / total * 100, 1) if total > 0 else 0
mort_df  = df[df["vivo_30_dias"].notna()]
n_obitos = int((mort_df["vivo_30_dias"] == False).sum())
pct_mort = round(n_obitos / len(mort_df) * 100, 1) if len(mort_df) > 0 else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Episódios</div>
        <div class="kpi-value">{total}</div>
        <div class="kpi-sub">Episódios AVC Isquémico</div>
        <span class="kpi-badge badge-blue">Total</span>
    </div>""", unsafe_allow_html=True)

with c2:
    b = "badge-green" if pct_fib >= 30 else "badge-orange"
    a = "✓ Dentro do alvo" if pct_fib >= 30 else "↑ Abaixo do alvo"
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Fibrinólise</div>
        <div class="kpi-value">{n_fib}</div>
        <div class="kpi-sub">{pct_fib}% com Fibrinólise IV</div>
        <span class="kpi-badge {b}">{a}</span>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Trombectomia</div>
        <div class="kpi-value">{n_tev}</div>
        <div class="kpi-sub">{pct_tev}% com Trombectomia</div>
        <span class="kpi-badge badge-blue">Endovascular</span>
    </div>""", unsafe_allow_html=True)

with c4:
    bm = "badge-green" if pct_mort < 10 else "badge-red"
    am = "✓ Favorável" if pct_mort < 10 else "↑ Elevada"
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Mortalidade 30d</div>
        <div class="kpi-value">{n_obitos}</div>
        <div class="kpi-sub">{pct_mort}% Mortalidade</div>
        <span class="kpi-badge {bm}">{am}</span>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Métricas Temporais + mRS 3 meses ──────────────────────────────────────
col_left, col_right = st.columns([3, 2])

with col_left:
    # Filtro por tipo de episódio
    tipos_disponiveis = ["Todos"] + sorted(
        [TIPO_LABELS.get(t, t) for t in df["tipo"].dropna().unique()]
    )
    tipo_metrica = st.selectbox("Tipo de episódio", tipos_disponiveis,
                                key="sel_tipo_metrica")

    # Aplica filtro ao dataframe de métricas
    tipo_inv = {v: k for k, v in TIPO_LABELS.items()}
    if tipo_metrica != "Todos":
        tipo_key = tipo_inv.get(tipo_metrica, tipo_metrica)
        df_metrica = df[df["tipo"] == tipo_key]
    else:
        df_metrica = df

    st.markdown('<div class="section-title">Métricas Temporais Médias (minutos)</div>',
                unsafe_allow_html=True)

    METRIC_CONFIG = [
        ("door_to_imaging",  "Door-to-Imaging",  25,  45),
        ("door_to_needle",   "Door-to-Needle",   60,  90),
        ("door_to_puncture", "Door-to-Puncture", 90, 120),
        ("onset_to_recan",   "Onset-to-Recan",  270, 360),
    ]
    metrics_data = []
    for key, label, t_green, t_yellow in METRIC_CONFIG:
        vals = df_metrica[key].dropna()
        if len(vals) > 0:
            media = round(float(vals.mean()), 1)
            color = C_GREEN if media <= t_green else (C_YELLOW if media <= t_yellow else C_RED)
            metrics_data.append((label, media, color, t_green, t_yellow, f"alvo ≤{t_green}min"))

    if metrics_data:
        fig = go.Figure()

        # Barras
        fig.add_trace(go.Bar(
            y=[m[0] for m in metrics_data],
            x=[m[1] for m in metrics_data],
            orientation="h",
            marker_color=[m[2] for m in metrics_data],
            marker_line_width=0,
            text=[f"{m[1]} min" for m in metrics_data],
            textposition="outside",
            textfont=dict(color=TEXT_MAIN, size=12),
            hovertemplate="%{y}: <b>%{x} min</b><extra></extra>",
        ))

        # Marcadores de target individuais por métrica
        for i, (label, media, color, t_green, t_yellow, _) in enumerate(metrics_data):
            fig.add_shape(
                type="line",
                x0=t_green, x1=t_green,
                y0=i - 0.4, y1=i + 0.4,
                line=dict(color="rgba(30,30,30,0.5)", width=2, dash="dot"),
            )

        max_val = max(max(m[1] for m in metrics_data),
                      max(m[3] for m in metrics_data)) * 1.35

        fig.update_layout(**PLOTLY_BASE, height=max(200, len(metrics_data) * 70),
            xaxis=dict(showgrid=True, gridcolor=BORDER,
                       range=[0, max_val],
                       tickfont=dict(color=TEXT_SUB)),
            yaxis=dict(tickfont=dict(color=TEXT_MAIN, size=12)),
            showlegend=False, bargap=0.35)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        l1, l2, l3 = st.columns(3)
        l1.markdown("🟢 Dentro do alvo")
        l2.markdown("🟡 Próximo do limite")
        l3.markdown("🔴 Acima do recomendado")
    else:
        st.caption("Sem métricas temporais disponíveis para este tipo de episódio.")

with col_right:
    st.markdown('<div class="section-title">Distribuição mRS aos 3 meses</div>',
                unsafe_allow_html=True)
    mrs_vals = df["mrs_3meses"].dropna()
    if not mrs_vals.empty:
        mrs_map = {0:"mRS 0-1",1:"mRS 0-1",2:"mRS 2",
                   3:"mRS 3",4:"mRS 4",5:"mRS 5",6:"mRS 6 (Óbito)"}
        grouped = {}
        for val, cnt in mrs_vals.value_counts().sort_index().items():
            lbl = mrs_map.get(int(val), f"mRS {int(val)}")
            grouped[lbl] = grouped.get(lbl, 0) + cnt
        fig_d = go.Figure(go.Pie(
            labels=list(grouped.keys()), values=list(grouped.values()),
            hole=0.55, marker_colors=MRS_COLORS[:len(grouped)],
            textinfo="percent", textfont=dict(size=12, color="white"),
            hovertemplate="%{label}: <b>%{value}</b> casos (%{percent})<extra></extra>",
        ))
        fig_d.update_layout(**PLOTLY_BASE, height=260,
            legend=dict(font=dict(size=11, color=TEXT_SUB),
                        orientation="h", x=0, y=-0.18),
            annotations=[dict(text=f"<b>{sum(grouped.values())}</b><br>casos",
                              x=0.5, y=0.5, font_size=13,
                              font_color=TEXT_MAIN, showarrow=False)])
        st.plotly_chart(fig_d, use_container_width=True, config={"displayModeBar": False})
        st.caption("mRS 0-2: Resultado funcional favorável")
    else:
        st.caption("Sem dados de mRS 3 meses.")

st.divider()

# ── NIHSS + TOAST ──────────────────────────────────────────────────────────
col3, col4 = st.columns(2)

with col3:
    st.markdown('<div class="section-title">Distribuição NIHSS Admissão</div>',
                unsafe_allow_html=True)
    nihss_data = df["nihss_admissao"].dropna()
    if not nihss_data.empty:
        bl = ["Minor (0-4)", "Moderado (5-15)", "Mod-Grave (16-20)", "Grave (21+)"]
        bc = [C_GREEN, C_YELLOW, C_RED, "#7f1d1d"]
        counts = pd.cut(nihss_data, bins=[0,5,16,21,43],
                        labels=bl, right=False).value_counts().reindex(bl, fill_value=0)
        fig_n = go.Figure(go.Bar(
            x=bl, y=[counts[l] for l in bl],
            marker_color=bc, marker_line_width=0,
            text=[counts[l] for l in bl], textposition="outside",
            textfont=dict(color=TEXT_MAIN),
            hovertemplate="%{x}: <b>%{y}</b> casos<extra></extra>",
        ))
        fig_n.update_layout(**PLOTLY_BASE, height=240,
            xaxis=dict(tickfont=dict(color=TEXT_MAIN, size=11)),
            yaxis=dict(showgrid=True, gridcolor=BORDER, tickfont=dict(color=TEXT_SUB)),
            showlegend=False,
            annotations=[dict(text=f"Média: {round(float(nihss_data.mean()),1)}",
                              xref="paper", yref="paper", x=0.98, y=0.98,
                              font=dict(size=11, color=TEXT_SUB), showarrow=False,
                              bgcolor=BG_CARD, borderpad=4,
                              bordercolor=BORDER, borderwidth=1)])
        st.plotly_chart(fig_n, use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("Sem dados de NIHSS.")

with col4:
    st.markdown('<div class="section-title">Classificação TOAST</div>',
                unsafe_allow_html=True)
    toast_data = df["etiologia_toast"].dropna().value_counts()
    if not toast_data.empty:
        fig_t = go.Figure(go.Pie(
            labels=toast_data.index.tolist(), values=toast_data.values.tolist(),
            hole=0.5, marker_colors=TOAST_COLORS[:len(toast_data)],
            textinfo="percent", textfont=dict(size=12, color="white"),
            hovertemplate="%{label}: <b>%{value}</b> casos (%{percent})<extra></extra>",
        ))
        fig_t.update_layout(**PLOTLY_BASE, height=260,
            legend=dict(font=dict(size=10, color=TEXT_SUB),
                        orientation="h", x=0, y=-0.2))
        st.plotly_chart(fig_t, use_container_width=True, config={"displayModeBar": False})
        st.caption("Classificação etiológica do AVC isquémico")
    else:
        st.caption("Sem dados de etiologia TOAST.")

st.divider()

# ── Tipo de Episódio ───────────────────────────────────────────────────────
st.markdown('<div class="section-title">Distribuição por Tipo de Episódio</div>',
            unsafe_allow_html=True)
tipo_data = df["tipo"].dropna().value_counts()
if not tipo_data.empty:
    tlabels = [TIPO_LABELS.get(k, k) for k in tipo_data.index]
    fig_tp  = go.Figure(go.Bar(
        x=tlabels, y=tipo_data.values,
        marker_color=TIPO_COLORS[:len(tipo_data)], marker_line_width=0,
        text=tipo_data.values, textposition="outside",
        textfont=dict(color=TEXT_MAIN),
        hovertemplate="%{x}: <b>%{y}</b> casos<extra></extra>",
    ))
    fig_tp.update_layout(**PLOTLY_BASE, height=220,
        xaxis=dict(tickfont=dict(color=TEXT_MAIN, size=11)),
        yaxis=dict(showgrid=True, gridcolor=BORDER, tickfont=dict(color=TEXT_SUB)),
        showlegend=False)
    st.plotly_chart(fig_tp, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── KPIs ESO ──────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Indicadores de Qualidade ESO</div>',
            unsafe_allow_html=True)
st.caption("KPIs 7a · 7b · 7c · 7d · 13a — European Stroke Organisation Action Plan")

n_total = len(df)

# KPI 7a — Taxa IVT (target ≥ 15%)
n_ivt   = df["tipo"].str.contains("fibrinolise", na=False).sum()
pct_ivt = round(n_ivt / n_total * 100, 1) if n_total > 0 else 0
ok_7a   = pct_ivt >= 15

# KPI 7b — Taxa MT (target ≥ 10%)
n_mt    = df["tipo"].str.contains("tev|bridging", na=False).sum()
pct_mt  = round(n_mt / n_total * 100, 1) if n_total > 0 else 0
ok_7b   = pct_mt >= 10

# KPI 7c — DTN ≤ 60 min (target ≥ 80% dos doentes com IVT)
dtn_data = df["door_to_needle"].dropna()
if not dtn_data.empty:
    n_dtn      = len(dtn_data)
    dtn_ok     = int((dtn_data <= 60).sum())
    pct_dtn_ok = round(dtn_ok / n_dtn * 100)
    ok_7c      = pct_dtn_ok >= 80
else:
    n_dtn = dtn_ok = pct_dtn_ok = 0
    ok_7c = False

# KPI 7d — Door-to-Groin ≤ 90 min (target ≥ 50% dos doentes com MT)
dtp_data = df["door_to_puncture"].dropna()
if not dtp_data.empty:
    n_dtp      = len(dtp_data)
    dtp_ok     = int((dtp_data <= 90).sum())
    pct_dtp_ok = round(dtp_ok / n_dtp * 100)
    ok_7d      = pct_dtp_ok >= 50
else:
    n_dtp = dtp_ok = pct_dtp_ok = 0
    ok_7d = False

# KPI 13a — Mortalidade AVC isquémico (monitorização)
mort_df  = df[df["vivo_30_dias"].notna()]
n_mort   = len(mort_df)
n_ob     = int((mort_df["vivo_30_dias"] == False).sum()) if n_mort > 0 else 0
pct_mort_kpi = round(n_ob / n_mort * 100, 1) if n_mort > 0 else 0

def kpi_card(kpi, titulo, valor, target_txt, atingido, nota=""):
    cor   = "badge-green" if atingido else "badge-red"
    badge = "✓ Target atingido" if atingido else "✗ Abaixo do target"
    return f"""<div class="kpi-card">
        <div class="kpi-label">KPI {kpi} — {titulo}</div>
        <div class="kpi-value">{valor}</div>
        <div class="kpi-sub">{target_txt}{(' · ' + nota) if nota else ''}</div>
        <span class="kpi-badge {cor}">{badge}</span>
    </div>"""

k1, k2, k3 = st.columns(3)
with k1:
    st.markdown(kpi_card("7a", "Taxa IVT",
                f"{pct_ivt}%",
                f"Target ≥ 15% · {n_ivt}/{n_total} doentes",
                ok_7a), unsafe_allow_html=True)
with k2:
    st.markdown(kpi_card("7b", "Taxa MT",
                f"{pct_mt}%",
                f"Target ≥ 10% · {n_mt}/{n_total} doentes",
                ok_7b), unsafe_allow_html=True)
with k3:
    if n_mort > 0:
        st.markdown(kpi_card("13a", "Mortalidade 30d",
                    f"{pct_mort_kpi}%",
                    f"Monitorização · {n_ob}/{n_mort} doentes com seguimento",
                    pct_mort_kpi < 15), unsafe_allow_html=True)
    else:
        st.markdown(kpi_card("13a", "Mortalidade 30d",
                    "—", "Sem dados de seguimento", False), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

k4, k5 = st.columns(2)
with k4:
    if n_dtn > 0:
        st.markdown(kpi_card("7c", "Door-to-Needle ≤ 60 min",
                    f"{pct_dtn_ok}%",
                    f"Target ≥ 80% · {dtn_ok}/{n_dtn} casos dentro do alvo",
                    ok_7c,
                    f"Média DTN: {round(float(dtn_data.mean()),1)} min"), unsafe_allow_html=True)
        st.progress(dtn_ok / n_dtn,
                    text=f"{pct_dtn_ok}% dentro do target ESO (≤ 60 min)")
    else:
        st.caption("KPI 7c — Sem casos com DTN calculado.")

with k5:
    if n_dtp > 0:
        st.markdown(kpi_card("7d", "Door-to-Groin ≤ 90 min",
                    f"{pct_dtp_ok}%",
                    f"Target ≥ 50% · {dtp_ok}/{n_dtp} casos dentro do alvo",
                    ok_7d,
                    f"Média DTP: {round(float(dtp_data.mean()),1)} min"), unsafe_allow_html=True)
        st.progress(dtp_ok / n_dtp,
                    text=f"{pct_dtp_ok}% dentro do target ESO (≤ 90 min)")
    else:
        st.caption("KPI 7d — Sem casos com Door-to-Groin calculado.")

st.divider()

# ── Tabela + Export ───────────────────────────────────────────────────────
st.markdown('<div class="section-title">Episódios Processados</div>',
            unsafe_allow_html=True)

# Filtros da tabela
tf1, tf2, tf3 = st.columns([2, 2, 1])

with tf1:
    vista = st.selectbox("Mostrar",
                         ["Últimos 20", "Últimos 50", "Todos"],
                         key="tabela_vista")
with tf2:
    tipos_tabela = ["Todos os tipos"] + sorted(
        [TIPO_LABELS.get(t, t) for t in df["tipo"].dropna().unique()]
    )
    tipo_tabela = st.selectbox("Tipo de episódio", tipos_tabela, key="tabela_tipo")

# Aplicar filtros da tabela
df_tabela = df.copy()

tipo_inv = {v: k for k, v in TIPO_LABELS.items()}
if tipo_tabela != "Todos os tipos":
    tipo_key = tipo_inv.get(tipo_tabela, tipo_tabela)
    df_tabela = df_tabela[df_tabela["tipo"] == tipo_key]

if vista == "Últimos 20":
    df_tabela = df_tabela.head(20)
elif vista == "Últimos 50":
    df_tabela = df_tabela.head(50)
# "Todos" não limita

if not df_tabela.empty:
    display = df_tabela[[
        "id", "source_file", "processed_at", "tipo",
        "etiologia_toast", "nihss_admissao",
        "door_to_needle", "mrs_alta", "vivo_30_dias"
    ]].copy()
    display["tipo"]         = display["tipo"].map(TIPO_LABELS).fillna(display["tipo"])
    display["vivo_30_dias"] = display["vivo_30_dias"].map(
        {True: "✅ Sim", False: "❌ Não"}).fillna("—")
    display["processed_at"] = pd.to_datetime(
        display["processed_at"]).dt.strftime("%d/%m/%Y %H:%M")
    display = display.rename(columns={
        "id": "ID", "source_file": "Ficheiro",
        "processed_at": "Processado em", "tipo": "Tipo",
        "etiologia_toast": "Etiologia", "nihss_admissao": "NIHSS Adm.",
        "door_to_needle": "DTN (min)", "mrs_alta": "mRS Alta",
        "vivo_30_dias": "Vivo 30d",
    })
    with tf3:
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            "⬇️ Exportar CSV",
            data=display.to_csv(index=False).encode("utf-8"),
            file_name="episodios_avc.csv", mime="text/csv",
            use_container_width=True,
        )
    st.caption(f"A mostrar {len(display)} episódio(s)")
    st.dataframe(display, use_container_width=True, hide_index=True)
else:
    st.caption("Sem episódios para mostrar.")

# ── Rodapé ────────────────────────────────────────────────────────────────
st.divider()
st.caption("🔒 Execução Local — Dados Anonimizados · AVC-Extraction · FCTUC / ULS Coimbra")