# Nyhets-ML: paper trading-backtest

Generert 2026-10-29T23:56 UTC · 120 aksjer · 50786 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2022-01-03 → 2026-10-28

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +42.3 % | +16.0 % | +75.8 % |
| Årlig (CAGR) | +7.6 % | +3.1 % | +12.4 % |
| Største fall | -29.0 % | -2.5 % | -16.1 % |
| Sharpe | 0.50 | 1.02 | 0.89 |
| Handler | 944 | 38 | – |
| Treffrate | +51.6 % | +60.5 % | – |

**Tilfeldighetstest:** 22.0 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +15.7 %).

**AUC ut-av-utvalget:** 0.501 (0,50 = mynt­kast) · **IC:** 0.017 (t = 4.5)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Dager siden kvartalsrapport: +0.0047
- Avkastning 120 d: +0.0032
- Avkastning 60 d: +0.0030
- Kursreaksjon på forrige rapport: +0.0026
- Oppkjøp/fusjon 90 d: +0.0018
- Guiding/oppdatering 30 d: +0.0015
- Fall fra 52-ukers topp: +0.0014
- Omsetning (log): +0.0014
- Emisjoner/lån 90 d: +0.0009
- Rang avkastning 20 d: +0.0009

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
