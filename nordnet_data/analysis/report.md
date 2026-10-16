# Forum-sentiment mot avkastning

Generert 2026-10-16 19:00 UTC · 21,267 scorede innlegg · 2,584 aksje-dager · 113 aksjer · 2026-08-27 → 2026-10-15 (36 handelsdager) · marked: OSEBX

## Konklusjon

Sentimentet henger mye tettere sammen med samme dags kurs (0.136) enn neste dags (0.007) – forumet reagerer mest på bevegelser som allerede har skjedd. Neste-dags-sammenhengen (IC 0.008) er ikke statistisk skillbar fra flaks (p = 0.673). Ingen modell slår «gjett 0» på ukjente data ennå – det vanligste utfallet med lite data. Med 36 handelsdager er alt dette foreløpig; ca. 6–12 måneder data trengs før konklusjonene blir solide.

## 1. Reagerer forumet, eller forutsier det?

| Sammenheng | Korrelasjon (Spearman) | p-verdi | n |
|---|---|---|---|
| Sentiment ↔ meravkastning samme dag | 0.136 | 0.000 | 2,583 |
| Sentiment → meravkastning neste dag | 0.007 | 0.732 | 2,584 |
| Sentiment → meravkastning neste 5 dager* | -0.002 | 0.926 | 2,288 |

*5-dagers vinduer overlapper, så p-verdien der er for optimistisk.

![Sentiment-kvintiler](sentiment_quintiles.png)

## 2. Tverrsnitts-IC og tilfeldighetstest

Snitt daglig IC: **0.008** (t = 0.40, 36 dager, positiv 58 % av dagene).
Tilfeldighetstest (2000 stokkinger): p = **0.673**. Stokkede data gir |IC| over 0.040 i 5 % av tilfellene.

IC over 0,02–0,03 som holder seg over tid regnes som interessant i kvant-verdenen. p under 0,05 betyr at sammenhengen sjelden oppstår av ren flaks.

![IC over tid](ic_over_time.png)

## 3. Modeller – ut-av-utvalget (walk-forward)

| Modell | MAE | RMSE | R² mot «gjett 0» | Treff på retning | IC | Long–short per dag |
|---|---|---|---|---|---|---|
| Gjett 0 (nullmodell) | 1.63 % | 2.67 % | 0.0000 | – | – | – |
| Gjett snittet | 1.63 % | 2.67 % | -0.0018 | 49.2 % | – | – |
| Lineær: kun snitt-sentiment | 1.63 % | 2.67 % | -0.0022 | 48.7 % | -0.017 | 0.152 % |
| Ridge: alle features | 1.64 % | 2.69 % | -0.0170 | 51.1 % | 0.017 | -0.123 % |
| Gradient boosting (grunne trær) | 1.68 % | 2.73 % | -0.0448 | 50.5 % | -0.003 | -0.071 % |

R² over 0 betyr at modellen bommer mindre enn å bare gjette 0 % meravkastning. Med daglige aksjeavkastninger er selv 0,005 bra – de fleste ekte signaler er svake.

![Feil per uke](model_errors.png)

### Overtilpasning: treningsdata vs. ukjente data

| Modell | R² på treningsdata | R² ut-av-utvalget |
|---|---|---|
| Lineær: kun snitt-sentiment | 0.0002 | -0.0022 |
| Ridge: alle features | 0.0144 | -0.0170 |
| Gradient boosting (grunne trær) | 0.1121 | -0.0448 |

Stort gap = modellen har lært støy i treningsdataene som ikke gjentar seg.

## Kjente svakheter

- Scraperen ser bare de ~10 nyeste innleggene per aksje per kjøring, og GitHub hopper over noen timer. Travle dager er derfor underrepresentert.
- Tidspunkt er estimert fra «for N t siden» (presisjon ~1 time, «for N døgn siden» ~1 døgn). Vi bruker seneste mulige tidspunkt, så signaler kan komme en dag for sent, aldri for tidlig.
- Meravkastning = aksje minus indeks (ingen beta-justering). Aksjer med høy beta ser bedre ut i stigende marked.
- Kurser fra Yahoo Finance; noen småaksjer kan mangle eller ha hull.
- Ingen handelskostnader i long–short-tallet. Spread i småaksjer kan alene spise et svakt signal.
- Sentiment er scoret av en språkmodell – den kan feiltolke ironi og forum-slang.

_Dette er en analyse av historiske sammenhenger, ikke en kjøps- eller salgsanbefaling._
