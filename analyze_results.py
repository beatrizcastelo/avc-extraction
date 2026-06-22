#!/usr/bin/env python3
"""
analyze_results.py
Agrega os CSVs de validação de validation_litellm/, calcula métricas completas
por modelo e gera tabelas LaTeX + gráficos para a tese.

Uso:
    python analyze_results.py
    python analyze_results.py --input validation_litellm/ --output figures/
"""

import argparse
import re
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")

# ── Configuração ───────────────────────────────────────────────────────────────

# Nome legível por modelo (para tabelas e gráficos)
MODEL_LABELS = {
    "Llama-3.2-1B-Instruct-bf16":          "Llama-3.2-1B",
    "Llama-3.2-3B-Instruct-bf16":          "Llama-3.2-3B",
    "Meta-Llama-3.1-8B-Instruct-bf16":     "Llama-3.1-8B",
    "Meta-Llama-3.1-8B-Instruct-8bit":     "Llama-3.1-8B-8bit",
    "Qwen2.5-0.5B-Instruct-bf16":          "Qwen2.5-0.5B",
    "Qwen2.5-1.5B-Instruct-bf16":          "Qwen2.5-1.5B",
    "Qwen2.5-3B-Instruct-bf16":            "Qwen2.5-3B",
    "Qwen2.5-7B-Instruct-bf16":            "Qwen2.5-7B",
    "Qwen2.5-7B-Instruct-8bit":            "Qwen2.5-7B-8bit",
    "gemma-3-1b-it-bf16":                  "Gemma-3-1B",
    "gemma-3-4b-it-bf16":                  "Gemma-3-4B",
    "Phi-3-mini-4k-instruct-8bit":         "Phi-3-mini",
    "Phi-3.5-mini-instruct-bf16":          "Phi-3.5-mini",
    "Phi-4-mini-instruct-4bit":            "Phi-4-mini",
    "Mistral-Nemo-Instruct-2407-bf16":     "Mistral-Nemo-12B",
    "DeepSeek-R1-Distill-Qwen-1.5B-bf16": "DS-R1-Qwen-1.5B",
    "DeepSeek-R1-Distill-Qwen-7B-bf16":   "DS-R1-Qwen-7B",
}

GROUP_LABELS = {
    "timestamp":   "Timestamps",
    "metric":      "Métricas temp.",
    "scale":       "Escalas clínicas",
    "categorical": "Categóricas",
    "binary":      "Binário",
    "numeric":     "Numérico",
}

# Ordem para Exp 1 — escadas de dimensão
EXP1_LLAMA   = ["Llama-3.2-1B", "Llama-3.2-3B", "Llama-3.1-8B"]
EXP1_QWEN    = ["Qwen2.5-0.5B", "Qwen2.5-1.5B", "Qwen2.5-3B", "Qwen2.5-7B"]
EXP1_GEMMA   = ["Gemma-3-1B", "Gemma-3-4B"]
EXP1_DS      = ["DS-R1-Qwen-1.5B", "DS-R1-Qwen-7B"]

# Exp 3 — ablação bf16 vs 8-bit
EXP3_PAIRS = [
    ("Qwen2.5-7B",    "Qwen2.5-7B-8bit"),
    ("Llama-3.1-8B",  "Llama-3.1-8B-8bit"),
]

PALETTE = sns.color_palette("tab10")


# ── Leitura dos CSVs ───────────────────────────────────────────────────────────

def load_latest_csvs(folder: Path) -> pd.DataFrame:
    """Lê o CSV mais recente por modelo e devolve um DataFrame combinado."""
    csvs = sorted(folder.glob("*.csv"))
    latest: dict[str, Path] = {}
    for f in csvs:
        m = re.search(r"validation_tiago_(.+?)_\d+casos_([\d_]+)\.csv", f.name)
        if not m:
            continue
        model_raw, ts = m.group(1), m.group(2)
        if model_raw not in latest or ts > latest[model_raw][1]:
            latest[model_raw] = (f, ts)

    frames = []
    for model_raw, (path, _) in sorted(latest.items()):
        label = MODEL_LABELS.get(model_raw, model_raw)
        df = pd.read_csv(path)
        df["model_raw"] = model_raw
        df["model"]     = label
        frames.append(df)
        print(f"  ✅  {label:<30} ({path.name})")

    return pd.concat(frames, ignore_index=True)


# ── Agregação ──────────────────────────────────────────────────────────────────

def summary_by_group(df: pd.DataFrame) -> pd.DataFrame:
    """F1 médio, Prec, Rec e MAE por modelo e grupo de variável.

    NaN F1/Prec/Rec (modelo nunca produziu previsão) conta como 0.
    MAE continua a excluir NaN — NaN em MAE significa variável não-temporal.
    """
    rows = []
    for (model, group), g in df.groupby(["model", "group"]):
        mae_vals = g["MAE"].dropna()
        rows.append({
            "model":   model,
            "group":   group,
            "F1":      round(g["F1"].fillna(0).mean(),        4),
            "Prec":    round(g["precision"].fillna(0).mean(),  4),
            "Rec":     round(g["recall"].fillna(0).mean(),     4),
            "MAE":     round(mae_vals.mean(), 2) if len(mae_vals) > 0 else float("nan"),
            "TP": int(g["TP"].sum()), "FP": int(g["FP"].sum()),
            "FN": int(g["FN"].sum()), "TN": int(g["TN"].sum()),
        })
    return pd.DataFrame(rows)


