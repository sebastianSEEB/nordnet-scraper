"""Tester for Fase 1-delene (syntetiske data, ingen nett)."""

import os
import shutil
import tempfile
import unittest

import numpy as np
import pandas as pd

from copytrade.insiders import NOISE2_RE, extract_person, parse_trade
from copytrade.paper import run_trades
from news_ml.attention import busy_days, placement_events, predicted_dividend_signals
from research import herd, insider2
from research.data import load_panel
from research.phase1 import old_timing
from research.tests.test_harness import make_prices


class TestPerson(unittest.TestCase):
    CASES = [
        ("Henning Beltestad, CEO of Lerøy Seafood Group ASA, has on 21 August 2026 purchased 12,000 shares",
         "Lerøy Seafood Group ASA", "Henning Beltestad"),
        ("AWC AS, a related party to vice chairman in Protector Forsikring ASA Arve Ree, has today acquired 23'285 "
         "shares", "Protector Forsikring ASA", "Arve Ree"),
        ("Styremedlem i Storebrand ASA Martin Skancke har i dag kjøpt 2.500 aksjer", "Storebrand ASA",
         "Martin Skancke"),
        ("Geir-Egil Bolstad, finansdirektør, har 20. november 2020 kjøpt 10.000 egenkapitalbevis",
         "SpareBank 1 Østlandet", "Geir-Egil Bolstad"),
        ("Oslo, 3 May 2021 Argentos AS, a company controlled by Chief Executive Officer Raymond Carlsen, has on "
         "3 May 2021 bought 22,500 shares in Scatec ASA", "Scatec ASA", "Raymond Carlsen"),
    ]

    def test_examples(self):
        for body, issuer, want in self.CASES:
            self.assertEqual(extract_person(body, issuer), want, body)

    def test_unknown_is_none(self):
        self.assertIsNone(extract_person("Reference is made to the stock exchange announcement made earlier today.",
                                         "OKEA ASA"))


class TestNoise(unittest.TestCase):
    def test_buyback_and_placement_are_noise(self):
        self.assertTrue(NOISE2_RE.search("The shares were purchased in accordance with the share buy-back program"))
        self.assertTrue(NOISE2_RE.search("Bever Holding AS has subscribed for 84,027,899 shares in the private placement"))
        self.assertFalse(NOISE2_RE.search("Henning Beltestad, CEO, has purchased 12,000 shares at NOK 50"))

    def test_parse_trade_marks_reason(self):
        t = parse_trade({"id": "1", "title": "Mandatory notification of trade", "issuer": "X",
                         "body": "In week 43 the company purchased 23,550 shares at an average price of NOK 10 under "
                                 "the share buy-back program."})
        self.assertTrue(t["noise"])
        self.assertIsNotNone(t["noise_reason"])


def _buys(rows):
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["published"], utc=True)
    df["noise"], df["direction"] = False, 1
    return df.sort_values("ts").reset_index(drop=True)


class TestInsiderFlags(unittest.TestCase):
    def test_flags(self):
        rows = [
            {"id": "a", "ticker": "A.OL", "published": "2020-01-10T08:00:00Z", "person": "Kari Nordmann"},
            {"id": "b", "ticker": "A.OL", "published": "2021-03-01T08:00:00Z", "person": "Ola Nordmann"},
            {"id": "c", "ticker": "A.OL", "published": "2021-03-05T08:00:00Z", "person": "Per Hansen"},
            {"id": "d", "ticker": "A.OL", "published": "2021-03-06T08:00:00Z", "person": "Per Hansen"},
            {"id": "e", "ticker": "B.OL", "published": "2020-05-04T08:00:00Z", "person": "Lise Berg"},
            {"id": "f", "ticker": "B.OL", "published": "2021-05-04T08:00:00Z", "person": "Lise Berg"},
            {"id": "g", "ticker": "B.OL", "published": "2022-05-04T08:00:00Z", "person": "Lise Berg"},
            {"id": "h", "ticker": "B.OL", "published": "2023-05-10T08:00:00Z", "person": "Lise Berg"},
            {"id": "i", "ticker": "B.OL", "published": "2023-09-10T08:00:00Z", "person": "Lise Berg"},
        ]
        df = insider2.add_flags(_buys(rows)).set_index("id")
        self.assertFalse(df.at["a", "forste_paa_aar"])           # ingen hel års historikk ennå
        self.assertTrue(df.at["b", "forste_paa_aar"])            # > 365 d siden forrige kjøp i A
        self.assertFalse(df.at["c", "forste_paa_aar"])
        self.assertTrue(df.at["c", "klynge"])                    # Ola + Per innen 10 dager
        self.assertTrue(df.at["d", "klynge"])
        self.assertFalse(df.at["b", "klynge"])                   # bare Ola
        self.assertIsNone(df.at["f", "utenfor_rutine"])          # mangler 3 års historikk
        self.assertFalse(df.at["h", "utenfor_rutine"])           # mai i 2020, 2021, 2022 -> rutine
        self.assertTrue(df.at["i", "utenfor_rutine"])            # september -> ikke rutine
        self.assertEqual(int(df.at["c", "score"]), 1)


