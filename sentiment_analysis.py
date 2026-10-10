#!/usr/bin/env python3
"""
Forum-sentiment mot faktisk avkastning
======================================
Kobler sentiment-scorene (score_sentiment.py) med kursene (fetch_prices.py),
måler sammenhengen, og trener enkle ML-modeller som testes ærlig på data de
ikke har sett.

Viktige designvalg (les dette før du tolker resultatene):

1. HANDELSDAG OG CUTOFF. Et innlegg tilhører handelsdag d hvis det ble skrevet
   før kl 16:00 Oslo-tid på dag d (og etter 16:00 forrige handelsdag). Da kan
   du faktisk handle på signalet i sluttauksjonen (16:20) samme dag. Innlegg i
   helgen havner på mandag. Tidspunktene i arkivet er "seneste mulige", så et
   innlegg kan havne en dag for sent, men aldri for tidlig (ingen look-ahead).

2. MÅLET ER NESTE DAGS AVKASTNING. Forumet reagerer mest på kurs som allerede
   har beveget seg. Samme-dags sammenheng er derfor stor, men ubrukelig å
   handle på. Vi viser begge, så du ser forskjellen.

3. MERAVKASTNING. Vi trekker fra markedets avkastning (OSEBX), så vi måler
   aksjens egen bevegelse - ikke at hele børsen steg.

4. WALK-FORWARD. Modellene trenes kun på dager FØR testuka, og testes på uka.
   Så flyttes vinduet en uke frem. Alle feilmål er beregnet på slike
   ut-av-utvalget-prediksjoner. Vi viser også feilen på treningsdata, så du
   ser hvor mye en modell "pynter" på seg selv (overtilpasning).

5. TILFELDIGHETSTEST. Vi stokker sentimentet tilfeldig mellom aksjene innen
   hver dag 2000 ganger. Hvis ekte data ikke slår de stokkede versjonene
   tydelig, er sammenhengen sannsynligvis flaks.

Output i nordnet_data/analysis/:
    daily_panel.csv   én rad per aksje per handelsdag med innlegg
    predictions.csv   ut-av-utvalget-prediksjoner per modell
    results.json      alle tall (leses av dashboardet)
    report.md         lesbar rapport (fungerer fint på GitHub-mobil)
    *.png             figurer

Bruk:
    pip install pandas numpy scipy scikit-learn matplotlib
    python sentiment_analysis.py
"""

import argparse
import json
import os
from datetime import datetime, time, timezone
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy import stats

from archive_posts import OSLO, iter_archive

BENCHMARK_SLUG = "_benchmark"
CUTOFF = time(16, 0)          # innlegg før dette tilhører dagens signal
RELEVANT = 0.5                # relevans >= dette regnes som "om aksjen"
MIN_STOCKS_PER_DAY = 5        # for tverrsnitts-IC
TEST_BLOCK_DAYS = 5           # walk-forward: test én uke om gangen
MIN_TRAIN_DAYS = 10           # minst så mange handelsdager før første test
N_PERMUTATIONS = 2000
SEED = 42

FEATURES = [
    "sent_w", "sent_sum", "pos_share", "neg_share", "n_rel_log",
    "attention_z", "sent_change", "news_share", "sent_eng", "ret_same",
]
FEATURE_LABELS = {
    "sent_w": "Snitt-sentiment (relevansvektet)",
    "sent_sum": "Sum sentiment (styrke × antall)",
    "pos_share": "Andel positive innlegg",
    "neg_share": "Andel negative innlegg",
    "n_rel_log": "Antall relevante innlegg (log)",
    "attention_z": "Uvanlig mye aktivitet (z-score)",
    "sent_change": "Endring i sentiment vs. siste dager",
    "news_share": "Andel nyheter/analyser",
    "sent_eng": "Sentiment vektet med likes",
    "ret_same": "Dagens meravkastning (kontroll)",
}


# ------------------------------------------------------------------ data