def summary_overall(df: pd.DataFrame) -> pd.DataFrame:
    """F1 médio global por modelo (macro-média de todas as variáveis).

    NaN F1 (modelo nunca produziu previsão para aquela variável) conta como 0.
    Excluir NaN inflacionaria artificialmente modelos que só extraem algumas variáveis.
    """
    rows = []
    for model, g in df.groupby("model"):
        f1_vals  = g["F1"].fillna(0)
        pr_vals  = g["precision"].fillna(0)
        rc_vals  = g["recall"].fillna(0)
        rows.append({
            "model":     model,
            "F1_mean":   round(f1_vals.mean(),  4),
            "Prec_mean": round(pr_vals.mean(),   4),
            "Rec_mean":  round(rc_vals.mean(),   4),
            "n_nan_f1":  int(g["F1"].isna().sum()),
        })
    return pd.DataFrame(rows).sort_values("F1_mean", ascending=False)


# ── Tabelas LaTeX ──────────────────────────────────────────────────────────────

def pivot_f1(summary: pd.DataFrame) -> pd.DataFrame:
    """Pivot: linhas = modelos, colunas = grupos, valores = F1."""
    p = summary.pivot(index="model", columns="group", values="F1")
    # reordenar colunas
    col_order = [c for c in ["timestamp","metric","scale","categorical","binary","numeric"] if c in p.columns]
    p = p[col_order]
    p.columns = [GROUP_LABELS.get(c, c) for c in p.columns]
    return p


def to_latex_table(pivot: pd.DataFrame, caption: str, label: str) -> str:
    n_cols = len(pivot.columns)
    col_spec = "l" + "r" * n_cols
    lines = [
        r"\begin{table}[htbp]",
        r"\centering", r"\small",
        r"\begin{tabular}{" + col_spec + "}",
        r"\toprule",
        "Modelo & " + " & ".join(pivot.columns) + r" \\",
        r"\midrule",
    ]
    for model, row in pivot.iterrows():
        vals = []
        for v in row:
            if pd.isna(v):
                vals.append("---")
            else:
                vals.append(f"{v:.3f}")
        lines.append(f"{model} & " + " & ".join(vals) + r" \\")
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\end{table}",
    ]
    return "\n".join(lines)


# ── Gráficos ───────────────────────────────────────────────────────────────────

