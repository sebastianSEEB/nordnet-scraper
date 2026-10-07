"""Re-prices the backtest trades under different brokerage setups (no re-run needed)."""
import json
import numpy as np
import pandas as pd
import backtest as bt

NORDIC = (".OL", ".ST", ".CO", ".HE")
# Typical bid-ask spread crossed per round trip, by liquidity (Oslo order books, rough).
SPREAD = {"large": 0.0005, "mid": 0.004, "small": 0.015}
TRADE = 10_000  # NOK per trade


def nordnet(rate_nordic, min_nordic, rate_other, min_other, fx):
    def cost(row):
        nordic = row.ticker.endswith(NORDIC)
        rate, mn = (rate_nordic, min_nordic) if nordic else (rate_other, min_other)
        per_side = max(rate, mn / TRADE)
        return 2 * per_side + (0 if nordic else fx) + SPREAD[row.bucket]
    return cost


SCEN = {
    "zero_cost": lambda r: 0.0,
    "student (0.15%, min 1 kr)": nordnet(0.0015, 1, 0.002, 49, 0.0015),
    "normal (0.049%, min 79 kr)": nordnet(0.00049, 79, 0.001, 99, 0.0015),
    "new-customer (0.035%, min 1 kr)": nordnet(0.00035, 1, 0.0009, 89, 0.0015),
    "previous model (0.3/1/2%)": lambda r: bt.P["bucket_cost"][r.bucket],
}

d, _ = bt.load_prices()
raw = pd.read_csv("results/trades.csv.gz")
out = {}
for name, f in SCEN.items():
    t = raw.copy()
    t["cost_stress"] = t.apply(f, axis=1)
    t = bt.finish(t)
    res = {"avg_cost": round(float(t.cost_stress.mean()), 4)}
    for m in ["ripple", "rebound", "drift_A"]:
        g = t[t["mode"] == m]
        s, k = bt.stats(g), bt.stats(g[~g.skip])
        res[m] = dict(net=s["mean"], t=s["t_stat"], net_with_skip=k.get("mean"), t_skip=k.get("t_stat"),
                      trades_skip=k.get("trades"),
                      by_bucket={b: round(float(x.net.mean()), 4) for b, x in g.groupby("bucket")})
    _, _, res["book_ripple_only"] = bt.portfolio(t, d, ("ripple",))
    _, _, res["book_ripple_rebound"] = bt.portfolio(t, d)
    out[name] = res
    print(name, json.dumps(res), flush=True)
json.dump(out, open("results/cost_scenarios.json", "w"), indent=1)