def load_posts(data_dir: str) -> pd.DataFrame:
    path = os.path.join(data_dir, "sentiment", "scores.jsonl")
    if not os.path.exists(path):
        raise SystemExit("Fant ingen scores - kjør score_sentiment.py først.")
    scores = pd.read_json(path, lines=True).drop_duplicates("key", keep="last")
    posts = pd.DataFrame([{
        "key": p["key"], "slug": p["slug"], "posted_at": p.get("posted_at"),
        "scraped_at": p["scraped_at"], "precision": p.get("time_precision"),
        "engagement": sum(p.get("engagement_numbers") or []),
        "has_link": bool(p.get("has_link")),
    } for p in iter_archive(data_dir)])
    df = posts.merge(scores[["key", "sentiment", "relevance", "category"]], on="key", how="inner")
    df = df.dropna(subset=["posted_at"])
    df["posted_at"] = pd.to_datetime(df["posted_at"], utc=True, format="ISO8601")
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], utc=True, format="ISO8601")
    return df


def load_prices(data_dir: str) -> (pd.DataFrame, pd.Series, str):
    path = os.path.join(data_dir, "prices", "prices.csv")
    if not os.path.exists(path):
        raise SystemExit("Fant ingen kurser - kjør fetch_prices.py først.")
    px = pd.read_csv(path, parse_dates=["date"])
    wide = px.pivot_table(index="date", columns="slug", values="adj_close").sort_index()
    rets = wide.pct_change(fill_method=None)
    if BENCHMARK_SLUG in rets.columns:
        market = rets.pop(BENCHMARK_SLUG)
        market_name = "OSEBX"
    else:
        market = rets.mean(axis=1)
        market_name = "likevektet snitt av aksjene"
    # Ekstreme dagsbevegelser (>50 %) er nesten alltid datafeil/emisjoner
    rets = rets.where(rets.abs() < 0.5)
    return rets, market, market_name


