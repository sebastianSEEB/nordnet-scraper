# Forum-sentiment mot avkastning

Generert 2026-11-05 21:37 UTC · 30,253 scorede innlegg · 3,531 aksje-dager · 117 aksjer · 2026-08-27 → 2026-11-04 (50 handelsdager) · marked: OSEBX

## Konklusjon

Sentimentet henger mye tettere sammen med samme dags kurs (0.131) enn neste dags (0.013) – forumet reagerer mest på bevegelser som allerede har skjedd. Neste-dags-sammenhengen (IC 0.009) er ikke statistisk skillbar fra flaks (p = 0.595). Ingen modell slår «gjett 0» på ukjente data ennå – det vanligste utfallet med lite data. Med 50 handelsdager er alt dette foreløpig; ca. 6–12 måneder data trengs før konklusjonene blir solide.

## 1. Reagerer forumet, eller forutsier det?

| Sammenheng | Korrelasjon (Spearman) | p-verdi | n |
|---|---|---|---|
| Sentiment ↔ meravkastning samme dag | 0.131 | 0.000 | 3,530 |
| Sentiment → meravkastning neste dag | 0.013 | 0.447 | 3,531 |
| Sentiment → meravkastning neste 5 dager* | -0.009 | 0.603 | 3,260 |

*5-dagers vinduer overlapper, så p-verdien der er for optimistisk.

![Sentiment-kvintiler](sentiment_quintiles.png)

## 2. Tverrsnitts-IC og tilfeldighetstest

Snitt daglig IC: **0.009** (t = 0.54, 50 dager, positiv 54 % av dagene).
Tilfeldighetstest (2000 stokkinger): p = **0.595**. Stokkede data gir |IC| over 0.033 i 5 % av tilfellene.

IC over 0,02–0,03 som holder seg over tid regnes som interessant i kvant-verdenen. p under 0,05 betyr at sammenhengen sjelden oppstår av ren flaks.

![IC over tid](ic_over_time.png)

## 3. Modeller – ut-av-utvalget (walk-forward)

| Modell | MAE | RMSE | R² mot «gjett 0» | Treff på retning | IC | Long–short per dag |
|---|---|---|---|---|---|---|
| Gjett 0 (nullmodell) | 1.68 % | 2.67 % | 0.0000 | – | – | – |
| Gjett snittet | 1.68 % | 2.67 % | -0.0010 | 50.2 % | – | – |
| Lineær: kun snitt-sentiment | 1.68 % | 2.67 % | -0.0013 | 50.0 % | -0.008 | 0.136 % |
| Ridge: alle features | 1.70 % | 2.70 % | -0.0218 | 49.2 % | -0.012 | -0.173 % |
| Gradient boosting (grunne trær) | 1.72 % | 2.73 % | -0.0445 | 50.2 % | -0.005 | -0.110 % |

R² over 0 betyr at modellen bommer mindre enn å bare gjette 0 % meravkastning. Med daglige aksjeavkastninger er selv 0,005 bra – de fleste ekte signaler er svake.

![Feil per uke](model_errors.png)

### Overtilpasning: treningsdata vs. ukjente data

| Modell | R² på treningsdata | R² ut-av-utvalget |
|---|---|---|
| Lineær: kun snitt-sentiment | 0.0005 | -0.0013 |
| Ridge: alle features | 0.0035 | -0.0218 |
| Gradient boosting (grunne trær) | 0.0862 | -0.0445 |

Stort gap = modellen har lært støy i treningsdataene som ikke gjentar seg.

## Kjente svakheter

- Scraperen ser bare de ~10 nyeste innleggene per aksje per kjøring, og GitHub hopper over noen timer. Travle dager er derfor underrepresentert.
- Tidspunkt er estimert fra «for N t siden» (presisjon ~1 time, «for N døgn siden» ~1 døgn). Vi bruker seneste mulige tidspunkt, så signaler kan komme en dag for sent, aldri for tidlig.
- Meravkastning = aksje minus indeks (ingen beta-justering). Aksjer med høy beta ser bedre ut i stigende marked.
- Kurser fra Yahoo Finance; noen småaksjer kan mangle eller ha hull.
- Ingen handelskostnader i long–short-tallet. Spread i småaksjer kan alene spise et svakt signal.
- Sentiment er scoret av en språkmodell – den kan feiltolke ironi og forum-slang.

_Dette er en analyse av historiske sammenhenger, ikke en kjøps- eller salgsanbefaling._
