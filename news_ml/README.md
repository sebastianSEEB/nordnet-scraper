# Nyhets-ML: paper trading-backtest

Kan ekte børsmeldinger + kursdata si hvilke aksjer som slår OSEBX de neste 10 handelsdagene?

```
Newsweb-børsmeldinger ─┐
                       ├─> ~38 features per aksje per dag ─> gradient boosting (walk-forward) ─> sannsynlighet
Yahoo-kurser (2019→) ──┘                                                                          │
                     paper trading: kjøp de 3 beste over 55 % ved neste åpning, hold 10 dager, maks 8 posisjoner
```

## Signalene (inspirert av Kongsberg Q3 2026)

- **Kontrakter**: antall, verdi tolket fra teksten, verdi siden forrige kvartalsrapport / markedsverdi
- **Kursreaksjon på kontrakter**: falt aksjen da gode nyheter kom? (ikke priset inn)
- **Innsidehandel**: kjøp/salg fra meldepliktige handler
- **Tilbakekjøp, emisjoner, oppkjøp, guiding**
- **Kvartalsrapport**: dager siden / til ventet rapport, reaksjon på forrige rapport
- **Teknisk**: SMA50/200, Bollinger %B, RSI, momentum, volatilitet, fall fra topp, volum
- **Marked**: OSEBX-trend og -volatilitet

## Forum-tillegget (`forum.py`)

Bruker forum-innleggene fra scraperen og Haiku-scorene (`nordnet_data/sentiment/scores.jsonl`):
sentiment 5 og 20 dager, stemningsskifte, oppmerksomhet mot normalt, andel nyhet/analyse-innlegg,
og «forum positivt mens kursen har falt». Innlegg teller bare hvis de er skrevet før 16:00.

Siden forumdata bare finnes fra slutten av august 2026, testes tillegget for seg i den perioden:

- korrelasjon samme dag (reagerer forumet?) mot neste 10 dager (forutsier det?), med tilfeldighetstest
  der hvilken aksje forum-dataene hører til stokkes
- paper trading: modell alene mot modell + forum (60/40-vekting bestemt på forhånd), pluss tilfeldige porteføljer
- to live paper-porteføljer side om side fra 30.10.2026 (`paper_live.json` og `paper_live_forum.json`)

Feiler scoringen (f.eks. tom API-kreditt), står feilen i `nordnet_data/sentiment/score_status.json`
og øverst i dashboardet.

## Ærlighetsregler

- Informasjon må være kjent ved børsslutt; handel skjer neste dags åpning. Meldinger etter 16:20 teller neste dag.
- Modellen trenes på nytt hver måned, kun på data før måneden, med 10 dagers karantene.
- 0,2 % kostnad per kjøp og per salg (kurtasje + glidning).
- Sammenlignes med OSEBX og 300 tilfeldige porteføljer som handler like ofte.
- Handelsreglene (55 %, 3 per dag, 8 plasser, 10 dager) ble satt før resultatene ble sett.
- Testet på syntetiske data: et plantet signal blir funnet, rene tilfeldige data gir ingen fordel.

## Filer

| Fil | Hva |
|---|---|
| `fetch_news.py` | Børsmeldinger fra Newsweb, inkrementelt, tekst for kontrakter/innside/rapporter |
| `fetch_prices_long.py` | Kurser fra 2019 + OSEBX (lagres ikke i repoet, hentes hver kjøring) |
| `model_backtest.py` | Features, walk-forward, backtest, baselines, live paper-portefølje |
| `../nordnet_data/news_ml/results.json` | Alt dashboardet viser |
| `../nordnet_data/news_ml/report.md` | Sammendrag, lesbart på GitHub |
| `../nordnet_data/news_ml/paper_live.json` | Fremadrettet paper-portefølje (startet 29.10.2026) |

Kjører automatisk hver hverdag etter børsslutt (`.github/workflows/news_ml.yml`).

## Begrensninger

Universet er dagens watchlist (overlevelsesskjevhet), markedsverdi bakover bruker dagens aksjeantall,
kontraktsverdier er tolket fra tekst med faste valutakurser, og rapportdato er estimert. Forskning, ikke investeringsråd.