def plot_heatmap(pivot: pd.DataFrame, out: Path):
    """Heatmap F1 — todos os modelos × grupos de variável."""
    data = pivot.astype(float).fillna(0.0)
    fig, ax = plt.subplots(figsize=(10, max(6, len(pivot) * 0.45)))
    sns.heatmap(
        data, annot=False,
        cmap="RdYlGn", vmin=0, vmax=1,
        linewidths=0.5, ax=ax, cbar_kws={"label": "F1-score"}
    )
    ax.set_title("F1-score por modelo e categoria de variável", fontsize=13, pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_size_ladders(df: pd.DataFrame, out: Path):
    """Exp 1 — F1 médio global vs tamanho, uma linha por família."""
    overall = summary_overall(df).set_index("model")["F1_mean"]

    families = {
        "Llama":       (EXP1_LLAMA,  [1, 3, 8]),
        "Qwen2.5":     (EXP1_QWEN,   [0.5, 1.5, 3, 7]),
        "Gemma-3":     (EXP1_GEMMA,  [1, 4]),
        "DeepSeek-R1": (EXP1_DS,     [1.5, 7]),
    }

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (fam, (models, sizes)) in enumerate(families.items()):
        f1s = [overall.get(m, np.nan) for m in models]
        ax.plot(sizes, f1s, marker="o", label=fam, color=PALETTE[i], linewidth=2, markersize=7)
        for s, f, m in zip(sizes, f1s, models):
            if not np.isnan(f):
                ax.annotate(f"{f:.3f}", (s, f), textcoords="offset points",
                            xytext=(4, 5), fontsize=8)

    ax.set_xlabel("Parâmetros (B)", fontsize=11)
    ax.set_ylabel("F1 médio global", fontsize=11)
    ax.set_title("Exp 1 — Efeito da dimensão do modelo (bf16)", fontsize=12)
    ax.legend(fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.4)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_family_bars(summary: pd.DataFrame, out: Path):
    """Exp 2 — Barras agrupadas: F1 por categoria, uma barra por modelo."""
    groups = ["Timestamps", "Métricas temp.", "Escalas clínicas", "Categóricas"]
    pivot  = pivot_f1(summary)
    pivot  = pivot[[c for c in groups if c in pivot.columns]]

    # modelos de interesse para Exp 2 (~7-12B, um por família)
    exp2_models = [
        "Llama-3.1-8B", "Qwen2.5-7B", "Gemma-3-4B",
        "Phi-3.5-mini", "Mistral-Nemo-12B",
        "DS-R1-Qwen-7B",
    ]
    pivot = pivot.loc[[m for m in exp2_models if m in pivot.index]]

    x    = np.arange(len(pivot.columns))
    w    = 0.12
    n    = len(pivot)

    fig, ax = plt.subplots(figsize=(11, 5))
    for i, (model, row) in enumerate(pivot.iterrows()):
        vals = [row.get(g, np.nan) for g in pivot.columns]
        offset = (i - n/2 + 0.5) * w
        bars = ax.bar(x + offset, vals, w, label=model, color=PALETTE[i % 10])
        for bar, v in zip(bars, vals):
            if not np.isnan(v):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                        f"{v:.2f}", ha="center", va="bottom", fontsize=6.5)

    ax.set_xticks(x)
    ax.set_xticklabels(pivot.columns, fontsize=10)
    ax.set_ylabel("F1-score", fontsize=11)
    ax.set_title("Exp 2 — Efeito da família/receita de treino (~7-12B, bf16)", fontsize=12)
    ax.legend(fontsize=8, loc="lower right")
    ax.set_ylim(0, 1.15)
    ax.grid(axis="y", alpha=0.4)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_ablation(summary: pd.DataFrame, out: Path):
    """Exp 3 — Ablação bf16 vs 8-bit por grupo de variável."""
    groups = ["Timestamps", "Métricas temp.", "Escalas clínicas", "Categóricas"]
    pivot  = pivot_f1(summary)
    pivot  = pivot[[c for c in groups if c in pivot.columns]]

    fig, axes = plt.subplots(1, len(EXP3_PAIRS), figsize=(11, 5), sharey=True)
    for ax, (bf16_m, bit8_m) in zip(axes, EXP3_PAIRS):
        if bf16_m not in pivot.index or bit8_m not in pivot.index:
            ax.set_visible(False)
            continue
        x    = np.arange(len(groups))
        vals_bf16 = [pivot.loc[bf16_m, g] if g in pivot.columns else np.nan for g in groups]
        vals_8bit = [pivot.loc[bit8_m, g] if g in pivot.columns else np.nan for g in groups]
        ax.bar(x - 0.2, vals_bf16, 0.35, label="bf16", color=PALETTE[0], alpha=0.85)
        ax.bar(x + 0.2, vals_8bit, 0.35, label="8-bit", color=PALETTE[1], alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(groups, fontsize=9, rotation=15, ha="right")
        ax.set_title(bf16_m, fontsize=11)
        ax.set_ylim(0, 1.1)
        ax.legend(fontsize=9)
        ax.grid(axis="y", alpha=0.4)

    fig.suptitle("Exp 3 — Ablação de quantização: bf16 vs 8-bit", fontsize=12, y=1.02)
    axes[0].set_ylabel("F1-score", fontsize=11)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_radar(summary: pd.DataFrame, out: Path):
    """Radar chart — F1 por categoria para cada modelo."""
    pivot = pivot_f1(summary)
    groups = [c for c in ["Timestamps","Métricas temp.","Escalas clínicas","Categóricas"] if c in pivot.columns]
    pivot  = pivot[groups].dropna(how="all")

    n_groups = len(groups)
    angles   = np.linspace(0, 2 * np.pi, n_groups, endpoint=False).tolist()
    angles  += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    for i, (model, row) in enumerate(pivot.iterrows()):
        vals = [row.get(g, 0) or 0 for g in groups] + [row.get(groups[0], 0) or 0]
        ax.plot(angles, vals, linewidth=1.5, label=model, color=PALETTE[i % 10])
        ax.fill(angles, vals, alpha=0.07, color=PALETTE[i % 10])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(groups, fontsize=11)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    ax.set_title("Perfil F1 por categoria de variável", fontsize=13, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), fontsize=8)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_overall_bar(overall: pd.DataFrame, out: Path):
    """Barra horizontal — F1 médio global por modelo (ranking)."""
    df_sorted = overall.sort_values("F1_mean", ascending=True)
    fig, ax   = plt.subplots(figsize=(8, max(5, len(df_sorted) * 0.4)))
    colors = [PALETTE[0] if "8bit" in m or "4bit" in m else PALETTE[2] for m in df_sorted["model"]]
    bars = ax.barh(df_sorted["model"], df_sorted["F1_mean"], color=colors, height=0.6)
    for bar, v in zip(bars, df_sorted["F1_mean"]):
        if not np.isnan(v):
            ax.text(v + 0.005, bar.get_y() + bar.get_height()/2,
                    f"{v:.3f}", va="center", fontsize=9)
    ax.set_xlabel("F1 médio global (macro-média)", fontsize=11)
    ax.set_title("Ranking de modelos — F1 médio global", fontsize=12)
    ax.set_xlim(0, 1.05)
    ax.grid(axis="x", alpha=0.4)
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=PALETTE[2], label="bf16 / fp16"),
        Patch(color=PALETTE[0], label="8-bit / 4-bit"),
    ], fontsize=9, loc="lower right")
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_per_variable_f1(df: pd.DataFrame, out: Path):
    """F1 por variável individual para o melhor modelo (Qwen2.5-7B),
    com barras de erro representando o desvio padrão entre todos os modelos competentes
    (excluindo DS-R1 que têm F1≈0 e distorceriam o desvio).
    As variáveis são ordenadas por F1 crescente (as mais difíceis à esquerda).
    Coloridas por grupo de variável.
    """
    # Modelos competentes (excluir DS-R1 e Llama-3.2-1B que falham completamente)
    excluir = {"DS-R1-Qwen-1.5B", "DS-R1-Qwen-7B", "Llama-3.2-1B"}
    df_comp = df[~df["model"].isin(excluir)].copy()

    best_model = "Qwen2.5-7B"
    best_df    = df[df["model"] == best_model][["variable", "group", "F1"]].copy()
    best_df    = best_df.sort_values("F1", ascending=True, na_position="first")

    # Std de F1 entre todos os modelos competentes por variável
    std_df = (
        df_comp.groupby("variable")["F1"]
        .apply(lambda s: s.fillna(0).std())
        .rename("F1_std")
        .reset_index()
    )
    best_df = best_df.merge(std_df, on="variable", how="left")

    # Cores por grupo
    group_colors = {
        "timestamp":   "#4878CF",
        "metric":      "#6ACC65",
        "scale":       "#D65F5F",
        "categorical": "#B47CC7",
        "binary":      "#C4AD66",
        "numeric":     "#77BEDB",
    }
    colors = [group_colors.get(g, "#888888") for g in best_df["group"]]

    # Rótulos legíveis para variáveis
    var_labels = {
        "admissaocoimbra":    "adm.coimbra",
        "admissaoorigem":     "adm.origem",
        "fibrinolise":        "fibrinólise",
        "puncaofemoral":      "punção femoral",
        "recanalizacao":      "recanal.",
        "sintomas":           "sintomas",
        "tcce":               "TCCE",
        "transferencia":      "transfer.",
        "door1_to_door2":     "D1→D2",
        "door_in_door_out":   "DIDO",
        "door_to_imaging":    "D→Img",
        "door_to_needle":     "DTN",
        "door_to_puncture":   "DTP",
        "onset_to_door":      "OTD",
        "onset_to_recan":     "OTR",
        "mrs_3meses_consulta":"mRS 3m",
        "mrs_alta_carta":     "mRS alta",
        "mrs_previo_carta":   "mRS prévio",
        "nihss_admissao_carta":"NIHSS adm",
        "nihss_alta_carta":   "NIHSS alta",
        "vivo_30_dias":       "vivo 30d",
        "dias_obito":         "dias óbito",
        "causa_obito":        "causa óbito",
        "complicacoes":       "complic.",
        "etiologia_toast":    "etiol. TOAST",
        "territorio":         "território",
        "tipo":               "tipo AVC",
        "tratamento":         "tratamento",
    }
    labels = [var_labels.get(v, v) for v in best_df["variable"]]

    fig, ax = plt.subplots(figsize=(14, 5))
    x = np.arange(len(best_df))
    bars = ax.bar(x, best_df["F1"].fillna(0), color=colors, width=0.7, zorder=2,
                  yerr=best_df["F1_std"].fillna(0), capsize=3,
                  error_kw={"elinewidth": 1.2, "ecolor": "black", "alpha": 0.6})
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8.5)
    ax.set_ylabel("F1-score (Qwen2.5-7B bf16)", fontsize=11)
    ax.set_title("F1-score por variável individual — Qwen2.5-7B\n"
                 "(barras de erro = desvio padrão entre modelos competentes)", fontsize=12)
    ax.set_ylim(0, 1.15)
    ax.axhline(0.9, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.grid(axis="y", alpha=0.35, zorder=0)

    from matplotlib.patches import Patch
    legend_handles = [Patch(color=c, label=GROUP_LABELS.get(g, g))
                      for g, c in group_colors.items()]
    ax.legend(handles=legend_handles, fontsize=9, loc="lower right", ncol=2)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_group_difficulty(df: pd.DataFrame, out: Path):
    """F1 médio por grupo de variável, média ± desvio padrão entre todos os 17 modelos.
    Mostra quais categorias são estruturalmente mais difíceis.
    Ordenado do mais difícil para o mais fácil (F1 crescente).
    """
    group_order = ["timestamp", "metric", "categorical", "scale", "numeric", "binary"]
    group_labels_list = [GROUP_LABELS.get(g, g) for g in group_order]

    rows = []
    for g in group_order:
        sub = df[df["group"] == g]["F1"].fillna(0)
        rows.append({"group": GROUP_LABELS.get(g, g), "mean": sub.mean(), "std": sub.std()})
    gdf = pd.DataFrame(rows).sort_values("mean", ascending=True)

    colors = plt.cm.RdYlGn(np.linspace(0.2, 0.85, len(gdf)))
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(gdf["group"], gdf["mean"], xerr=gdf["std"], color=colors,
                   height=0.55, capsize=5,
                   error_kw={"elinewidth": 1.5, "ecolor": "#333333"}, zorder=2)
    for bar, v in zip(bars, gdf["mean"]):
        ax.text(v + 0.005, bar.get_y() + bar.get_height()/2,
                f"{v:.3f}", va="center", fontsize=10, fontweight="bold")
    ax.set_xlabel("F1 médio (macro-média entre 17 modelos)", fontsize=11)
    ax.set_title("Dificuldade por categoria de variável\n(média ± desvio padrão entre todos os modelos)", fontsize=12)
    ax.set_xlim(0, 1.2)
    ax.axvline(0.5, color="red", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.axvline(0.9, color="green", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.grid(axis="x", alpha=0.35, zorder=0)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_prec_rec_top(overall: pd.DataFrame, out: Path):
    """Barras agrupadas: Precisão, Recall e F1 para os top 10 modelos (por F1).
    Permite ver onde os modelos sacrificam precisão por recall ou vice-versa.
    """
    top = overall.nlargest(10, "F1_mean").sort_values("F1_mean", ascending=False)

    x  = np.arange(len(top))
    w  = 0.25
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(x - w, top["Prec_mean"], w, label="Precisão", color=PALETTE[0], alpha=0.85)
    ax.bar(x,     top["F1_mean"],   w, label="F1",       color=PALETTE[2], alpha=0.85)
    ax.bar(x + w, top["Rec_mean"],  w, label="Recall",   color=PALETTE[1], alpha=0.85)

    for xi, (_, row) in zip(x, top.iterrows()):
        for offset, val in [(-w, row.Prec_mean), (0, row.F1_mean), (w, row.Rec_mean)]:
            ax.text(xi + offset, val + 0.008, f"{val:.2f}", ha="center", va="bottom", fontsize=7)

    ax.set_xticks(x)
    ax.set_xticklabels(top["model"], rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_title("Precisão, F1 e Recall — top 10 modelos", fontsize=12)
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.4)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_exp1_all_bars(df: pd.DataFrame, overall: pd.DataFrame, out: Path):
    """Exp 1 — Barras horizontais de todos os modelos da Exp 1 ordenados por F1,
    com tabela de dados abaixo (estilo Adelino Fig 7.1).
    Inclui Phi-3-mini e Phi-4-mini como outliers a destacar.
    """
    exp1_all = EXP1_LLAMA + EXP1_QWEN + EXP1_GEMMA + EXP1_DS
    ov = overall.set_index("model")

    # Adicionar Phi (pertencem ao Exp 2 mas são relevantes para contextualizar)
    exp1_models_present = [m for m in exp1_all if m in ov.index]
    sub = ov.loc[exp1_models_present, "F1_mean"].sort_values(ascending=True)

    # Cores por família
    family_color = {}
    for m in sub.index:
        if "Llama" in m:   family_color[m] = PALETTE[1]
        elif "Qwen" in m:  family_color[m] = PALETTE[0]
        elif "Gemma" in m: family_color[m] = PALETTE[2]
        else:              family_color[m] = PALETTE[3]

    colors = [family_color[m] for m in sub.index]

    fig, (ax, ax_tbl) = plt.subplots(2, 1, figsize=(9, 8),
                                      gridspec_kw={"height_ratios": [3, 1]})
    bars = ax.barh(sub.index, sub.values, color=colors, height=0.6)
    for bar, v in zip(bars, sub.values):
        ax.text(v + 0.005, bar.get_y() + bar.get_height()/2,
                f"{v:.3f}", va="center", fontsize=9)
    ax.set_xlabel("F1 médio global (macro-média, 150 casos)", fontsize=11)
    ax.set_title("Exp 1 — Efeito da dimensão do modelo (bf16)", fontsize=12)
    ax.set_xlim(0, 1.08)
    ax.axvline(0.9, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.grid(axis="x", alpha=0.4)

    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=PALETTE[0], label="Qwen2.5"),
        Patch(color=PALETTE[1], label="Llama"),
        Patch(color=PALETTE[2], label="Gemma-3"),
        Patch(color=PALETTE[3], label="DeepSeek-R1"),
    ], fontsize=9, loc="lower right")

    # Tabela de dados
    col_names  = ["Modelo", "F1 médio", "Prec.", "Recall"]
    table_data = []
    for m in sub.index[::-1]:  # top→bottom
        r = ov.loc[m]
        table_data.append([m, f"{r.F1_mean:.3f}", f"{r.Prec_mean:.3f}", f"{r.Rec_mean:.3f}"])

    ax_tbl.axis("off")
    tbl = ax_tbl.table(cellText=table_data, colLabels=col_names,
                       cellLoc="center", loc="center", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_facecolor("#CCCCCC")
            cell.set_text_props(fontweight="bold")
        cell.set_edgecolor("#AAAAAA")

    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_exp2_overall_bars(overall: pd.DataFrame, out: Path):
    """Exp 2 — Ranking horizontal por F1 global, todos os modelos de Exp2,
    coloridos por família, com tabela de dados (estilo Adelino Fig 7.4).
    """
    # Todos os modelos de ~6-12B (Exp 2) + modelos pequenos e outliers para contexto
    exp2_models = [
        "Qwen2.5-7B", "Qwen2.5-7B-8bit",
        "Llama-3.1-8B", "Llama-3.1-8B-8bit",
        "Gemma-3-4B",
        "Phi-3.5-mini", "Phi-3-mini", "Phi-4-mini",
        "Mistral-Nemo-12B",
        "DS-R1-Qwen-7B",
    ]
    ov = overall.set_index("model")
    present = [m for m in exp2_models if m in ov.index]
    sub = ov.loc[present, "F1_mean"].sort_values(ascending=True)

    def _family_color(m):
        if "Qwen" in m:    return PALETTE[0]
        if "Llama" in m:   return PALETTE[1]
        if "Gemma" in m:   return PALETTE[2]
        if "Phi" in m:     return PALETTE[4]
        if "Mistral" in m: return PALETTE[5]
        if "DS-R1" in m:   return PALETTE[3]
        return "#888888"

    colors = [_family_color(m) for m in sub.index]

    fig, (ax, ax_tbl) = plt.subplots(2, 1, figsize=(9, 9),
                                      gridspec_kw={"height_ratios": [3, 1]})
    bars = ax.barh(sub.index, sub.values, color=colors, height=0.6)
    for bar, v in zip(bars, sub.values):
        ax.text(v + 0.005, bar.get_y() + bar.get_height()/2,
                f"{v:.3f}", va="center", fontsize=9)
    ax.set_xlabel("F1 médio global (macro-média, 150 casos)", fontsize=11)
    ax.set_title("Exp 2 — Comparação entre famílias/receitas de treino", fontsize=12)
    ax.set_xlim(0, 1.08)
    ax.axvline(0.9, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.grid(axis="x", alpha=0.4)

    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=PALETTE[0], label="Qwen2.5"),
        Patch(color=PALETTE[1], label="Llama"),
        Patch(color=PALETTE[2], label="Gemma-3"),
        Patch(color=PALETTE[4], label="Phi"),
        Patch(color=PALETTE[5], label="Mistral"),
        Patch(color=PALETTE[3], label="DeepSeek-R1"),
    ], fontsize=9, loc="lower right")

    col_names  = ["Modelo", "F1 médio", "Prec.", "Recall"]
    table_data = []
    for m in sub.index[::-1]:
        r = ov.loc[m]
        table_data.append([m, f"{r.F1_mean:.3f}", f"{r.Prec_mean:.3f}", f"{r.Rec_mean:.3f}"])

    ax_tbl.axis("off")
    tbl = ax_tbl.table(cellText=table_data, colLabels=col_names,
                       cellLoc="center", loc="center", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_facecolor("#CCCCCC")
            cell.set_text_props(fontweight="bold")
        cell.set_edgecolor("#AAAAAA")

    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


# ── Tabela detalhada por variável ──────────────────────────────────────────────

def detailed_table(df: pd.DataFrame) -> pd.DataFrame:
    """Prec, Rec, F1, MAE por variável por modelo."""
    models  = df["model"].unique()
    rows    = []
    for var, grp_df in df.groupby("variable"):
        group = grp_df["group"].iloc[0]
        row   = {"variable": var, "group": group}
        for m in models:
            sub = grp_df[grp_df["model"] == m]
            if sub.empty:
                row[f"{m}_F1"]   = np.nan
                row[f"{m}_Prec"] = np.nan
                row[f"{m}_Rec"]  = np.nan
                row[f"{m}_MAE"]  = np.nan
            else:
                row[f"{m}_F1"]   = sub["F1"].values[0]
                row[f"{m}_Prec"] = sub["precision"].values[0]
                row[f"{m}_Rec"]  = sub["recall"].values[0]
                row[f"{m}_MAE"]  = sub["MAE"].values[0]
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["group", "variable"])


