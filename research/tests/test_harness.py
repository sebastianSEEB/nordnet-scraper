"""
Tester for testbenken på syntetiske kurser (ingen nett, ingen Yahoo).

    python -m unittest discover -s research/tests -t .
"""

import copy
import json
import os
import shutil
import tempfile
import unittest

import numpy as np
import pandas as pd

from copytrade.paper import entry_index
from news_ml.common import BENCHMARK
from research import costs as C
from research.archive_prices import archive_prices, update_universe_log
from research.data import load_config, load_panel
from research.gate0_insiders import evaluate, insider_buy_signals
from research.harness import (HoldoutUsed, clustered_t, normalize_published, reaction_index, read_log,
                              distinct_tests, required_t, run_event_study, tradable_returns)


def make_prices(n_tickers=40, days=1200, seed=0, flat_range=False, plants=(), jump=0.03, dividend=None):
    """Syntetiske dagskurser. plants = [(ticker_nr, dag_nr)] får et hopp på `jump` i løpet av dagen.

    flat_range=True setter høy = lav = slutt (ingen spread i Abdi-Ranaldo -> gulvet brukes).
    dividend=(ticker_nr, dag_nr, andel): kursen faller med utbyttet på dagen, adj_close gjør det ikke
    (samme konvensjon som Yahoo: adj_close = close for siste dager, tidligere dager skalert ned).
    """
    rng = np.random.default_rng(seed)
    cal = pd.bdate_range("2020-01-01", periods=days)
    m_on, m_in = rng.normal(0, 0.004, days), rng.normal(0.0003, 0.008, days)
    frames = []

    def add(ticker, lo_on, lo_in, div=None):
        lc = np.cumsum(lo_on + lo_in) + np.log(100)
        close, opn = np.exp(lc), np.exp(lc - lo_in)
        adj = close.copy()
        if div is not None:
            d, frac = div
            close[d:] *= 1 - frac
            opn[d:] *= 1 - frac
            adj = adj * (1 - frac)
        if flat_range:
            hi = lo = close
        else:
            wig = np.abs(rng.normal(0, 0.006, days))
            hi = np.maximum(opn, close) * np.exp(wig)
            lo = np.minimum(opn, close) * np.exp(-wig)
        frames.append(pd.DataFrame({"date": [d.date().isoformat() for d in cal], "ticker": ticker, "open": opn,
                                    "high": hi, "low": lo, "close": close, "adj_close": adj, "volume": 1e5}))

    add(BENCHMARK, m_on, m_in)
    for k in range(n_tickers):
        on = m_on + rng.normal(0, 0.008, days)
        intra = m_in + rng.normal(0, 0.014, days)
        for pk, pday in plants:
            if pk == k:
                intra[pday] += np.log(1 + jump)
        div = (dividend[1], dividend[2]) if dividend and dividend[0] == k else None
        add(f"T{k:02d}.OL", on, intra, div)
    return pd.concat(frames, ignore_index=True), cal


def signal(ticker_nr, day, cal, hour_utc=6):
    """Publisert kl. hour_utc UTC på dag `day` (06 UTC = 07:00/08:00 Oslo -> samme dags åpning hele året)."""
    return {"ticker": f"T{ticker_nr:02d}.OL", "published": f"{cal[day].date()}T{hour_utc:02d}:00:00Z",
            "direction": 1}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = copy.deepcopy(load_config())
        self.cfg["holdout_start"] = "2024-01-01"
        self.cfg["placebo_draws"] = 200

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def panel_from(self, df):
        path = os.path.join(self.tmp, "prices.csv")
        df.to_csv(path, index=False)
        return load_panel(price_csv=path, use_archive=False)


