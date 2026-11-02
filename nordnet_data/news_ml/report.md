# Nyhets-ML: paper trading-backtest

Generert 2026-11-02T23:47 UTC · 120 aksjer · 38626 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-10-30

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +49.2 % | +15.7 % | +80.3 % |
| Årlig (CAGR) | +8.5 % | +3.0 % | +12.8 % |
| Største fall | -34.4 % | -6.1 % | -16.1 % |
| Sharpe | 0.55 | 0.68 | 0.91 |
| Handler | 962 | 62 | – |
| Treffrate | +51.6 % | +59.7 % | – |

**Tilfeldighetstest:** 19.0 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +15.7 %).

**AUC ut-av-utvalget:** 0.496 (0,50 = mynt­kast) · **IC:** 0.012 (t = 3.1)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Dager siden kvartalsrapport: +0.0056
- Kursreaksjon på forrige rapport: +0.0031
- Avkastning 60 d: +0.0027
- Kursreaksjon på kontrakter 90 d: +0.0021
- Volum-z (20 d mot 60 d): +0.0019
- Avkastning 5 d: +0.0015
- Avkastning 120 d: +0.0013
- Oppkjøp/fusjon 90 d: +0.0013
- Omsetning (log): +0.0012
- Innsidesalg 90 d: +0.0009

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-10-30 (45 handelsdager, 35 med fasit = ca. 3.5 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.022 | 0.0 | 0.988 |
| Forum-oppmerksomhet mot normalt | -0.012 | -0.019 | 0.63 |
| Sentiment 5 d | 0.038 | -0.041 | 0.334 |
| Sentiment 20 d | 0.021 | 0.034 | 0.45 |
| Stemningen snur (5 d mot 20 d) | 0.042 | -0.049 | 0.182 |
| Forum positivt mens kursen faller | None | -0.035 | 0.348 |
| Andel nyhet/analyse-innlegg | 0.027 | 0.033 | 0.384 |
| Modellscore (uten forum) | -0.091 | -0.024 | 0.604 |
| Kombinert (modell + forum) | -0.193 | -0.03 | 0.466 |

Paper trading i perioden: modell alene +2.3 % (32 handler), modell + forum -5.0 % (32 handler), OSEBX +1.3 %. Tilfeldig median -1.6 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