# ── English figures for the journal article ────────────────────────────────

EN_GROUP_LABELS = {
    "timestamp":   "Timestamps",
    "metric":      "Temporal metrics",
    "scale":       "Clinical scales",
    "categorical": "Categorical",
    "binary":      "Binary",
    "numeric":     "Numeric",
}

EN_VAR_LABELS = {
    "admissaocoimbra":    "adm.coimbra",
    "admissaoorigem":     "adm.origin",
    "fibrinolise":        "thrombolysis",
    "puncaofemoral":      "femoral punct.",
    "recanalizacao":      "recanalis.",
    "sintomas":           "onset",
    "tcce":               "CT scan",
    "transferencia":      "transfer",
    "door1_to_door2":     "D1→D2",
    "door_in_door_out":   "DIDO",
    "door_to_imaging":    "D→Img",
    "door_to_needle":     "DTN",
    "door_to_puncture":   "DTP",
    "onset_to_door":      "OTD",
    "onset_to_recan":     "OTR",
    "mrs_3meses_consulta":"mRS 3m",
    "mrs_alta_carta":     "mRS discharge",
    "mrs_previo_carta":   "mRS prior",
    "nihss_admissao_carta":"NIHSS adm",
    "nihss_alta_carta":   "NIHSS discharge",
    "vivo_30_dias":       "30d survival",
    "dias_obito":         "days to death",
    "causa_obito":        "death cause",
    "complicacoes":       "complications",
    "etiologia_toast":    "TOAST aetiol.",
    "territorio":         "territory",
    "tipo":               "episode type",
    "tratamento":         "treatment",
}


