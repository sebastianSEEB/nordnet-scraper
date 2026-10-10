# Forum-sentiment mot avkastning

Generert 2026-10-10 01:12 UTC · 514 scorede innlegg · 0 aksje-dager · 0 aksjer · None → None (0 handelsdager) · marked: OSEBX

## Konklusjon

For lite data til tilfeldighetstesten ennå. Ingen modell slår «gjett 0» på ukjente data ennå – det vanligste utfallet med lite data. Med 0 handelsdager er alt dette foreløpig; ca. 6–12 måneder data trengs før konklusjonene blir solide.

## 1. Reagerer forumet, eller forutsier det?

| Sammenheng | Korrelasjon (Spearman) | p-verdi | n |
|---|---|---|---|
| Sentiment ↔ meravkastning samme dag | – | – | 0 |
| Sentiment → meravkastning neste dag | – | – | 0 |
| Sentiment → meravkastning neste 5 dager* | – | – | 0 |

*5-dagers vinduer overlapper, så p-verdien der er for optimistisk.

![Sentiment-kvintiler](sentiment_quintiles.png)

## 2. Tverrsnitts-IC og tilfeldighetstest

Snitt daglig IC: **–** (t = –, 0 dager, positiv – av dagene).
Tilfeldighetstest (2000 stokkinger): p = **–**. Stokkede data gir |IC| over – i 5 % av tilfellene.

IC over 0,02–0,03 som holder seg over tid regnes som interessant i kvant-verdenen. p under 0,05 betyr at sammenhengen sjelden oppstår av ren flaks.

![IC over tid](ic_over_time.png)

## 3. Modeller – ut-av-utvalget (walk-forward)

| Modell | MAE | RMSE | R² mot «gjett 0» | Treff på retning | IC | Long–short per dag |
|---|---|---|---|---|---|---|
| Gjett 0 (nullmodell) | – | – | – | – | – | – |
| Gjett snittet | – | – | – | – | – | – |
| Lineær: kun snitt-sentiment | – | – | – | – | – | – |
| Ridge: alle features | – | – | – | – | – | – |
| Gradient boosting (grunne trær) | – | – | – | – | – | – |

R² over 0 betyr at modellen bommer mindre enn å bare gjette 0 % meravkastning. Med daglige aksjeavkastninger er selv 0,005 bra – de fleste ekte signaler er svake.

![Feil per uke](model_errors.png)

### Overtilpasning: treningsdata vs. ukjente data

| Modell | R² på treningsdata | R² ut-av-utvalget |
|---|---|---|
| Lineær: kun snitt-sentiment | – | – |
| Ridge: alle features | – | – |
| Gradient boosting (grunne trær) | – | – |

Stort gap = modellen har lært støy i treningsdataene som ikke gjentar seg.

## Kjente svakheter

- Scraperen ser bare de ~10 nyeste innleggene per aksje per kjøring, og GitHub hopper over noen timer. Travle dager er derfor underrepresentert.
- Tidspunkt er estimert fra «for N t siden» (presisjon ~1 time, «for N døgn siden» ~1 døgn). Vi bruker seneste mulige tidspunkt, så signaler kan komme en dag for sent, aldri for tidlig.
- Meravkastning = aksje minus indeks (ingen beta-justering). Aksjer med høy beta ser bedre ut i stigende marked.
- Kurser fra Yahoo Finance; noen småaksjer kan mangle eller ha hull.
- Ingen handelskostnader i long–short-tallet. Spread i småaksjer kan alene spise et svakt signal.
- Sentiment er scoret av en språkmodell – den kan feiltolke ironi og forum-slang.

_Dette er en analyse av historiske sammenhenger, ikke en kjøps- eller salgsanbefaling._