def assign_signal_day(posted_at: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    """Første handelsdag d der cutoff(d) er ETTER at innlegget ble skrevet."""
    cutoffs = pd.DatetimeIndex([
        datetime.combine(d.date(), CUTOFF, tzinfo=OSLO).astimezone(timezone.utc) for d in calendar
    ])
    # Samme tidsenhet på begge sider (pandas 3 bruker ofte mikrosekunder)
    cut_ns = cutoffs.as_unit("ns").asi8
    post_ns = pd.DatetimeIndex(posted_at).tz_convert("UTC").as_unit("ns").asi8
    idx = np.searchsorted(cut_ns, post_ns, side="right")
    out = pd.Series(pd.NaT, index=posted_at.index, dtype="datetime64[ns]")
    ok = idx < len(calendar)
    out[ok] = calendar[idx[ok]].to_numpy()
    return out


# -------------------------------------------------------------- features

def build_panel(posts: pd.DataFrame, rets: pd.DataFrame, market: pd.Series) -> pd.DataFrame:
    calendar = rets.index
    posts = posts.copy()
    posts["day"] = assign_signal_day(posts["posted_at"], calendar)

    # Før scraperen startet er "0 innlegg" ukjent, ikke null. Start panelet
    # første hele handelsdag etter første scraping.
    first_scrape = posts["scraped_at"].min()
    start_day = assign_signal_day(pd.Series([first_scrape]), calendar).iloc[0]
    posts = posts[posts["day"] >= start_day].dropna(subset=["day"])

    w = posts["relevance"]
    posts["sw"] = posts["sentiment"] * w
    posts["rel"] = (w >= RELEVANT).astype(int)
    posts["pos"] = ((posts["sentiment"] > 0.2) & posts["rel"].astype(bool)).astype(int)
    posts["neg"] = ((posts["sentiment"] < -0.2) & posts["rel"].astype(bool)).astype(int)
    posts["news"] = (posts["category"].isin(["nyhet", "analyse"]) & posts["rel"].astype(bool)).astype(int)
    posts["ew"] = w * (1 + np.log1p(posts["engagement"]))
    posts["sew"] = posts["sentiment"] * posts["ew"]

    g = posts.groupby(["slug", "day"])
    daily = pd.DataFrame({
        "n_posts": g.size(),
        "n_rel": g["rel"].sum(),
        "w_sum": g["relevance"].sum(),
        "sent_sum": g["sw"].sum(),
        "pos": g["pos"].sum(),
        "neg": g["neg"].sum(),
        "news": g["news"].sum(),
        "ew_sum": g["ew"].sum(),
        "sew_sum": g["sew"].sum(),
    }).reset_index()

    # Fullt panel (alle aksjer med kurs × alle dager) for å kunne regne ut
    # "uvanlig aktivitet" mot aksjens egen normal
    days = calendar[calendar >= start_day]
    slugs = sorted(set(daily["slug"]) & set(rets.columns))
    full = pd.MultiIndex.from_product([slugs, days], names=["slug", "day"]).to_frame(index=False)
    panel = full.merge(daily, on=["slug", "day"], how="left")
    for c in ["n_posts", "n_rel", "w_sum", "sent_sum", "pos", "neg", "news", "ew_sum", "sew_sum"]:
        panel[c] = panel[c].fillna(0)
    panel = panel.sort_values(["slug", "day"]).reset_index(drop=True)

    gs = panel.groupby("slug")["n_posts"]
    prev_mean = gs.transform(lambda s: s.shift(1).rolling(20, min_periods=5).mean())
    prev_std = gs.transform(lambda s: s.shift(1).rolling(20, min_periods=5).std())
    panel["attention_z"] = ((panel["n_posts"] - prev_mean) / prev_std.replace(0, np.nan)).clip(-5, 5)

    panel["sent_w"] = panel["sent_sum"] / panel["w_sum"].replace(0, np.nan)
    panel["sent_eng"] = panel["sew_sum"] / panel["ew_sum"].replace(0, np.nan)
    panel["pos_share"] = panel["pos"] / panel["n_rel"].replace(0, np.nan)
    panel["neg_share"] = panel["neg"] / panel["n_rel"].replace(0, np.nan)
    panel["news_share"] = panel["news"] / panel["n_rel"].replace(0, np.nan)
    panel["n_rel_log"] = np.log1p(panel["n_rel"])

    # Meravkastning: aksje minus marked
    abn_w = rets.sub(market, axis=0)
    tgt = {
        "ret_same": abn_w,                                   # dagen innleggene ble skrevet
        "ret_next": abn_w.shift(-1),                         # MÅLET: neste handelsdag
        "ret_next5": abn_w[::-1].rolling(5, min_periods=5).sum()[::-1].shift(-1),  # neste 5 dager
    }
    for name, frame in tgt.items():
        long = frame.stack().rename(name).reset_index()
        long.columns = ["day", "slug", name]
        panel = panel.merge(long, on=["day", "slug"], how="left")

    # Sentiment-endring: dagens snitt mot snittet av aksjens siste 5 dager med innlegg
    obs = panel[panel["n_rel"] > 0].copy()
    obs["prev_sent"] = obs.groupby("slug")["sent_w"].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    panel = panel.merge(obs[["slug", "day", "prev_sent"]], on=["slug", "day"], how="left")
    panel["sent_change"] = panel["sent_w"] - panel["prev_sent"]
    return panel


# --------------------------------------------------------------- metrics

def daily_ic(df: pd.DataFrame, pred_col: str, target: str = "ret_next") -> pd.Series:
    """Tverrsnitts-IC: hver dag, rangkorrelasjon mellom signal og avkastning på tvers av aksjer."""
    out = {}
    for day, sub in df.dropna(subset=[pred_col, target]).groupby("day"):
        if len(sub) >= MIN_STOCKS_PER_DAY and sub[pred_col].nunique() > 1:
            out[day] = stats.spearmanr(sub[pred_col], sub[target]).statistic
    return pd.Series(out, dtype=float)


def ic_summary(ic: pd.Series) -> dict:
    ic = ic.dropna()
    n = len(ic)
    if n < 3:
        return {"days": n, "mean": None, "t_stat": None, "share_positive": None}
    return {"days": n, "mean": float(ic.mean()),
            "t_stat": float(ic.mean() / (ic.std(ddof=1) / np.sqrt(n))) if ic.std(ddof=1) > 0 else None,
            "share_positive": float((ic > 0).mean())}


def permutation_test(df: pd.DataFrame, col: str, n: int = N_PERMUTATIONS) -> dict:
    """Stokker signalet mellom aksjer innen hver dag. p = andel stokkede
    versjoner med minst like høy |snitt-IC| som ekte data."""
    d = df.dropna(subset=[col, "ret_next"])
    groups = [g for _, g in d.groupby("day") if len(g) >= MIN_STOCKS_PER_DAY]
    if len(groups) < 3:
        return {"p_value": None, "real_ic": None}
    rng = np.random.default_rng(SEED)
    ranks_y = [stats.rankdata(g["ret_next"].to_numpy()) for g in groups]
    ranks_x = [stats.rankdata(g[col].to_numpy()) for g in groups]

    def mean_ic(xs):
        vals = [np.corrcoef(x, y)[0, 1] for x, y in zip(xs, ranks_y) if np.std(x) > 0 and np.std(y) > 0]
        return float(np.mean(vals)) if vals else 0.0

    real = mean_ic(ranks_x)
    null = np.array([mean_ic([rng.permutation(x) for x in ranks_x]) for _ in range(n)])
    return {"p_value": float((np.abs(null) >= abs(real)).mean()), "real_ic": real,
            "null_p95": float(np.quantile(np.abs(null), 0.95))}


def error_metrics(df: pd.DataFrame, pred: str, target: str = "ret_next") -> dict:
    d = df.dropna(subset=[pred, target])
    y, p = d[target].to_numpy(), d[pred].to_numpy()
    if len(y) == 0:
        return {}
    sse, sse0 = float(np.sum((y - p) ** 2)), float(np.sum(y ** 2))
    nz = p != 0
    ls = []
    for _, sub in d.groupby("day"):
        if len(sub) >= 6 and sub[pred].nunique() > 2:
            q = sub[pred].rank(pct=True)
            ls.append(sub.loc[q > 2 / 3, target].mean() - sub.loc[q <= 1 / 3, target].mean())
    ls = np.array(ls)
    ic = ic_summary(daily_ic(d, pred, target))
    return {
        "n": int(len(y)),
        "mae": float(np.mean(np.abs(y - p))),
        "rmse": float(np.sqrt(sse / len(y))),
        "r2_vs_zero": float(1 - sse / sse0) if sse0 > 0 else None,
        "hit_rate": float(np.mean(np.sign(p[nz]) == np.sign(y[nz]))) if nz.any() else None,
        "ic_mean": ic["mean"], "ic_t": ic["t_stat"],
        "long_short_daily": float(ls.mean()) if len(ls) else None,
        "long_short_t": float(ls.mean() / (ls.std(ddof=1) / np.sqrt(len(ls)))) if len(ls) > 2 and ls.std(ddof=1) > 0 else None,
        "long_short_days": int(len(ls)),
    }


# ---------------------------------------------------------------- models

def make_models() -> Dict[str, object]:
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return {
        "linear_sentiment": ("Lineær: kun snitt-sentiment", ["sent_w"], lambda: LinearRegression()),
        "ridge_all": ("Ridge: alle features", FEATURES,
                      lambda: make_pipeline(StandardScaler(), Ridge(alpha=50.0))),
        "gbm": ("Gradient boosting (grunne trær)", FEATURES,
                lambda: HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150,
                                                      min_samples_leaf=40, l2_regularization=1.0,
                                                      random_state=SEED)),
    }


