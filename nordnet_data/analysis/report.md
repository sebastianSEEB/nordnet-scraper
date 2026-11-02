# Forum-sentiment mot avkastning

Generert 2026-11-02 23:16 UTC · 28,532 scorede innlegg · 3,260 aksje-dager · 115 aksjer · 2026-08-27 → 2026-10-29 (46 handelsdager) · marked: OSEBX

## Konklusjon

Sentimentet henger mye tettere sammen med samme dags kurs (0.128) enn neste dags (0.008) – forumet reagerer mest på bevegelser som allerede har skjedd. Neste-dags-sammenhengen (IC 0.003) er ikke statistisk skillbar fra flaks (p = 0.848). Ingen modell slår «gjett 0» på ukjente data ennå – det vanligste utfallet med lite data. Med 46 handelsdager er alt dette foreløpig; ca. 6–12 måneder data trengs før konklusjonene blir solide.

## 1. Reagerer forumet, eller forutsier det?

| Sammenheng | Korrelasjon (Spearman) | p-verdi | n |
|---|---|---|---|
| Sentiment ↔ meravkastning samme dag | 0.128 | 0.000 | 3,259 |
| Sentiment → meravkastning neste dag | 0.008 | 0.644 | 3,260 |
| Sentiment → meravkastning neste 5 dager* | -0.015 | 0.415 | 3,016 |

*5-dagers vinduer overlapper, så p-verdien der er for optimistisk.

![Sentiment-kvintiler](sentiment_quintiles.png)

## 2. Tverrsnitts-IC og tilfeldighetstest

Snitt daglig IC: **0.003** (t = 0.20, 46 dager, positiv 52 % av dagene).
Tilfeldighetstest (2000 stokkinger): p = **0.848**. Stokkede data gir |IC| over 0.035 i 5 % av tilfellene.

IC over 0,02–0,03 som holder seg over tid regnes som interessant i kvant-verdenen. p under 0,05 betyr at sammenhengen sjelden oppstår av ren flaks.

![IC over tid](ic_over_time.png)

## 3. Modeller – ut-av-utvalget (walk-forward)

| Modell | MAE | RMSE | R² mot «gjett 0» | Treff på retning | IC | Long–short per dag |
|---|---|---|---|---|---|---|
| Gjett 0 (nullmodell) | 1.64 % | 2.67 % | 0.0000 | – | – | – |
| Gjett snittet | 1.64 % | 2.67 % | -0.0011 | 50.8 % | – | – |
| Lineær: kun snitt-sentiment | 1.64 % | 2.67 % | -0.0014 | 50.6 % | -0.016 | 0.097 % |
| Ridge: alle features | 1.65 % | 2.70 % | -0.0220 | 50.2 % | 0.006 | -0.133 % |
| Gradient boosting (grunne trær) | 1.69 % | 2.74 % | -0.0485 | 50.3 % | -0.005 | -0.131 % |

R² over 0 betyr at modellen bommer mindre enn å bare gjette 0 % meravkastning. Med daglige aksjeavkastninger er selv 0,005 bra – de fleste ekte signaler er svake.

![Feil per uke](model_errors.png)

### Overtilpasning: treningsdata vs. ukjente data

| Modell | R² på treningsdata | R² ut-av-utvalget |
|---|---|---|
| Lineær: kun snitt-sentiment | 0.0005 | -0.0014 |
| Ridge: alle features | 0.0047 | -0.0220 |
| Gradient boosting (grunne trær) | 0.0833 | -0.0485 |

Stort gap = modellen har lært støy i treningsdataene som ikke gjentar seg.

## Kjente svakheter

- Scraperen ser bare de ~10 nyeste innleggene per aksje per kjøring, og GitHub hopper over noen timer. Travle dager er derfor underrepresentert.
- Tidspunkt er estimert fra «for N t siden» (presisjon ~1 time, «for N døgn siden» ~1 døgn). Vi bruker seneste mulige tidspunkt, så signaler kan komme en dag for sent, aldri for tidlig.
- Meravkastning = aksje minus indeks (ingen beta-justering). Aksjer med høy beta ser bedre ut i stigende marked.
- Kurser fra Yahoo Finance; noen småaksjer kan mangle eller ha hull.
- Ingen handelskostnader i long–short-tallet. Spread i småaksjer kan alene spise et svakt signal.
- Sentiment er scoret av en språkmodell – den kan feiltolke ironi og forum-slang.

_Dette er en analyse av historiske sammenhenger, ikke en kjøps- eller salgsanbefaling._
