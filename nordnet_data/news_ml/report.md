# Nyhets-ML: paper trading-backtest

Generert 2026-10-30T00:40 UTC · 120 aksjer · 38489 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2022-01-03 → 2026-10-28

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | -13.9 % | +18.2 % | +75.8 % |
| Årlig (CAGR) | -3.1 % | +3.5 % | +12.4 % |
| Største fall | -32.6 % | -4.7 % | -16.1 % |
| Sharpe | -0.08 | 0.95 | 0.89 |
| Handler | 951 | 44 | – |
| Treffrate | +49.1 % | +59.1 % | – |

**Tilfeldighetstest:** 85.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +13.2 %).

**AUC ut-av-utvalget:** 0.501 (0,50 = mynt­kast) · **IC:** 0.016 (t = 4.4)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Kursreaksjon på forrige rapport: +0.0103
- Dager siden kvartalsrapport: +0.0048
- Avkastning 120 d: +0.0042
- Kursreaksjon på kontrakter 90 d: +0.0042
- OSEBX volatilitet: +0.0037
- Avkastning 60 d: +0.0037
- Omsetning (log): +0.0022
- Avkastning 5 d: +0.0018
- Meravkastning 60 d: +0.0016
- Fall fra 52-ukers topp: +0.0016

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