class TestTimeRules(unittest.TestCase):
    def setUp(self):
        self.cal = pd.bdate_range("2024-03-01", "2024-03-29")

    def day(self, s):
        return self.cal.get_loc(pd.Timestamp(s))

    def test_before_open_same_day(self):  # 07:00 UTC = 08:00 Oslo
        self.assertEqual(entry_index(self.cal, "2024-03-05T07:00:00Z"), self.day("2024-03-05"))

    def test_after_open_next_day(self):  # 09:00 UTC = 10:00 Oslo
        self.assertEqual(entry_index(self.cal, "2024-03-05T09:00:00Z"), self.day("2024-03-06"))

    def test_weekend_to_monday(self):
        self.assertEqual(entry_index(self.cal, "2024-03-09T12:00:00Z"), self.day("2024-03-11"))

    def test_reaction_day(self):
        self.assertEqual(reaction_index(self.cal, "2024-03-05T14:00:00Z"), self.day("2024-03-05"))  # 15:00 Oslo
        self.assertEqual(reaction_index(self.cal, "2024-03-05T16:00:00Z"), self.day("2024-03-06"))  # 17:00 Oslo

    def test_date_only_is_after_close(self):
        iso = normalize_published("2024-03-05")
        self.assertEqual(entry_index(self.cal, iso), self.day("2024-03-06"))


class TestStats(unittest.TestCase):
    def test_required_t_grows_with_k(self):
        self.assertAlmostEqual(required_t(1), 3.0)
        self.assertGreater(required_t(1000), 4.0)
        self.assertGreaterEqual(required_t(50), required_t(10))

    def test_clustered_t_does_not_reward_duplicates(self):
        rng = np.random.default_rng(1)
        x = rng.normal(0.01, 0.05, 200)
        base = clustered_t(x, np.arange(200))
        dup = np.repeat(x, 5)
        groups = np.repeat(np.arange(200), 5)
        self.assertAlmostEqual(clustered_t(dup, groups), base, delta=0.05 * abs(base) + 0.05)
        plain = dup.mean() / (dup.std(ddof=1) / np.sqrt(len(dup)))
        self.assertGreater(plain, 2 * abs(base))


class TestCosts(Base):
    def test_commission_classes(self):
        c = copy.deepcopy(self.cfg["costs"])
        c["fee_class"] = "mini"
        self.assertAlmostEqual(C.commission_rate(c), 29 / 10_000)
        c["fee_class"] = "student"
        self.assertAlmostEqual(C.commission_rate(c), 15 / 10_000)

    def test_abdi_ranaldo_recovers_spread(self):
        rng = np.random.default_rng(3)
        days, steps, S = 3000, 100, 0.01
        eff = np.cumsum(rng.normal(0, 0.02 / np.sqrt(steps), days * steps)).reshape(days, steps)
        trades = eff + rng.choice([-S / 2, S / 2], size=eff.shape)
        close = pd.DataFrame({"X": np.exp(trades[:, -1])})
        high = pd.DataFrame({"X": np.exp(trades.max(axis=1))})
        low = pd.DataFrame({"X": np.exp(trades.min(axis=1))})
        hs = C.abdi_ranaldo_half_spread(close, high, low, window=days, min_obs=days - 5, floor=0, cap=1)
        est = hs["X"].dropna().iloc[-1]
        self.assertAlmostEqual(est, S / 2, delta=0.3 * S / 2)

    def test_net_is_gross_minus_costs(self):
        df, cal = make_prices(n_tickers=5, days=300, flat_range=True)
        panel = self.panel_from(df)
        sig = pd.DataFrame([signal(k, d, cal) for k in range(5) for d in range(70, 250, 20)])
        from research.harness import prepare_signals
        prep, _ = prepare_signals(sig, panel)
        costs = self.cfg["costs"]
        tr = tradable_returns(prep, panel, 5, costs, 0, len(panel.cal))
        per_side = costs["half_spread_floor"] + C.commission_rate(costs) + costs["slippage_per_side"]
        self.assertTrue(len(tr["net"]) > 30)
        np.testing.assert_allclose(tr["cost"], 2 * per_side)
        np.testing.assert_allclose(tr["net"], tr["excess"] - 2 * per_side)


