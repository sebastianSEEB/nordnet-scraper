# Nyhets-ML: paper trading-backtest

Generert 2026-11-24T03:04 UTC · 120 aksjer · 39077 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-20

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | -6.3 % | +24.3 % | +71.3 % |
| Årlig (CAGR) | -1.3 % | +4.5 % | +11.4 % |
| Største fall | -42.7 % | -5.8 % | -16.1 % |
| Sharpe | 0.02 | 0.89 | 0.83 |
| Handler | 968 | 57 | – |
| Treffrate | +49.2 % | +54.4 % | – |

**Tilfeldighetstest:** 75.0 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +11.8 %).

**AUC ut-av-utvalget:** 0.498 (0,50 = mynt­kast) · **IC:** 0.010 (t = 2.7)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Kursreaksjon på forrige rapport: +0.0070
- Avkastning 120 d: +0.0045
- Omsetning (log): +0.0027
- Oppkjøp/fusjon 90 d: +0.0024
- Volum-z (20 d mot 60 d): +0.0023
- Meravkastning 60 d: +0.0021
- Dager siden kvartalsrapport: +0.0021
- Rang volatilitet: +0.0020
- Avkastning 5 d: +0.0015
- Kursreaksjon på kontrakter 90 d: +0.0015

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-20 (60 handelsdager, 50 med fasit = ca. 5.0 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | -0.0 | -0.053 | 0.156 |
| Forum-oppmerksomhet mot normalt | 0.004 | -0.004 | 0.904 |
| Sentiment 5 d | 0.045 | -0.018 | 0.596 |
| Sentiment 20 d | 0.021 | 0.038 | 0.344 |
| Stemningen snur (5 d mot 20 d) | 0.049 | -0.02 | 0.528 |
| Forum positivt mens kursen faller | None | 0.002 | 0.938 |
| Andel nyhet/analyse-innlegg | 0.019 | -0.023 | 0.48 |
| Modellscore (uten forum) | -0.101 | -0.005 | 0.872 |
| Kombinert (modell + forum) | -0.199 | -0.005 | 0.874 |

Paper trading i perioden: modell alene -3.0 % (40 handler), modell + forum -7.5 % (40 handler), OSEBX -3.8 %. Tilfeldig median -4.9 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
