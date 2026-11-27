# Nyhets-ML: paper trading-backtest

Generert 2026-11-27T00:48 UTC · 119 aksjer · 39167 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-25

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +46.1 % | +34.8 % | +70.6 % |
| Årlig (CAGR) | +7.9 % | +6.2 % | +11.3 % |
| Største fall | -30.4 % | -5.8 % | -16.1 % |
| Sharpe | 0.51 | 0.99 | 0.82 |
| Handler | 977 | 58 | – |
| Treffrate | +51.8 % | +55.2 % | – |

**Tilfeldighetstest:** 18.7 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +13.5 %).

**AUC ut-av-utvalget:** 0.500 (0,50 = mynt­kast) · **IC:** 0.018 (t = 4.9)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Kursreaksjon på forrige rapport: +0.0059
- Kursreaksjon på kontrakter 90 d: +0.0045
- Avkastning 60 d: +0.0039
- Omsetning (log): +0.0034
- OSEBX volatilitet: +0.0034
- Avkastning 5 d: +0.0030
- Volum-z (20 d mot 60 d): +0.0025
- Rang avkastning 60 d: +0.0024
- Rang volatilitet: +0.0023
- Tilbakekjøp 90 d: +0.0022

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-25 (63 handelsdager, 53 med fasit = ca. 5.3 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | -0.003 | -0.065 | 0.09 |
| Forum-oppmerksomhet mot normalt | -0.002 | -0.011 | 0.726 |
| Sentiment 5 d | 0.045 | -0.014 | 0.652 |
| Sentiment 20 d | 0.021 | 0.04 | 0.312 |
| Stemningen snur (5 d mot 20 d) | 0.048 | -0.017 | 0.604 |
| Forum positivt mens kursen faller | None | 0.016 | 0.608 |
| Andel nyhet/analyse-innlegg | 0.023 | -0.017 | 0.584 |
| Modellscore (uten forum) | -0.108 | -0.023 | 0.508 |
| Kombinert (modell + forum) | -0.207 | -0.011 | 0.774 |

Paper trading i perioden: modell alene -7.5 % (45 handler), modell + forum -11.4 % (48 handler), OSEBX -4.2 %. Tilfeldig median -6.3 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