class TestEventStudy(Base):
    def test_planted_signal_is_found(self):
        rng = np.random.default_rng(11)
        plants = [(int(rng.integers(0, 40)), int(d)) for d in rng.choice(np.arange(80, 950), 150, replace=False)]
        df, cal = make_prices(plants=plants, jump=0.03)
        panel = self.panel_from(df)
        sig = pd.DataFrame([signal(k, d, cal) for k, d in plants])
        res = run_event_study(sig, "plantet", panel=panel, config=self.cfg, out_root=self.tmp)
        h5 = res["horizons"]["5"]
        self.assertGreater(h5["gross_excess"]["mean"], 0.02)
        self.assertTrue(h5["passed"], h5["reasons"])
        self.assertGreater(res["reaction"]["car_0_1"]["mean"], 0.02)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "plantet", "report.md")))

    def test_random_signals_fail(self):
        rng = np.random.default_rng(8)
        df, cal = make_prices(seed=2)
        panel = self.panel_from(df)
        sig = pd.DataFrame([signal(int(rng.integers(0, 40)), int(rng.integers(80, 950)), cal) for _ in range(150)])
        res = run_event_study(sig, "tilfeldig", panel=panel, config=self.cfg, out_root=self.tmp)
        self.assertFalse(res["passed_any"])
        self.assertLess(abs(res["horizons"]["5"]["gross_excess"]["mean"]), 0.01)

    def test_holdout_excluded_and_locked(self):
        df, cal = make_prices(n_tickers=10, days=1200)
        panel = self.panel_from(df)
        h = int(panel.cal.searchsorted(pd.Timestamp(self.cfg["holdout_start"])))
        sig = pd.DataFrame([signal(k % 10, d, cal) for k, d in enumerate(range(h + 5, 1150, 3))])
        res = run_event_study(sig, "idé", panel=panel, config=self.cfg, out_root=self.tmp)
        self.assertEqual(res["horizons"]["1"]["net"]["n"], 0)  # alt ligger i holdout -> ingenting i bygg
        res2 = run_event_study(sig, "idé", panel=panel, config=self.cfg, out_root=self.tmp, use_holdout=True)
        self.assertGreater(res2["horizons"]["1"]["net"]["n"], 0)
        with self.assertRaises(HoldoutUsed):
            run_event_study(sig, "idé", panel=panel, config=self.cfg, out_root=self.tmp, use_holdout=True)

    def test_build_trades_never_exit_inside_holdout(self):
        df, cal = make_prices(n_tickers=10, days=1200)
        panel = self.panel_from(df)
        h = int(panel.cal.searchsorted(pd.Timestamp(self.cfg["holdout_start"])))
        sig = pd.DataFrame([signal(k, h - 30, cal) for k in range(10)])
        res = run_event_study(sig, "kant", panel=panel, config=self.cfg, out_root=self.tmp)
        self.assertEqual(res["horizons"]["20"]["net"]["n"], 10)
        self.assertEqual(res["horizons"]["60"]["net"]["n"], 0)

    def test_log_counts_distinct_tests(self):
        df, cal = make_prices(n_tickers=5, days=400)
        panel = self.panel_from(df)
        sig = pd.DataFrame([signal(k, d, cal) for k in range(5) for d in range(80, 300, 15)])
        for params in ({"a": 1}, {"a": 1}, {"a": 2}):
            run_event_study(sig, "x", params=params, panel=panel, config=self.cfg, out_root=self.tmp, write=False)
        log = read_log(self.tmp)
        self.assertEqual(len(log), 3)
        self.assertEqual(distinct_tests(log), 2)
        self.assertEqual(log[-1]["K"], 2)


