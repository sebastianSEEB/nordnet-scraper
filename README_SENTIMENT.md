# Sentiment mot avkastning

Scorer hvert forum-innlegg for sentiment, kobler det mot faktisk kursutvikling,
og tester om forumet kan forutsi noe – ærlig, på data modellene ikke har sett.

```
innlegg ──> arkiv ──> sentiment-score ──> daglig score per aksje ──> mot neste dags meravkastning ──> modeller + feil
```

## Filer

| Fil | Hva den gjør |
|---|---|
| `archive_posts.py` | Permanent arkiv over alle innlegg (`nordnet_data/archive/`). Scraperen skriver hit automatisk. Kan fylle arkivet fra git-historikken. |
| `score_sentiment.py` | Claude Haiku gir hvert innlegg sentiment (−1…+1), relevans (0…1) og kategori. Inkrementelt – scorer aldri samme innlegg to ganger. |
| `fetch_prices.py` | Daglige kurser fra Yahoo Finance + OSEBX. Feil ticker? Legg den i `ticker_overrides.json`. |
| `sentiment_analysis.py` | Bygger datasettet, korrelasjoner, IC, tilfeldighetstest og walk-forward-modeller. Skriver `nordnet_data/analysis/report.md` + figurer. |
| `sentiment_dashboard.py` | Streamlit-dashboard med alle grafene. |
| `.github/workflows/sentiment.yml` | Kjører alt hver hverdag etter børsslutt og committer resultatene. |

## Oppsett

1. Last opp filene til repoet. `ANTHROPIC_API_KEY`-hemmeligheten finnes allerede.
2. Gå til **Actions → Sentiment mot avkastning → Run workflow**. Skriv `300` i
   «Maks innlegg» for en billig testkjøring. Første kjøring bygger også arkivet
   fra hele git-historikken.
3. Sjekk `nordnet_data/prices/ticker_map.json` → `missing` for aksjer uten kurs.
4. Kjør igjen med `0` for å score resten (~18 000 innlegg, noen dollar). Deretter
   går den automatisk hver hverdag og scorer bare nye innlegg.
5. Les `nordnet_data/analysis/report.md` på GitHub (fungerer på mobil), eller
   kjør dashboardet lokalt:

```
git pull
pip install -r requirements-sentiment.txt streamlit plotly
streamlit run sentiment_dashboard.py
```

## Slik leser du resultatene

- **Samme dag vs. neste dag.** Høy sammenheng samme dag, null neste dag = forumet
  *reagerer* på kursen, det forutsier den ikke. Det er det vanligste funnet.
- **IC** (information coefficient) = rangkorrelasjon mellom dagens sentiment og
  morgendagens meravkastning, på tvers av aksjer, snittet over dager. 0,02–0,03
  som holder seg over tid er interessant. 0,1+ på få uker er nesten alltid flaks.
- **Tilfeldighetstest p.** Vi stokker sentimentet mellom aksjene 2000 ganger.
  p < 0,05 = ekte data slår nesten alle stokkede versjoner.
- **R² mot «gjett 0».** Over 0 = modellen bommer mindre enn å gjette 0 %. Med
  daglige avkastninger er 0,005 bra.
- **Treningsdata vs. ut-av-utvalget.** Hvis en modell er mye bedre på
  treningsdata enn på ukjente uker, har den pugget støy (overtilpasning).

## Viktige designvalg

- **Ingen look-ahead.** Nordnet viser «for 3 t siden» (rundet ned). Vi bruker
  *seneste* mulige tidspunkt, og innlegg teller for en handelsdag bare hvis de er
  skrevet før 16:00. Signalet kan komme en dag for sent, aldri for tidlig.
  Testet med syntetiske data: et plantet neste-dags-signal oppdages, mens
  sentiment som bare følger samme dags kurs gir null prediksjonskraft.
- **Meravkastning** = aksje minus OSEBX.
- **Walk-forward.** Modellene trenes bare på dager før hver testuke.

## Begrensninger

Scraperen ser bare ~10 innlegg per aksje per kjøring, tidspunkt har ~1 times
presisjon, og noen få ukers data er for lite til sikre konklusjoner. Rapporten
lister alle svakhetene. Dette er analyse, ikke investeringsråd.
