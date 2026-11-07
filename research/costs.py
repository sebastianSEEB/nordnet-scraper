"""
Kostnadsmodell for testbenken
=============================
Alt som trekkes fra en handel, per side (kjøp eller salg), som andel av beløpet:

    halv spread   anslått fra daglige høy/lav/slutt med Abdi & Ranaldo (2017):
                      S^2 = 4 * E[(c_t - eta_t) * (c_t - eta_{t+1})]
                  der c = log(slutt) og eta = (log(høy) + log(lav)) / 2.
                  Rullerende snitt per aksje, negative anslag settes til 0, så
                  gulv og tak. For lite historikk -> konservativ standardverdi.
    kurtasje      max(minstekurtasje, sats * beløp) / beløp  (Nordnet-klasse i config)
    slippage      fast påslag per side

Spread-anslaget for dag t bruker bare data som var kjent ved slutt av dag t,
og en handel på åpningen dag i bruker anslaget fra dag i-1. Ingen titting fremover.
"""

import numpy as np


def abdi_ranaldo_half_spread(close, high, low, window=60, min_obs=20, floor=0.0005, cap=0.05):
    """Halv spread (andel) per dag og aksje. Rad t = anslag kjent ved slutt av dag t.

    close/high/low: DataFrames (dato x ticker), samme justering innen hver dag.
    """
    c = np.log(close.where(close > 0))
    eta = (np.log(high.where(high > 0)) + np.log(low.where(low > 0))) / 2
    # p_t bruker eta_{t+1}, altså data fra dag t+1 -> forskyv én dag så rad t bare ser til og med dag t
    p = ((c - eta) * (c - eta.shift(-1))).shift(1)
    m = p.rolling(window, min_periods=min_obs).mean()
    s = np.sqrt((4 * m).clip(lower=0))
    hs = (s / 2).clip(lower=floor, upper=cap)
    return hs.where(m.notna())


def commission_rate(costs):
    cls = costs["fee_classes"][costs["fee_class"]]
    stake = float(costs["stake_nok"])
    fee = max(float(cls["min_nok"]), float(cls["rate"]) * stake)
    return fee / stake + float(costs.get("algo_surcharge", 0.0))


def side_cost(half_spread, costs):
    """Kostnad for én side gitt anslått halv spread (skalar eller array)."""
    hs = np.where(np.isfinite(half_spread), half_spread, costs["half_spread_default"])
    return hs + commission_rate(costs) + float(costs["slippage_per_side"])


def round_trip_cost(hs_entry, hs_exit, costs):
    return side_cost(hs_entry, costs) + side_cost(hs_exit, costs)


def describe(costs):
    """Kort tekst til rapporten."""
    cls = costs["fee_classes"][costs["fee_class"]]
    stake = f"{int(costs['stake_nok']):,}".replace(",", " ")
    return (f"kurtasjeklasse {costs['fee_class']} ({cls['rate']:.3%}, min {cls['min_nok']} kr) på "
            f"{stake} kr = {commission_rate(costs):.3%} per side; slippage "
            f"{costs['slippage_per_side']:.3%} per side; halv spread fra Abdi-Ranaldo "
            f"({costs['spread_window']} d, gulv {costs['half_spread_floor']:.2%}, tak {costs['half_spread_cap']:.0%}, "
            f"standard {costs['half_spread_default']:.2%})")