class TestHerd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        df, self.cal = make_prices(n_tickers=3, days=120, seed=4)
        # T00 stiger 15 % på dag 80
        m = (df["ticker"] == "T00.OL") & (df["date"] >= self.cal[80].date().isoformat())
        for c in ("open", "high", "low", "close", "adj_close"):
            df.loc[m, c] *= 1.15
        df.loc[(df["ticker"] == "T00.OL") & (df["date"] == self.cal[80].date().isoformat()), "open"] /= 1.15
        path = os.path.join(self.tmp, "p.csv")
        df.to_csv(path, index=False)
        self.panel = load_panel(price_csv=path, use_archive=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def counts(self, spike_posts):
        c = pd.DataFrame(20.0, index=self.panel.cal, columns=["T00.OL", "T01.OL", "T02.OL"])
        c.iloc[80, 0] = spike_posts
        return c

    def test_spike_needs_posts_and_price(self):
        s = herd.find_spikes(self.counts(200), self.panel)
        self.assertEqual(list(s["i"]), [80])
        self.assertEqual(len(herd.find_spikes(self.counts(30), self.panel)), 0)  # for få innlegg

    def test_shadow_block_and_tighten(self):
        spikes = herd.find_spikes(self.counts(200), self.panel)
        trades = {"ticker": np.array(["T00.OL", "T00.OL", "T01.OL"]), "i": np.array([83, 70, 83]),
                  "j": np.array([103, 90, 103]), "net": np.array([0.01, 0.02, 0.03]),
                  "cost": np.array([0.01, 0.01, 0.01]), "direction": np.array([1, 1, 1])}
        sh = herd.shadow_filter(trades, spikes, self.panel)
        self.assertEqual(list(sh["blocked"]), [True, False, False])
        self.assertEqual(list(sh["tightened"]), [False, True, False])
        self.assertNotAlmostEqual(sh.loc[1, "net_tight"], 0.02)


class TestAttention(unittest.TestCase):
    def test_busy_threshold_uses_only_past(self):
        cal = pd.bdate_range("2024-01-01", periods=300)
        t0 = np.r_[np.repeat(np.arange(0, 290, 10), 2), np.repeat([295], 12)]
        rep = pd.DataFrame({"t0": t0})
        busy = busy_days(rep, cal)
        self.assertTrue(busy.iloc[295])
        self.assertFalse(busy.iloc[10])        # for lite historikk til å si noe

    def test_dividend_month_signal_is_month_before(self):
        sig = predicted_dividend_signals({("A.OL", "2023-05")}, "2026-12")
        self.assertEqual(sig.iloc[0]["published"], "2024-04-30")

    def test_repair_after_t0_is_not_used(self):
        cal = pd.bdate_range("2024-03-01", periods=30)
        msgs = pd.DataFrame({
            "issuer": ["A", "A", "B", "B"],
            "title": ["A ASA: Private placement successfully completed", "A ASA: Subsequent offering",
                      "B ASA: Private placement successfully completed", "B ASA: update"],
            "category": "", "body": ["", "", "The board will consider a subsequent offering.", ""],
            "ts": pd.to_datetime(["2024-03-05T06:00Z", "2024-03-12T06:00Z", "2024-03-05T06:00Z",
                                  "2024-03-06T06:00Z"], utc=True)})
        pl = placement_events(msgs, {"A": "A.OL", "B": "B.OL"}, cal).set_index("ticker")
        self.assertFalse(pl.at["A.OL", "reparasjon"])   # varslet en uke senere -> ikke kjent ved t0
        self.assertTrue(pl.at["B.OL", "reparasjon"])


class TestTimingAndSlippage(unittest.TestCase):
    def test_old_timing(self):
        self.assertTrue(old_timing("2024-03-04T07:00:00Z").startswith("2024-03-04T16:30"))   # mandag morgen
        self.assertTrue(old_timing("2024-03-08T17:00:00Z").startswith("2024-03-11T16:30"))   # fredag kveld

    def test_paper_slippage(self):
        cal = pd.bdate_range("2024-03-01", periods=40)
        opn = pd.DataFrame({"A.OL": 100.0, "_benchmark": 50.0}, index=cal)
        raw = pd.DataFrame({"A.OL": 102.0}, index=cal)
        sig = pd.DataFrame([{"id": "1", "published": "2024-03-04T07:00:00Z", "ticker": "A.OL", "issuer_name": "A",
                             "role": "CEO", "value_nok": 1e6, "title": "t", "price": 100.0}])
        tr = run_trades(sig, opn, 5, raw_open=raw)
        self.assertAlmostEqual(tr[0]["entry_vs_insider"], 0.02)


if __name__ == "__main__":
    unittest.main()