def prepare_X(df: pd.DataFrame, cols: List[str], fill: pd.Series) -> np.ndarray:
    return df[cols].fillna(fill[cols]).fillna(0).to_numpy(dtype=float)


def walk_forward(data: pd.DataFrame) -> (pd.DataFrame, dict):
    days = np.array(sorted(data["day"].unique()))
    preds = data[["slug", "day", "ret_next", "ret_same", "sent_w", "n_rel"]].copy()
    preds["zero"] = 0.0
    preds["train_mean"] = np.nan
    models = make_models()
    for name in models:
        preds[name] = np.nan
    in_sample = {}

    if len(days) < MIN_TRAIN_DAYS + 2:
        return preds, in_sample
    for start in range(MIN_TRAIN_DAYS, len(days), TEST_BLOCK_DAYS):
        test_days = days[start:start + TEST_BLOCK_DAYS]
        train = data[data["day"] < test_days[0]]
        test_mask = data["day"].isin(test_days)
        if train.empty or not test_mask.any():
            continue
        preds.loc[test_mask, "train_mean"] = train["ret_next"].mean()
        med = train[FEATURES].median()
        for name, (_, cols, factory) in models.items():
            m = factory()
            m.fit(prepare_X(train, cols, med), train["ret_next"].to_numpy())
            preds.loc[test_mask, name] = m.predict(prepare_X(data[test_mask], cols, med))

    # Treningsfeil (fit på alt, mål på alt) - kun for å vise overtilpasning
    med = data[FEATURES].median()
    for name, (_, cols, factory) in models.items():
        m = factory()
        X = prepare_X(data, cols, med)
        m.fit(X, data["ret_next"].to_numpy())
        tmp = data[["day", "ret_next"]].copy()
        tmp["p"] = m.predict(X)
        in_sample[name] = error_metrics(tmp, "p")
        if name == "ridge_all":
            coefs = m[-1].coef_
            in_sample["ridge_coefficients"] = {c: float(v) for c, v in zip(cols, coefs)}
    return preds, in_sample


