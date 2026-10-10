# Forum-sentiment mot avkastning

Generert 2026-10-10 01:17 UTC · 1,108 scorede innlegg · 298 aksje-dager · 85 aksjer · 2026-08-27 → 2026-10-07 (30 handelsdager) · marked: OSEBX

## Konklusjon

Samme dag: 0.046, neste dag: -0.039. Neste-dags-sammenhengen (IC -0.062) er ikke statistisk skillbar fra flaks (p = 0.333). Ingen modell slår «gjett 0» på ukjente data ennå – det vanligste utfallet med lite data. Med 30 handelsdager er alt dette foreløpig; ca. 6–12 måneder data trengs før konklusjonene blir solide.

## 1. Reagerer forumet, eller forutsier det?

| Sammenheng | Korrelasjon (Spearman) | p-verdi | n |
|---|---|---|---|
| Sentiment ↔ meravkastning samme dag | 0.046 | 0.434 | 297 |
| Sentiment → meravkastning neste dag | -0.039 | 0.503 | 298 |
| Sentiment → meravkastning neste 5 dager* | -0.018 | 0.774 | 250 |

*5-dagers vinduer overlapper, så p-verdien der er for optimistisk.

![Sentiment-kvintiler](sentiment_quintiles.png)

## 2. Tverrsnitts-IC og tilfeldighetstest

Snitt daglig IC: **-0.062** (t = -0.87, 27 dager, positiv 44 % av dagene).
Tilfeldighetstest (2000 stokkinger): p = **0.333**. Stokkede data gir |IC| over 0.125 i 5 % av tilfellene.

IC over 0,02–0,03 som holder seg over tid regnes som interessant i kvant-verdenen. p under 0,05 betyr at sammenhengen sjelden oppstår av ren flaks.

![IC over tid](ic_over_time.png)

## 3. Modeller – ut-av-utvalget (walk-forward)

| Modell | MAE | RMSE | R² mot «gjett 0» | Treff på retning | IC | Long–short per dag |
|---|---|---|---|---|---|---|
| Gjett 0 (nullmodell) | 2.01 % | 3.99 % | 0.0000 | – | – | – |
| Gjett snittet | 2.01 % | 4.00 % | -0.0066 | 50.3 % | – | – |
| Lineær: kun snitt-sentiment | 2.01 % | 4.01 % | -0.0093 | 51.3 % | 0.077 | 0.136 % |
| Ridge: alle features | 2.05 % | 4.03 % | -0.0192 | 44.7 % | 0.051 | 0.391 % |
| Gradient boosting (grunne trær) | 2.20 % | 4.15 % | -0.0809 | 45.7 % | -0.118 | -0.830 % |

R² over 0 betyr at modellen bommer mindre enn å bare gjette 0 % meravkastning. Med daglige aksjeavkastninger er selv 0,005 bra – de fleste ekte signaler er svake.

![Feil per uke](model_errors.png)

### Overtilpasning: treningsdata vs. ukjente data

| Modell | R² på treningsdata | R² ut-av-utvalget |
|---|---|---|
| Lineær: kun snitt-sentiment | 0.0013 | -0.0093 |
| Ridge: alle features | 0.0186 | -0.0192 |
| Gradient boosting (grunne trær) | 0.2344 | -0.0809 |

Stort gap = modellen har lært støy i treningsdataene som ikke gjentar seg.

## Kjente svakheter

- Scraperen ser bare de ~10 nyeste innleggene per aksje per kjøring, og GitHub hopper over noen timer. Travle dager er derfor underrepresentert.
- Tidspunkt er estimert fra «for N t siden» (presisjon ~1 time, «for N døgn siden» ~1 døgn). Vi bruker seneste mulige tidspunkt, så signaler kan komme en dag for sent, aldri for tidlig.
- Meravkastning = aksje minus indeks (ingen beta-justering). Aksjer med høy beta ser bedre ut i stigende marked.
- Kurser fra Yahoo Finance; noen småaksjer kan mangle eller ha hull.
- Ingen handelskostnader i long–short-tallet. Spread i småaksjer kan alene spise et svakt signal.
- Sentiment er scoret av en språkmodell – den kan feiltolke ironi og forum-slang.

_Dette er en analyse av historiske sammenhenger, ikke en kjøps- eller salgsanbefaling._
