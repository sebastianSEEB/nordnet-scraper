# Nyhets-ML: paper trading-backtest

Generert 2026-11-26T00:41 UTC · 120 aksjer · 39136 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-24

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +4.4 % | +34.7 % | +70.6 % |
| Årlig (CAGR) | +0.9 % | +6.2 % | +11.3 % |
| Største fall | -45.0 % | -5.8 % | -16.1 % |
| Sharpe | 0.14 | 0.99 | 0.82 |
| Handler | 975 | 58 | – |
| Treffrate | +48.9 % | +55.2 % | – |

**Tilfeldighetstest:** 61.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +11.7 %).

**AUC ut-av-utvalget:** 0.501 (0,50 = mynt­kast) · **IC:** 0.020 (t = 5.2)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Omsetning (log): +0.0051
- OSEBX volatilitet: +0.0049
- Kursreaksjon på forrige rapport: +0.0027
- Rang avkastning 60 d: +0.0024
- Avkastning 5 d: +0.0021
- Avkastning 120 d: +0.0020
- Tilbakekjøp 90 d: +0.0020
- Kontraktsverdi 90 d / markedsverdi: +0.0014
- Rang avkastning 20 d: +0.0011
- Volatilitet 20 d / 120 d: +0.0010

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-24 (62 handelsdager, 52 med fasit = ca. 5.2 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | -0.0 | -0.061 | 0.118 |
| Forum-oppmerksomhet mot normalt | -0.001 | -0.008 | 0.792 |
| Sentiment 5 d | 0.043 | -0.016 | 0.668 |
| Sentiment 20 d | 0.019 | 0.039 | 0.352 |
| Stemningen snur (5 d mot 20 d) | 0.049 | -0.02 | 0.564 |
| Forum positivt mens kursen faller | None | 0.015 | 0.66 |
| Andel nyhet/analyse-innlegg | 0.021 | -0.02 | 0.51 |
| Modellscore (uten forum) | -0.091 | 0.009 | 0.82 |
| Kombinert (modell + forum) | -0.193 | 0.012 | 0.742 |

Paper trading i perioden: modell alene -11.0 % (44 handler), modell + forum -11.5 % (46 handler), OSEBX -4.2 %. Tilfeldig median -5.3 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
