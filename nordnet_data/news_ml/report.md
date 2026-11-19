# Nyhets-ML: paper trading-backtest

Generert 2026-11-19T23:14 UTC · 120 aksjer · 39020 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-18

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +22.2 % | +21.0 % | +74.3 % |
| Årlig (CAGR) | +4.1 % | +3.9 % | +11.8 % |
| Største fall | -31.5 % | -5.8 % | -16.1 % |
| Sharpe | 0.32 | 0.80 | 0.86 |
| Handler | 973 | 57 | – |
| Treffrate | +49.5 % | +54.4 % | – |

**Tilfeldighetstest:** 45.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +17.6 %).

**AUC ut-av-utvalget:** 0.497 (0,50 = mynt­kast) · **IC:** 0.010 (t = 2.6)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Kursreaksjon på forrige rapport: +0.0047
- Avkastning 120 d: +0.0037
- Omsetning (log): +0.0028
- Kursreaksjon på kontrakter 90 d: +0.0027
- Avkastning 60 d: +0.0024
- Innsidekjøp 90 d: +0.0021
- Avkastning 5 d: +0.0020
- Oppkjøp/fusjon 90 d: +0.0017
- Meravkastning 60 d: +0.0015
- Tilbakekjøp 90 d: +0.0015

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-18 (58 handelsdager, 48 med fasit = ca. 4.8 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.003 | -0.044 | 0.234 |
| Forum-oppmerksomhet mot normalt | 0.001 | -0.0 | 0.998 |
| Sentiment 5 d | 0.044 | -0.026 | 0.472 |
| Sentiment 20 d | 0.022 | 0.032 | 0.436 |
| Stemningen snur (5 d mot 20 d) | 0.047 | -0.024 | 0.468 |
| Forum positivt mens kursen faller | None | -0.01 | 0.754 |
| Andel nyhet/analyse-innlegg | 0.02 | -0.022 | 0.49 |
| Modellscore (uten forum) | -0.091 | -0.019 | 0.634 |
| Kombinert (modell + forum) | -0.191 | -0.019 | 0.606 |

Paper trading i perioden: modell alene +0.3 % (40 handler), modell + forum -5.1 % (40 handler), OSEBX -2.1 %. Tilfeldig median -3.0 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
