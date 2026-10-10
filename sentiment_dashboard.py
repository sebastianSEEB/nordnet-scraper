#!/usr/bin/env python3
"""
Dashboard: forum-sentiment mot avkastning
=========================================
Viser resultatene fra sentiment_analysis.py.

    pip install streamlit plotly pandas
    streamlit run sentiment_dashboard.py

Hent fersk data fra GitHub først (git pull), så ser du siste kjøring.
"""

import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

DATA_DIR = os.environ.get("NORDNET_DATA_DIR", "nordnet_data")
A_DIR = os.path.join(DATA_DIR, "analysis")
BLUE, ORANGE, GREY, RED, GREEN = "#2a6fdb", "#e07b39", "#9aa0a6", "#d64545", "#2e9e5b"

st.set_page_config(page_title="Forum-sentiment", layout="wide")


@st.cache_data
def load_results():
    with open(os.path.join(A_DIR, "results.json"), encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_csv(name):
    return pd.read_csv(os.path.join(A_DIR, name), parse_dates=["day"])


@st.cache_data
def load_abnormal_returns():
    px = pd.read_csv(os.path.join(DATA_DIR, "prices", "prices.csv"), parse_dates=["date"])
    wide = px.pivot_table(index="date", columns="slug", values="adj_close").sort_index()
    rets = wide.pct_change(fill_method=None)
    market = rets.pop("_benchmark") if "_benchmark" in rets else rets.mean(axis=1)
    return rets.where(rets.abs() < 0.5).sub(market, axis=0)


@st.cache_data
def load_scored_posts():
    from archive_posts import iter_archive
    scores = pd.read_json(os.path.join(DATA_DIR, "sentiment", "scores.jsonl"), lines=True)
    posts = pd.DataFrame([{k: p.get(k) for k in ("key", "slug", "author", "text", "posted_at")}
                          for p in iter_archive(DATA_DIR)])
    df = posts.merge(scores[["key", "sentiment", "relevance", "category"]], on="key")
    df["posted_at"] = pd.to_datetime(df["posted_at"], utc=True, format="ISO8601").dt.tz_convert("Europe/Oslo")
    return df


def fmt(x, d=3):
    return "–" if x is None else f"{x:.{d}f}"


def pct(x, d=2):
    return "–" if x is None else f"{x * 100:.{d}f} %"


if not os.path.exists(os.path.join(A_DIR, "results.json")):
    st.title("Forum-sentiment mot avkastning")
    st.info("Ingen resultater ennå. Kjør i rekkefølge: `score_sentiment.py`, `fetch_prices.py`, "
            "`sentiment_analysis.py` (eller vent på GitHub-workflowen og gjør `git pull`).")
    st.stop()

R = load_results()
panel = load_csv("daily_panel.csv")
preds = load_csv("predictions.csv")
m = R["meta"]

st.title("Forum-sentiment mot avkastning")
st.caption(f"{m['first_day']} → {m['last_day']} · {m['n_days']} handelsdager · marked: {m['market']} · "
           f"innlegg før {m['cutoff_oslo']} teller for samme dag · oppdatert {m['generated_at'][:16]} UTC")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Scorede innlegg", f"{m['n_posts_scored']:,}")
c2.metric("Aksje-dager", f"{m['n_stock_days']:,}", help="Aksje × handelsdag med minst ett relevant innlegg")
c3.metric("Snitt daglig IC", fmt(R["ic"]["mean"]), help="Rangkorrelasjon mellom dagens sentiment og morgendagens meravkastning, på tvers av aksjer")
c4.metric("Flaks-test p", fmt(R["permutation"]["p_value"]), help="Under 0,05 = sjelden ren flaks")
st.info(R["verdict"])

tab1, tab2, tab3, tab4 = st.tabs(["Reaksjon eller prediksjon?", "Per aksje", "Modeller og feil", "Om dataene"])

# ---------------------------------------------------------------- tab 1
with tab1:
    st.markdown("Hvis forumet bare **reagerer** på kursen, ser du en trapp til venstre og ingenting til høyre. "
                "En ekte **prediksjon** viser seg som en trapp til høyre.")
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True,
                        subplot_titles=("Samme dag (reaksjon)", "Neste dag (prediksjon)"))
    for col, key, color in [(1, "same_day", GREY), (2, "next_day", BLUE)]:
        b = R["binned"].get(key) or []
        fig.add_bar(x=[f"Q{i + 1}" for i in range(len(b))], y=[v["y_mean"] * 100 for v in b],
                    error_y=dict(type="data", array=[v["y_se"] * 100 for v in b]),
                    marker_color=color, row=1, col=col, showlegend=False,
                    hovertemplate="%{y:.2f} %<extra></extra>")
    fig.update_yaxes(title_text="Snitt meravkastning (%)", row=1, col=1)
    fig.update_xaxes(title_text="Sentiment-kvintil (Q1 = mest negativ)")
    fig.update_layout(height=380, margin=dict(t=40, b=10))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Hver aksje-dag som ett punkt")
    target = st.radio("Avkastning", ["Neste dag", "Samme dag"], horizontal=True)
    tcol = "ret_next" if target == "Neste dag" else "ret_same"
    d = panel.dropna(subset=["sent_w", tcol])
    d = d[d["n_rel"] >= st.slider("Minst antall relevante innlegg den dagen", 1, 10, 1)]
    if len(d) > 2:
        slope, icpt = np.polyfit(d["sent_w"], d[tcol] * 100, 1)
        xs = np.linspace(-1, 1, 20)
        fig = go.Figure()
        fig.add_scatter(x=d["sent_w"], y=d[tcol] * 100, mode="markers",
                        marker=dict(size=5, color=BLUE, opacity=0.35), text=d["slug"],
                        hovertemplate="%{text}<br>sentiment %{x:.2f}<br>avkastning %{y:.2f} %<extra></extra>",
                        name="aksje-dag")
        fig.add_scatter(x=xs, y=icpt + slope * xs, mode="lines", line=dict(color=ORANGE, width=3),
                        name=f"trend: {slope:.2f} %-poeng per sentiment-enhet")
        fig.update_layout(height=420, xaxis_title="Relevansvektet sentiment", yaxis_title="Meravkastning (%)",
                          yaxis_range=[-10, 10], legend=dict(orientation="h", y=1.08), margin=dict(t=30))
        st.plotly_chart(fig, width="stretch")
        corr = d[["sent_w", tcol]].corr(method="spearman").iloc[0, 1]
        st.caption(f"{len(d):,} punkter · Spearman-korrelasjon {corr:.3f}. Punktsky uten tydelig helning = svakt signal.")

    ic = pd.Series(R["ic_series"])
    if len(ic):
        ic.index = pd.to_datetime(ic.index)
        fig = go.Figure()
        fig.add_bar(x=ic.index, y=ic.values, marker_color=[BLUE if v > 0 else ORANGE for v in ic.values], name="daglig IC")
        fig.add_scatter(x=ic.index, y=ic.expanding().mean(), mode="lines", line=dict(color="black"), name="løpende snitt")
        fig.update_layout(height=300, title="Daglig IC over tid", margin=dict(t=40), legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- tab 2
with tab2:
    counts = panel.groupby("slug")["n_rel"].sum().sort_values(ascending=False)
    slug = st.selectbox("Aksje (sortert etter forumaktivitet)", counts.index,
                        format_func=lambda s: f"{s}  ({int(counts[s])} relevante innlegg)")
    abn = load_abnormal_returns()
    sub = panel[panel["slug"] == slug].set_index("day")
    if slug in abn:
        a = abn[slug].dropna()
        a = a[a.index >= pd.Timestamp(m["first_day"])]
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_bar(x=sub.index, y=sub["sent_w"], name="sentiment (dag)",
                    marker_color=[GREEN if v > 0 else RED for v in sub["sent_w"].fillna(0)], opacity=0.6,
                    customdata=sub["n_rel"], hovertemplate="sentiment %{y:.2f}<br>%{customdata} innlegg<extra></extra>")
        fig.add_scatter(x=a.index, y=((1 + a).cumprod() - 1) * 100, name="kumulativ meravkastning (%)",
                        line=dict(color=BLUE, width=2.5), secondary_y=True)
        fig.update_yaxes(title_text="Sentiment", range=[-1, 1], secondary_y=False)
        fig.update_yaxes(title_text="Meravkastning vs. marked (%)", secondary_y=True)
        fig.update_layout(height=420, legend=dict(orientation="h", y=1.1), margin=dict(t=30))
        st.plotly_chart(fig, width="stretch")
    else:
        st.warning("Ingen kurser for denne aksjen (sjekk ticker_overrides.json).")

    posts = load_scored_posts()
    p = posts[posts["slug"] == slug].sort_values("posted_at", ascending=False).head(50)
    st.markdown("**Siste innlegg med score**")
    st.dataframe(p[["posted_at", "sentiment", "relevance", "category", "author", "text"]],
                 hide_index=True, width="stretch",
                 column_config={"posted_at": st.column_config.DatetimeColumn("Skrevet (senest)", format="DD.MM HH:mm"),
                                "sentiment": st.column_config.ProgressColumn("Sentiment", min_value=-1, max_value=1, format="%.2f"),
                                "relevance": st.column_config.ProgressColumn("Relevans", min_value=0, max_value=1, format="%.2f"),
                                "text": st.column_config.TextColumn("Tekst", width="large")})

# ---------------------------------------------------------------- tab 3
with tab3:
    st.markdown("Alle tall under er **ut-av-utvalget**: modellen er trent på dagene *før* hver testuke. "
                "«Gjett 0» er nullmodellen – en modell som ikke slår den, har ikke lært noe nyttig.")
    rows = []
    for k, label in R["model_labels"].items():
        e = R["oos"].get(k, {})
        rows.append({"Modell": label, "MAE": pct(e.get("mae")), "RMSE": pct(e.get("rmse")),
                     "R² mot «gjett 0»": fmt(e.get("r2_vs_zero"), 4), "Treff på retning": pct(e.get("hit_rate"), 1),
                     "IC": fmt(e.get("ic_mean")), "Long–short / dag": pct(e.get("long_short_daily"), 3),
                     "R² på treningsdata": fmt(R["in_sample"].get(k, {}).get("r2_vs_zero"), 4)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Stort gap mellom «R² på treningsdata» og «R² mot gjett 0» = overtilpasning (modellen har pugget støy).")

    oos = preds.dropna(subset=["gbm"])
    if not oos.empty:
        wk = oos.assign(week=oos["day"].dt.to_period("W").dt.start_time)
        fig = go.Figure()
        for col, color, label in [("zero", GREY, "Gjett 0"), ("linear_sentiment", BLUE, "Lineær sentiment"),
                                  ("ridge_all", "#6a3d9a", "Ridge"), ("gbm", ORANGE, "Gradient boosting")]:
            mae = wk.groupby("week").apply(lambda s: np.mean(np.abs(s["ret_next"] - s[col])), include_groups=False)
            fig.add_scatter(x=mae.index, y=mae.values * 100, mode="lines+markers", name=label, line=dict(color=color))
        fig.update_layout(height=340, title="Gjennomsnittlig feil per testuke (lavere = bedre)",
                          yaxis_title="MAE (%-poeng)", legend=dict(orientation="h"), margin=dict(t=40))
        st.plotly_chart(fig, width="stretch")

        st.markdown("**Prediksjon mot fasit** (velg modell)")
        model = st.selectbox("Modell", ["linear_sentiment", "ridge_all", "gbm"],
                             format_func=lambda k: R["model_labels"][k])
        fig = go.Figure()
        fig.add_scatter(x=oos[model] * 100, y=oos["ret_next"] * 100, mode="markers",
                        marker=dict(size=5, opacity=0.35, color=BLUE), text=oos["slug"],
                        hovertemplate="%{text}<br>predikert %{x:.2f} %<br>faktisk %{y:.2f} %<extra></extra>")
        lim = float(np.nanquantile(np.abs(oos[model] * 100), 0.99)) or 1
        fig.add_scatter(x=[-lim, lim], y=[-lim, lim], mode="lines", line=dict(color=GREY, dash="dash"), name="perfekt")
        fig.update_layout(height=400, xaxis_title="Predikert meravkastning (%)", yaxis_title="Faktisk (%)",
                          yaxis_range=[-10, 10], showlegend=False, margin=dict(t=20))
        st.plotly_chart(fig, width="stretch")
        st.caption("Prediksjonene er små fordi modellene (riktig nok) er forsiktige når signalet er svakt.")

    coefs = R["in_sample"].get("ridge_coefficients")
    if coefs:
        s = pd.Series(coefs).rename(index=R["feature_labels"]).sort_values()
        fig = go.Figure(go.Bar(x=s.values, y=s.index, orientation="h",
                               marker_color=[GREEN if v > 0 else RED for v in s.values]))
        fig.update_layout(height=380, title="Ridge: hva modellen vektlegger (standardiserte features)",
                          margin=dict(t=40, l=10))
        st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- tab 4
with tab4:
    st.markdown("**Kjente svakheter**")
    for c in R["caveats"]:
        st.markdown(f"- {c}")
    st.markdown("**Korrelasjoner**")
    st.json(R["correlations"], expanded=False)
    st.caption("Dette er en analyse av historiske sammenhenger, ikke en kjøps- eller salgsanbefaling.")
