# Forum-sentiment mot avkastning

Generert 2026-11-17 23:11 UTC · 35,171 scorede innlegg · 4,012 aksje-dager · 117 aksjer · 2026-08-27 → 2026-11-13 (57 handelsdager) · marked: OSEBX

## Konklusjon

Sentimentet henger mye tettere sammen med samme dags kurs (0.122) enn neste dags (0.013) – forumet reagerer mest på bevegelser som allerede har skjedd. Neste-dags-sammenhengen (IC 0.011) er ikke statistisk skillbar fra flaks (p = 0.527). Ingen modell slår «gjett 0» på ukjente data ennå – det vanligste utfallet med lite data. Med 57 handelsdager er alt dette foreløpig; ca. 6–12 måneder data trengs før konklusjonene blir solide.

## 1. Reagerer forumet, eller forutsier det?

| Sammenheng | Korrelasjon (Spearman) | p-verdi | n |
|---|---|---|---|
| Sentiment ↔ meravkastning samme dag | 0.122 | 0.000 | 4,011 |
| Sentiment → meravkastning neste dag | 0.013 | 0.426 | 4,012 |
| Sentiment → meravkastning neste 5 dager* | -0.004 | 0.808 | 3,742 |

*5-dagers vinduer overlapper, så p-verdien der er for optimistisk.

![Sentiment-kvintiler](sentiment_quintiles.png)

## 2. Tverrsnitts-IC og tilfeldighetstest

Snitt daglig IC: **0.011** (t = 0.72, 57 dager, positiv 54 % av dagene).
Tilfeldighetstest (2000 stokkinger): p = **0.527**. Stokkede data gir |IC| over 0.031 i 5 % av tilfellene.

IC over 0,02–0,03 som holder seg over tid regnes som interessant i kvant-verdenen. p under 0,05 betyr at sammenhengen sjelden oppstår av ren flaks.

![IC over tid](ic_over_time.png)

## 3. Modeller – ut-av-utvalget (walk-forward)

| Modell | MAE | RMSE | R² mot «gjett 0» | Treff på retning | IC | Long–short per dag |
|---|---|---|---|---|---|---|
| Gjett 0 (nullmodell) | 1.67 % | 2.65 % | 0.0000 | – | – | – |
| Gjett snittet | 1.67 % | 2.65 % | -0.0012 | 49.8 % | – | – |
| Lineær: kun snitt-sentiment | 1.68 % | 2.65 % | -0.0016 | 49.7 % | -0.003 | 0.077 % |
| Ridge: alle features | 1.69 % | 2.67 % | -0.0208 | 49.0 % | -0.021 | -0.141 % |
| Gradient boosting (grunne trær) | 1.71 % | 2.70 % | -0.0390 | 50.4 % | 0.003 | -0.065 % |

R² over 0 betyr at modellen bommer mindre enn å bare gjette 0 % meravkastning. Med daglige aksjeavkastninger er selv 0,005 bra – de fleste ekte signaler er svake.

![Feil per uke](model_errors.png)

### Overtilpasning: treningsdata vs. ukjente data

| Modell | R² på treningsdata | R² ut-av-utvalget |
|---|---|---|
| Lineær: kun snitt-sentiment | 0.0001 | -0.0016 |
| Ridge: alle features | 0.0020 | -0.0208 |
| Gradient boosting (grunne trær) | 0.0785 | -0.0390 |

Stort gap = modellen har lært støy i treningsdataene som ikke gjentar seg.

## Kjente svakheter

- Scraperen ser bare de ~10 nyeste innleggene per aksje per kjøring, og GitHub hopper over noen timer. Travle dager er derfor underrepresentert.
- Tidspunkt er estimert fra «for N t siden» (presisjon ~1 time, «for N døgn siden» ~1 døgn). Vi bruker seneste mulige tidspunkt, så signaler kan komme en dag for sent, aldri for tidlig.
- Meravkastning = aksje minus indeks (ingen beta-justering). Aksjer med høy beta ser bedre ut i stigende marked.
- Kurser fra Yahoo Finance; noen småaksjer kan mangle eller ha hull.
- Ingen handelskostnader i long–short-tallet. Spread i småaksjer kan alene spise et svakt signal.
- Sentiment er scoret av en språkmodell – den kan feiltolke ironi og forum-slang.

_Dette er en analyse av historiske sammenhenger, ikke en kjøps- eller salgsanbefaling._