class TestArchive(Base):
    def test_append_only_and_survivor(self):
        df, cal = make_prices(n_tickers=3, days=120, dividend=(1, 60, 0.05))
        adir = os.path.join(self.tmp, "arkiv")
        first = df[df["date"] < cal[100].date().isoformat()]
        self.assertGreater(archive_prices(first, adir), 0)
        # Yahoo "endrer" historikken og legger til nye dager: gamle rader skal stå urørt
        changed = df.copy()
        changed.loc[changed["date"] < cal[100].date().isoformat(), "close"] *= 1.5
        n_new = archive_prices(changed, adir)
        self.assertEqual(n_new, 20 * 4)  # 20 nye dager x (3 aksjer + indeks)
        self.assertEqual(archive_prices(changed, adir), 0)  # idempotent
        a = pd.concat([pd.read_csv(os.path.join(adir, x)) for x in sorted(os.listdir(adir))
                       if x.startswith("prices_")])
        orig = df.set_index(["date", "ticker"])["close"]
        a = a.set_index(["date", "ticker"])
        early = a.index.get_level_values(0) < cal[100].date().isoformat()
        np.testing.assert_allclose(a.loc[early, "close"], orig.loc[a.index[early]], rtol=1e-5)

        # T01 forsvinner fra Yahoo -> hentes fra arkivet, med riktig utbyttejustering
        gone = df[df["ticker"] != "T01.OL"]
        path = os.path.join(self.tmp, "prices.csv")
        gone.to_csv(path, index=False)
        panel = load_panel(price_csv=path, archive_dir=adir)
        self.assertIn("T01.OL", panel.close.columns)
        self.assertEqual(panel.source["T01.OL"], "arkiv")
        true = df[df["ticker"] == "T01.OL"].set_index(pd.to_datetime(df.loc[df["ticker"] == "T01.OL", "date"]))
        r_true = true["adj_close"].pct_change().dropna()
        r_arch = panel.close["T01.OL"].pct_change().reindex(r_true.index)
        np.testing.assert_allclose(r_arch.to_numpy(), r_true.to_numpy(), rtol=1e-4, atol=1e-5)

    def test_universe_log(self):
        df, _ = make_prices(n_tickers=3, days=60)
        adir = os.path.join(self.tmp, "arkiv")
        os.makedirs(adir)
        uni = [{"ticker": f"T{k:02d}.OL"} for k in range(3)] + [{"ticker": "NY.OL"}]
        ev = update_universe_log(df, adir, universe=uni, today="2026-01-01")
        self.assertEqual(ev[0]["event"], "start")
        self.assertEqual(ev[0]["missing_from_yahoo"], ["NY.OL"])
        ev = update_universe_log(df[df["ticker"] != "T02.OL"], adir, universe=uni, today="2026-01-02")
        self.assertEqual([(e["ticker"], e["event"]) for e in ev], [("T02.OL", "mangler_hos_yahoo")])
        with open(os.path.join(adir, "universe_log.jsonl")) as f:
            self.assertEqual(len([json.loads(x) for x in f]), 2)


class TestGate0(unittest.TestCase):
    def test_signal_mapping_and_verdict(self):
        trades = [{"id": "1", "issuer": "EQNR", "published": "2024-01-02T07:00:00Z", "direction": 1, "noise": False},
                  {"id": "2", "issuer": "EQNR", "published": "2024-01-02T07:00:00Z", "direction": -1, "noise": False},
                  {"id": "3", "issuer": "EQNR", "published": "2024-01-02T07:00:00Z", "direction": 1, "noise": True},
                  {"id": "4", "issuer": "UKJENT", "published": "2024-01-02T07:00:00Z", "direction": 1,
                   "noise": False}]
        sig = insider_buy_signals(trades, [{"issuer": "EQNR", "ticker": "EQNR.OL"}])
        self.assertEqual(list(sig["id"]), ["1"])
        cfg = load_config()
        ok = evaluate({"reaction": {"car_0_1": {"n": 900, "mean": 0.011, "t_cluster": 5.0}}}, cfg)
        bad = evaluate({"reaction": {"car_0_1": {"n": 900, "mean": 0.08, "t_cluster": 5.0}}}, cfg)
        self.assertTrue(ok["passed"])
        self.assertFalse(bad["passed"])


if __name__ == "__main__":
    unittest.main()