# ---------------------------------------------------------------- report

def binned(df: pd.DataFrame, x: str, y: str, bins: int = 5) -> list:
    d = df.dropna(subset=[x, y])
    if len(d) < bins * 10:
        return []
    d = d.assign(bin=pd.qcut(d[x], bins, duplicates="drop"))
    out = []
    for b, sub in d.groupby("bin", observed=True):
        out.append({"bin": str(b), "x_mean": float(sub[x].mean()), "y_mean": float(sub[y].mean()),
                    "y_se": float(sub[y].std(ddof=1) / np.sqrt(len(sub))), "n": int(len(sub))})
    return out


def corr(df: pd.DataFrame, x: str, y: str) -> dict:
    d = df.dropna(subset=[x, y])
    if len(d) < 10:
        return {"n": int(len(d))}
    pr = stats.pearsonr(d[x], d[y])
    sr = stats.spearmanr(d[x], d[y])
    return {"n": int(len(d)), "pearson": float(pr.statistic), "pearson_p": float(pr.pvalue),
            "spearman": float(sr.statistic), "spearman_p": float(sr.pvalue)}


def make_figures(out_dir: str, data: pd.DataFrame, preds: pd.DataFrame, ic_series: pd.Series) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                         "font.size": 10})
    blue, orange, grey = "#2a6fdb", "#e07b39", "#9aa0a6"

    # 1) Sentiment-kvintiler mot samme dag og neste dag
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, target, title in [(axes[0], "ret_same", "Samme dag (reaksjon)"),
                              (axes[1], "ret_next", "Neste dag (prediksjon)")]:
        b = binned(data, "sent_w", target)
        if b:
            xs = range(1, len(b) + 1)
            ax.bar(xs, [v["y_mean"] * 100 for v in b], yerr=[v["y_se"] * 100 for v in b],
                   color=blue if target == "ret_next" else grey, capsize=3)
            ax.set_xticks(list(xs), [f"Q{i}" for i in xs])
        ax.axhline(0, color="black", lw=0.6)
        ax.set_title(title)
        ax.set_xlabel("Sentiment-kvintil (Q1 = mest negativ)")
    axes[0].set_ylabel("Snitt meravkastning (%)")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "sentiment_quintiles.png"))
    plt.close(fig)

    # 2) Daglig IC over tid
    if len(ic_series):
        fig, ax = plt.subplots(figsize=(9, 3.2))
        ax.bar(ic_series.index, ic_series.values, color=[blue if v > 0 else orange for v in ic_series.values])
        ax.plot(ic_series.index, ic_series.expanding().mean().values, color="black", lw=1.2,
                label="Løpende snitt")
        ax.axhline(0, color="black", lw=0.6)
        ax.set_ylabel("IC (rangkorrelasjon)")
        ax.set_title("Daglig tverrsnitts-IC: sentiment i dag mot meravkastning i morgen")
        ax.legend(frameon=False)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "ic_over_time.png"))
        plt.close(fig)

    # 3) Feil per uke: modeller mot "gjett 0"
    oos = preds.dropna(subset=["gbm"])
    if not oos.empty:
        wk = oos.assign(week=pd.to_datetime(oos["day"]).dt.to_period("W").dt.start_time)
        fig, ax = plt.subplots(figsize=(9, 3.2))
        for col, color, label in [("zero", grey, "Gjett 0"), ("linear_sentiment", blue, "Lineær sentiment"),
                                  ("ridge_all", "#6a3d9a", "Ridge"), ("gbm", orange, "Gradient boosting")]:
            mae = wk.groupby("week").apply(lambda s: np.mean(np.abs(s["ret_next"] - s[col])), include_groups=False)
            ax.plot(mae.index, mae.values * 100, marker="o", color=color, label=label, lw=1.4)
        ax.set_ylabel("MAE (%-poeng)")
        ax.set_title("Prediksjonsfeil per testuke (lavere = bedre)")
        ax.legend(frameon=False, ncol=4, fontsize=8)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "model_errors.png"))
        plt.close(fig)