def plot_ranking_en(overall: pd.DataFrame, out: Path):
    """English version of overall ranking bar chart."""
    df_sorted = overall.sort_values("F1_mean", ascending=True)
    fig, ax   = plt.subplots(figsize=(8, max(5, len(df_sorted) * 0.4)))
    colors = [PALETTE[0] if "8bit" in m or "4bit" in m else PALETTE[2]
              for m in df_sorted["model"]]
    bars = ax.barh(df_sorted["model"], df_sorted["F1_mean"], color=colors, height=0.6)
    for bar, v in zip(bars, df_sorted["F1_mean"]):
        if not np.isnan(v):
            ax.text(v + 0.005, bar.get_y() + bar.get_height()/2,
                    f"{v:.3f}", va="center", fontsize=9)
    ax.set_xlabel("Macro-average F1-score (all 28 variables, NaN→0)", fontsize=11)
    ax.set_title("Model ranking — overall macro-average F1", fontsize=12)
    ax.set_xlim(0, 1.08)
    ax.grid(axis="x", alpha=0.4)
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=PALETTE[2], label="bf16 / fp16"),
        Patch(color=PALETTE[0], label="8-bit / 4-bit"),
    ], fontsize=9, loc="lower right")
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_size_ladders_en(df: pd.DataFrame, out: Path):
    """English version of Exp 1 size-ladder line plot."""
    overall = summary_overall(df).set_index("model")["F1_mean"]
    families = {
        "Llama":       (EXP1_LLAMA,  [1, 3, 8]),
        "Qwen2.5":     (EXP1_QWEN,   [0.5, 1.5, 3, 7]),
        "Gemma-3":     (EXP1_GEMMA,  [1, 4]),
        "DeepSeek-R1": (EXP1_DS,     [1.5, 7]),
    }
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (fam, (models, sizes)) in enumerate(families.items()):
        f1s = [overall.get(m, np.nan) for m in models]
        ax.plot(sizes, f1s, marker="o", label=fam, color=PALETTE[i], linewidth=2, markersize=7)
        for s, f in zip(sizes, f1s):
            if not np.isnan(f):
                ax.annotate(f"{f:.3f}", (s, f), textcoords="offset points",
                            xytext=(4, 5), fontsize=8)
    ax.set_xlabel("Parameter count (B)", fontsize=11)
    ax.set_ylabel("Macro-average F1-score", fontsize=11)
    ax.set_title("Experiment 1 — Effect of model size within family (bf16)", fontsize=12)
    ax.legend(fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.4)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_per_variable_f1_en(df: pd.DataFrame, out: Path):
    """English version of per-variable F1 chart."""
    excluir = {"DS-R1-Qwen-1.5B", "DS-R1-Qwen-7B", "Llama-3.2-1B"}
    df_comp  = df[~df["model"].isin(excluir)].copy()
    best_df  = df[df["model"] == "Qwen2.5-7B"][["variable", "group", "F1"]].copy()
    best_df  = best_df.sort_values("F1", ascending=True, na_position="first")

    std_df = (
        df_comp.groupby("variable")["F1"]
        .apply(lambda s: s.fillna(0).std())
        .rename("F1_std").reset_index()
    )
    best_df = best_df.merge(std_df, on="variable", how="left")

    group_colors = {
        "timestamp":   "#4878CF",
        "metric":      "#6ACC65",
        "scale":       "#D65F5F",
        "categorical": "#B47CC7",
        "binary":      "#C4AD66",
        "numeric":     "#77BEDB",
    }
    colors = [group_colors.get(g, "#888888") for g in best_df["group"]]
    labels = [EN_VAR_LABELS.get(v, v) for v in best_df["variable"]]

    fig, ax = plt.subplots(figsize=(14, 5))
    x = np.arange(len(best_df))
    ax.bar(x, best_df["F1"].fillna(0), color=colors, width=0.7, zorder=2,
           yerr=best_df["F1_std"].fillna(0), capsize=3,
           error_kw={"elinewidth": 1.2, "ecolor": "black", "alpha": 0.6})
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8.5)
    ax.set_ylabel("F1-score (Qwen2.5-7B bf16)", fontsize=11)
    ax.set_title("F1-score per variable — Qwen2.5-7B\n"
                 "(error bars = std across competent models)", fontsize=12)
    ax.set_ylim(0, 1.15)
    ax.axhline(0.9, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.grid(axis="y", alpha=0.35, zorder=0)

    from matplotlib.patches import Patch
    legend_handles = [Patch(color=c, label=EN_GROUP_LABELS.get(g, g))
                      for g, c in group_colors.items()]
    ax.legend(handles=legend_handles, fontsize=9, loc="lower right", ncol=2)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_group_difficulty_en(df: pd.DataFrame, out: Path):
    """English version of category difficulty chart."""
    group_order = ["timestamp", "metric", "categorical", "scale", "numeric", "binary"]
    rows = []
    for g in group_order:
        sub = df[df["group"] == g]["F1"].fillna(0)
        rows.append({"group": EN_GROUP_LABELS.get(g, g), "mean": sub.mean(), "std": sub.std()})
    gdf = pd.DataFrame(rows).sort_values("mean", ascending=True)

    colors = plt.cm.RdYlGn(np.linspace(0.2, 0.85, len(gdf)))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.barh(gdf["group"], gdf["mean"], xerr=gdf["std"], color=colors,
                   height=0.55, capsize=5,
                   error_kw={"elinewidth": 1.5, "ecolor": "#333333"}, zorder=2)
    for bar, v in zip(bars, gdf["mean"]):
        ax.text(v + 0.005, bar.get_y() + bar.get_height()/2,
                f"{v:.3f}", va="center", fontsize=10, fontweight="bold")
    ax.set_xlabel("Mean F1-score (macro-average across 17 models)", fontsize=11)
    ax.set_title("Extraction difficulty by variable category\n"
                 "(mean ± std across all models, easiest to hardest)", fontsize=12)
    ax.set_xlim(0, 1.2)
    ax.axvline(0.5, color="red", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.axvline(0.9, color="green", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.grid(axis="x", alpha=0.35, zorder=0)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_heatmap_en(pivot: pd.DataFrame, out: Path):
    """English version of F1 heatmap."""
    pivot_en = pivot.copy()
    pivot_en.columns = [EN_GROUP_LABELS.get(
        {v: k for k, v in GROUP_LABELS.items()}.get(c, c), c)
        for c in pivot_en.columns]
    fig, ax = plt.subplots(figsize=(10, max(6, len(pivot_en) * 0.45)))
    sns.heatmap(
        pivot_en.astype(float), annot=True, fmt=".3f",
        cmap="RdYlGn", vmin=0, vmax=1,
        linewidths=0.5, ax=ax, cbar_kws={"label": "F1-score"}
    )
    ax.set_title("F1-score by model and variable category", fontsize=13, pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


def plot_prec_rec_en(overall: pd.DataFrame, out: Path):
    """English version of Precision/F1/Recall grouped bar chart (top 10)."""
    top = overall.nlargest(10, "F1_mean").sort_values("F1_mean", ascending=False)
    x, w = np.arange(len(top)), 0.25
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(x - w, top["Prec_mean"], w, label="Precision", color=PALETTE[0], alpha=0.85)
    ax.bar(x,     top["F1_mean"],   w, label="F1",        color=PALETTE[2], alpha=0.85)
    ax.bar(x + w, top["Rec_mean"],  w, label="Recall",    color=PALETTE[1], alpha=0.85)
    for xi, (_, row) in zip(x, top.iterrows()):
        for offset, val in [(-w, row.Prec_mean), (0, row.F1_mean), (w, row.Rec_mean)]:
            ax.text(xi + offset, val + 0.008, f"{val:.2f}",
                    ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(top["model"], rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_title("Precision, F1, and Recall — top 10 models", fontsize=12)
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.4)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊  {out.name}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  default="validation_litellm",
                        help="Pasta com os CSVs (default: validation_litellm/)")
    parser.add_argument("--output", default="figures",
                        help="Pasta para figuras e relatórios (default: figures/)")
    args = parser.parse_args()

    in_dir  = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📂 A ler CSVs de: {in_dir}")
    df = load_latest_csvs(in_dir)
    print(f"\n   {df['model'].nunique()} modelos | {df['variable'].nunique()} variáveis\n")

    summary = summary_by_group(df)
    overall = summary_overall(df)
    pivot   = pivot_f1(summary)

    # ── Tabelas ────────────────────────────────────────────────────────────────
    print("📋 A gerar tabelas...")

    # Resumo por grupo
    pivot.to_csv(out_dir / "tabela_f1_por_grupo.csv")
    print(f"   tabela_f1_por_grupo.csv")

    # Detalhada por variável
    detailed = detailed_table(df)
    detailed.to_csv(out_dir / "tabela_detalhada.csv", index=False)
    print(f"   tabela_detalhada.csv")

    # Ranking global
    overall.to_csv(out_dir / "ranking_global.csv", index=False)
    print(f"   ranking_global.csv")

    # LaTeX — tabela principal F1 por grupo
    latex = to_latex_table(
        pivot.round(3),
        caption="F1-score por modelo e categoria de variável (macro-média, 150 casos sintéticos)",
        label="tab:resultados-f1"
    )
    (out_dir / "tabela_f1_latex.tex").write_text(latex, encoding="utf-8")
    print(f"   tabela_f1_latex.tex")

    # ── Gráficos ───────────────────────────────────────────────────────────────
    print("\n📊 A gerar gráficos...")
    plot_overall_bar(overall,                    out_dir / "fig_ranking_global.pdf")
    plot_heatmap(pivot,                          out_dir / "fig_heatmap_f1.pdf")
    plot_size_ladders(df,                        out_dir / "fig_exp1_dimensao.pdf")
    plot_family_bars(summary,                    out_dir / "fig_exp2_familia.pdf")
    plot_ablation(summary,                       out_dir / "fig_exp3_ablacao.pdf")
    plot_radar(summary,                          out_dir / "fig_radar.pdf")
    # Gráficos adicionais — profundidade analítica
    plot_per_variable_f1(df,                     out_dir / "fig_per_variavel_f1.pdf")
    plot_group_difficulty(df,                    out_dir / "fig_dificuldade_grupo.pdf")
    plot_prec_rec_top(overall,                   out_dir / "fig_prec_rec_top10.pdf")
    plot_exp1_all_bars(df, overall,              out_dir / "fig_exp1_barras.pdf")
    plot_exp2_overall_bars(overall,              out_dir / "fig_exp2_barras.pdf")

    # ── English figures for journal article ───────────────────────────────────
    art_dir = Path("/Users/beatrizcastelo/Downloads/Elsevier_Article__elsarticle__Template/figures")
    art_dir.mkdir(parents=True, exist_ok=True)
    print("\n── English figures (article) ─────────────────────────────────────────────")
    plot_ranking_en(overall,           art_dir / "fig_ranking_en.pdf")
    plot_size_ladders_en(df,           art_dir / "fig_exp1_size_en.pdf")
    plot_per_variable_f1_en(df,        art_dir / "fig_per_variable_f1_en.pdf")
    plot_group_difficulty_en(df,       art_dir / "fig_group_difficulty_en.pdf")
    plot_heatmap_en(pivot,             art_dir / "fig_heatmap_en.pdf")
    plot_prec_rec_en(overall,          art_dir / "fig_prec_rec_en.pdf")

    # ── Resumo no terminal ─────────────────────────────────────────────────────
    print("\n" + "="*80)
    print("  RANKING GLOBAL — F1 médio por modelo  (NaN F1 → 0)")
    print("="*80)
    print(f"  {'Modelo':<32} {'F1':>7}  {'Prec':>7}  {'Rec':>7}  {'NaN/28':>6}")
    print("  " + "-"*65)
    for _, row in overall.iterrows():
        f1   = f"{row.F1_mean:.4f}"
        prec = f"{row.Prec_mean:.4f}"
        rec  = f"{row.Rec_mean:.4f}"
        nan_f1 = int(row.get("n_nan_f1", 0))
        flag = "  ⚠" if nan_f1 > 5 else ""
        print(f"  {row.model:<32} {f1:>7}  {prec:>7}  {rec:>7}  {nan_f1:>6}{flag}")

    print(f"\n✅ Tudo guardado em: {out_dir}/\n")


if __name__ == "__main__":
    main()
