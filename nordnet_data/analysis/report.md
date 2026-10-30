# Forum-sentiment mot avkastning

Generert 2026-10-30 15:25 UTC · 22,786 scorede innlegg · 2,847 aksje-dager · 115 aksjer · 2026-08-27 → 2026-10-21 (40 handelsdager) · marked: OSEBX

## Konklusjon

Sentimentet henger mye tettere sammen med samme dags kurs (0.126) enn neste dags (0.013) – forumet reagerer mest på bevegelser som allerede har skjedd. Neste-dags-sammenhengen (IC 0.016) er ikke statistisk skillbar fra flaks (p = 0.410). Ingen modell slår «gjett 0» på ukjente data ennå – det vanligste utfallet med lite data. Med 40 handelsdager er alt dette foreløpig; ca. 6–12 måneder data trengs før konklusjonene blir solide.

## 1. Reagerer forumet, eller forutsier det?

| Sammenheng | Korrelasjon (Spearman) | p-verdi | n |
|---|---|---|---|
| Sentiment ↔ meravkastning samme dag | 0.126 | 0.000 | 2,846 |
| Sentiment → meravkastning neste dag | 0.013 | 0.481 | 2,847 |
| Sentiment → meravkastning neste 5 dager* | -0.008 | 0.689 | 2,847 |

*5-dagers vinduer overlapper, så p-verdien der er for optimistisk.

![Sentiment-kvintiler](sentiment_quintiles.png)

## 2. Tverrsnitts-IC og tilfeldighetstest

Snitt daglig IC: **0.016** (t = 0.85, 40 dager, positiv 60 % av dagene).
Tilfeldighetstest (2000 stokkinger): p = **0.410**. Stokkede data gir |IC| over 0.039 i 5 % av tilfellene.

IC over 0,02–0,03 som holder seg over tid regnes som interessant i kvant-verdenen. p under 0,05 betyr at sammenhengen sjelden oppstår av ren flaks.

![IC over tid](ic_over_time.png)

## 3. Modeller – ut-av-utvalget (walk-forward)

| Modell | MAE | RMSE | R² mot «gjett 0» | Treff på retning | IC | Long–short per dag |
|---|---|---|---|---|---|---|
| Gjett 0 (nullmodell) | 1.61 % | 2.65 % | 0.0000 | – | – | – |
| Gjett snittet | 1.61 % | 2.65 % | -0.0016 | 50.0 % | – | – |
| Lineær: kun snitt-sentiment | 1.61 % | 2.65 % | -0.0019 | 49.8 % | -0.003 | 0.156 % |
| Ridge: alle features | 1.62 % | 2.67 % | -0.0208 | 51.3 % | 0.019 | -0.101 % |
| Gradient boosting (grunne trær) | 1.66 % | 2.70 % | -0.0457 | 50.3 % | 0.005 | 0.015 % |

R² over 0 betyr at modellen bommer mindre enn å bare gjette 0 % meravkastning. Med daglige aksjeavkastninger er selv 0,005 bra – de fleste ekte signaler er svake.

![Feil per uke](model_errors.png)

### Overtilpasning: treningsdata vs. ukjente data

| Modell | R² på treningsdata | R² ut-av-utvalget |
|---|---|---|
| Lineær: kun snitt-sentiment | 0.0002 | -0.0019 |
| Ridge: alle features | 0.0090 | -0.0208 |
| Gradient boosting (grunne trær) | 0.1046 | -0.0457 |

Stort gap = modellen har lært støy i treningsdataene som ikke gjentar seg.

## Kjente svakheter

- Scraperen ser bare de ~10 nyeste innleggene per aksje per kjøring, og GitHub hopper over noen timer. Travle dager er derfor underrepresentert.
- Tidspunkt er estimert fra «for N t siden» (presisjon ~1 time, «for N døgn siden» ~1 døgn). Vi bruker seneste mulige tidspunkt, så signaler kan komme en dag for sent, aldri for tidlig.
- Meravkastning = aksje minus indeks (ingen beta-justering). Aksjer med høy beta ser bedre ut i stigende marked.
- Kurser fra Yahoo Finance; noen småaksjer kan mangle eller ha hull.
- Ingen handelskostnader i long–short-tallet. Spread i småaksjer kan alene spise et svakt signal.
- Sentiment er scoret av en språkmodell – den kan feiltolke ironi og forum-slang.

_Dette er en analyse av historiske sammenhenger, ikke en kjøps- eller salgsanbefaling._