def pct(x, d=2):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:.{d}f} %"


def num(x, d=3):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def write_report(out_dir: str, r: dict) -> None:
    m = r["meta"]
    L = ["# Forum-sentiment mot avkastning",
         "",
         f"Generert {m['generated_at'][:16].replace('T', ' ')} UTC · {m['n_posts_scored']:,} scorede innlegg · "
         f"{m['n_stock_days']:,} aksje-dager · {m['n_stocks']} aksjer · {m['first_day']} → {m['last_day']} "
         f"({m['n_days']} handelsdager) · marked: {m['market']}",
         "",
         "## Konklusjon",
         "",
         r["verdict"],
         "",
         "## 1. Reagerer forumet, eller forutsier det?",
         "",
         "| Sammenheng | Korrelasjon (Spearman) | p-verdi | n |",
         "|---|---|---|---|"]
    for key, label in [("same_day", "Sentiment ↔ meravkastning samme dag"),
                       ("next_day", "Sentiment → meravkastning neste dag"),
                       ("next_5d", "Sentiment → meravkastning neste 5 dager*")]:
        c = r["correlations"].get(key, {})
        L.append(f"| {label} | {num(c.get('spearman'))} | {num(c.get('spearman_p'))} | {c.get('n', 0):,} |")
    L += ["",
          "*5-dagers vinduer overlapper, så p-verdien der er for optimistisk.",
          "",
          "![Sentiment-kvintiler](sentiment_quintiles.png)",
          "",
          "## 2. Tverrsnitts-IC og tilfeldighetstest",
          "",
          f"Snitt daglig IC: **{num(r['ic']['mean'])}** (t = {num(r['ic']['t_stat'], 2)}, "
          f"{r['ic']['days']} dager, positiv {pct(r['ic']['share_positive'], 0)} av dagene).",
          f"Tilfeldighetstest ({N_PERMUTATIONS} stokkinger): p = **{num(r['permutation']['p_value'])}**. "
          f"Stokkede data gir |IC| over {num(r['permutation'].get('null_p95'))} i 5 % av tilfellene.",
          "",
          "IC over 0,02–0,03 som holder seg over tid regnes som interessant i kvant-verdenen. "
          "p under 0,05 betyr at sammenhengen sjelden oppstår av ren flaks.",
          "",
          "![IC over tid](ic_over_time.png)",
          "",
          "## 3. Modeller – ut-av-utvalget (walk-forward)",
          "",
          "| Modell | MAE | RMSE | R² mot «gjett 0» | Treff på retning | IC | Long–short per dag |",
          "|---|---|---|---|---|---|---|"]
    for key, label in r["model_labels"].items():
        e = r["oos"].get(key, {})
        L.append(f"| {label} | {pct(e.get('mae'))} | {pct(e.get('rmse'))} | {num(e.get('r2_vs_zero'), 4)} | "
                 f"{pct(e.get('hit_rate'), 1)} | {num(e.get('ic_mean'))} | {pct(e.get('long_short_daily'), 3)} |")
    L += ["",
          "R² over 0 betyr at modellen bommer mindre enn å bare gjette 0 % meravkastning. "
          "Med daglige aksjeavkastninger er selv 0,005 bra – de fleste ekte signaler er svake.",
          "",
          "![Feil per uke](model_errors.png)",
          "",
          "### Overtilpasning: treningsdata vs. ukjente data",
          "",
          "| Modell | R² på treningsdata | R² ut-av-utvalget |",
          "|---|---|---|"]
    for key in ["linear_sentiment", "ridge_all", "gbm"]:
        L.append(f"| {r['model_labels'][key]} | {num(r['in_sample'].get(key, {}).get('r2_vs_zero'), 4)} | "
                 f"{num(r['oos'].get(key, {}).get('r2_vs_zero'), 4)} |")
    L += ["",
          "Stort gap = modellen har lært støy i treningsdataene som ikke gjentar seg.",
          "",
          "## Kjente svakheter",
          ""] + [f"- {c}" for c in r["caveats"]] + [
          "",
          "_Dette er en analyse av historiske sammenhenger, ikke en kjøps- eller salgsanbefaling._"]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def verdict(r: dict) -> str:
    p = r["permutation"].get("p_value")
    ic = r["ic"].get("mean")
    best = max((v.get("r2_vs_zero") or -9, k) for k, v in r["oos"].items() if k not in ("zero",))
    same = r["correlations"].get("same_day", {}).get("spearman")
    nxt = r["correlations"].get("next_day", {}).get("spearman")
    parts = []
    if same is not None and nxt is not None:
        if abs(same) > 2 * abs(nxt):
            parts.append(f"Sentimentet henger mye tettere sammen med samme dags kurs ({num(same)}) enn neste dags "
                         f"({num(nxt)}) – forumet reagerer mest på bevegelser som allerede har skjedd.")
        else:
            parts.append(f"Samme dag: {num(same)}, neste dag: {num(nxt)}.")
    if p is None:
        parts.append("For lite data til tilfeldighetstesten ennå.")
    elif p < 0.05:
        parts.append(f"Neste-dags-sammenhengen (IC {num(ic)}) består tilfeldighetstesten (p = {num(p)}). "
                     "Lovende, men kort periode – følg med på om den holder seg.")
    else:
        parts.append(f"Neste-dags-sammenhengen (IC {num(ic)}) er ikke statistisk skillbar fra flaks (p = {num(p)}).")
    if best[0] > 0:
        parts.append(f"Beste modell ut-av-utvalget: {r['model_labels'][best[1]]} (R² {num(best[0], 4)} mot «gjett 0»).")
    else:
        parts.append("Ingen modell slår «gjett 0» på ukjente data ennå – det vanligste utfallet med lite data.")
    if r["meta"]["n_days"] < 120:
        parts.append(f"Med {r['meta']['n_days']} handelsdager er alt dette foreløpig; "
                     "ca. 6–12 måneder data trengs før konklusjonene blir solide.")
    return " ".join(parts)


# ------------------------------------------------------------------ main

def main() -> None:
    ap = argparse.ArgumentParser(description="Sentiment mot avkastning + ML")
    ap.add_argument("--data-dir", default="nordnet_data")
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()
    out_dir = os.path.join(args.data_dir, "analysis")
    os.makedirs(out_dir, exist_ok=True)

    posts = load_posts(args.data_dir)
    rets, market, market_name = load_prices(args.data_dir)
    panel = build_panel(posts, rets, market)
    data = panel[(panel["n_rel"] > 0) & panel["ret_next"].notna()].copy()
    data = data.sort_values(["day", "slug"]).reset_index(drop=True)
    print(f"{len(posts):,} scorede innlegg -> {len(data):,} aksje-dager med relevante innlegg og kjent neste-dags-kurs")

    ic_series = daily_ic(data, "sent_w")
    preds, in_sample = walk_forward(data)
    labels = {"zero": "Gjett 0 (nullmodell)", "train_mean": "Gjett snittet"}
    labels.update({k: v[0] for k, v in make_models().items()})
    oos_mask = preds["gbm"].notna()
    oos = {k: error_metrics(preds[oos_mask], k) for k in labels}

    days = sorted(data["day"].unique())
    r = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_posts_scored": int(len(posts)),
            "n_stock_days": int(len(data)),
            "n_stocks": int(data["slug"].nunique()),
            "n_days": int(len(days)),
            "first_day": str(pd.Timestamp(days[0]).date()) if days else None,
            "last_day": str(pd.Timestamp(days[-1]).date()) if days else None,
            "oos_rows": int(oos_mask.sum()),
            "market": market_name,
            "cutoff_oslo": CUTOFF.strftime("%H:%M"),
            "relevance_threshold": RELEVANT,
        },
        "correlations": {
            "same_day": corr(data, "sent_w", "ret_same"),
            "next_day": corr(data, "sent_w", "ret_next"),
            "next_5d": corr(data, "sent_w", "ret_next5"),
            "attention_next_abs": corr(data.assign(a=data["ret_next"].abs()), "attention_z", "a"),
        },
        "binned": {"same_day": binned(data, "sent_w", "ret_same"), "next_day": binned(data, "sent_w", "ret_next")},
        "ic": ic_summary(ic_series),
        "ic_series": {str(pd.Timestamp(k).date()): float(v) for k, v in ic_series.items()},
        "permutation": permutation_test(data, "sent_w"),
        "model_labels": labels,
        "oos": oos,
        "in_sample": in_sample,
        "feature_labels": FEATURE_LABELS,
        "caveats": [
            "Scraperen ser bare de ~10 nyeste innleggene per aksje per kjøring, og GitHub hopper over noen "
            "timer. Travle dager er derfor underrepresentert.",
            "Tidspunkt er estimert fra «for N t siden» (presisjon ~1 time, «for N døgn siden» ~1 døgn). "
            "Vi bruker seneste mulige tidspunkt, så signaler kan komme en dag for sent, aldri for tidlig.",
            "Meravkastning = aksje minus indeks (ingen beta-justering). Aksjer med høy beta ser bedre ut i stigende marked.",
            "Kurser fra Yahoo Finance; noen småaksjer kan mangle eller ha hull.",
            "Ingen handelskostnader i long–short-tallet. Spread i småaksjer kan alene spise et svakt signal.",
            "Sentiment er scoret av en språkmodell – den kan feiltolke ironi og forum-slang.",
        ],
    }
    r["verdict"] = verdict(r)

    data.to_csv(os.path.join(out_dir, "daily_panel.csv"), index=False)
    preds.to_csv(os.path.join(out_dir, "predictions.csv"), index=False)
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, default=str)
    if not args.no_figures:
        make_figures(out_dir, data, preds, ic_series)
    write_report(out_dir, r)
    print(r["verdict"])
    print(f"Resultater -> {out_dir}/")


if __name__ == "__main__":
    main()
