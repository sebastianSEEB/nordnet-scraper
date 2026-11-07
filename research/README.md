# research/ – testbenken (Fase 0) og Fase 1

Alle signalideer skal gjennom den samme testen før de får penger eller plass i paper trading.
Testbenken er laget for å si **nei** til tilfeldigheter, ikke for å finne noe som ser bra ut.

## Hva den gjør

Inn: en tabell med signaler – `ticker`, `published` (tidspunkt), `direction` (+1 kjøp / −1 short, standard +1), `id`.

Ut, per holdetid 1 / 5 / 20 / 60 handelsdager:

| Mål | Forklaring |
|---|---|
| Brutto | Meravkastning mot OSEBX, kjøpt på første åpning etter publisering |
| Kostnad | Halv spread inn og ut (Abdi–Ranaldo), Nordnet-kurtasje og slippage |
| Netto | Brutto minus kostnad – det er dette dommen bygger på |
| Treff | Andel handler med positivt netto |
| Klynge-t | t-verdi der hendelser i samme blokk på max(5, hold) dager telles som én klynge |
| Placebo-p | Andel tilfeldige inngangsdager i de samme aksjene som ga minst like godt netto |

I tillegg vises reaksjonen rundt publisering, CAR[0,1] og CAR[−5,−1]. Den er ikke handlebar, men er det
klassiske målet i forskningen og brukes til Gate 0.

**Bestått** krever alt dette samtidig: minst 40 hendelser, positivt netto, klynge-t over kravet og placebo-p under 0,05.

## Faste regler

- **Ingen titting fremover.** Inngang følger `entry_index` i `copytrade/paper.py`: publisert før 09:00 Oslo-tid
  gir samme dags åpning, ellers neste dags åpning. Signaler med bare dato regnes som publisert etter børsslutt.
- **Kostnader trekkes alltid.** Satser i `config.json`. Standard er kurtasjeklassen *mini* (0,15 %, minst 29 kr), som på
  10 000 kr blir 0,29 % per side. Bytt `fee_class` til `student` eller en annen klasse hvis det stemmer for kontoen.
- **Holdout er låst.** Hendelser fra `holdout_start` (2025-11-01) er skjult i vanlige kjøringer, og handler som ville
  gått ut i holdout-perioden tas ut. En idé får teste mot holdout én gang (`--holdout`). Andre forsøk stopper med feil.
- **Alle kjøringer logges** i `nordnet_data/research/test_log.jsonl`. Kravet til klynge-t er
  `max(3,0, Bonferroni-z for K ulike tester)`. Hver ny variant (nytt navn eller nye `params`) øker K og gjør kravet
  strengere for alle. Ikke juster en idé til den består – lag en ny og ta straffen.

## Bruk

```bash
# Kjør en idé (CSV med ticker, published, direction, id)
python research/harness.py --signals mine_signaler.csv --name min_ide --params '{"filter": "CEO, >= 1 mill"}'

# Én gang, når ideen er ferdig: bekreft mot holdout
python research/harness.py --signals mine_signaler.csv --name min_ide --params '{"filter": "CEO, >= 1 mill"}' --holdout
```

Rapporten havner i `nordnet_data/research/<navn>/report.md` (+ `results.json`, og `events.csv` med `--events`).

Fra Python:

```python
from research.harness import run_event_study
res = run_event_study(signaler_df, "min_ide", params={...})
```

## Gate 0

`gate0_insiders.py` kjører alle innsidekjøp fra børsmeldingene gjennom testbenken. Testbenken må gjenskape den kjente
effekten (NHH-masteroppgave: +1,14 % over [0,1]) før den får dømme nye ideer: snitt CAR[0,1] mellom 0,3 % og 3 % og
klynge-t ≥ 2. Resultatet ligger i `nordnet_data/research/gate0/` og oppdateres hver hverdag av `news_ml.yml`.

## Fase 1: raske gevinster (`phase1.py`)

Kjøres hver hverdag etter Gate 0 og skriver `nordnet_data/research/phase1/report.md` og `status.json`.

**Innsidesignal 2.0** (`copytrade/insiders.py`, `insider2.py`)
- Strengere støyfilter: selskapets eget tilbakekjøp, ansattstiftelser, aksjer tegnet i emisjoner eller børsnoteringer og
  vederlagsaksjer regnes ikke lenger som innsidekjøp (`noise_reason` sier hvorfor).
- Navnet på innsideren leses ut av meldingen når det går (ca. 8 av 10).
- Fire flagg per kjøp: første kjøp i selskapet på et år, klynge (minst 2 innsidere på 10 dager), kjøp etter fall
  (≥ 10 % under OSEBX på 20 dager) og utenfor rutine (personen pleier ikke å kjøpe i denne måneden). `score` = antall flagg.
- Paper-handlene i copytrade får `entry_vs_insider`: hvor mye dyrere vi kjøpte enn innsideren.

**Flokk-filteret** (`herd.py`): en topp er minst 10 innlegg og 4 × normalen samme dag som kursen stiger minst 5 %.
Nye kjøp blokkeres i 5 dager etter en topp, og åpne posisjoner selges neste åpning. Det kjøres i skyggemodus ved siden av
den låste strategien, og alle topper logges i `phase1/spikes.csv` med avkastningen 5 og 20 dager etter.

**Oppmerksomhet** (`news_ml/attention.py`): antall rapporter per dag (travle dager = topp 10 %), rapporter fredag etter
stengning, ventet utbyttemåned (eks utbytte samme måned i fjor) og rettede emisjoner med og uten reparasjonsemisjon.
De går inn i nyhetsmodellen bare hvis `phase1.attention_in_model` settes til `true` i `config.json`, og det skal først
gjøres når testen bak featuren har bestått.

**Gate 1** er bestått når
1. det har kommet minst 40 innsidesignaler siden paper trading startet, og ny inngang (neste åpning etter meldingen)
   slår gammel inngang (etter den daglige kjøringen) etter kostnader, og
2. kjøpene flokk-filteret blokkerer, gjør det dårligere enn kjøpene det slipper gjennom (minst 10 blokkerte).

Forumarkivet har full dekning først fra høsten 2026, så flokk-filteret kan bare vurderes fremover. Det samme gjelder
inngangstidspunktet, fordi det måles på paper-handlene. Begge deler bruker data i holdout-perioden, men bare som
overvåking. Ingen av dem logges som tester.

## Kursarkiv mot overlevelsesskjevhet

Yahoo gir bare kurser for aksjer som finnes i dag. `archive_prices.py` lagrer derfor hver dag nye rader i
`nordnet_data/price_archive/prices_ÅÅÅÅ-MM.csv` og endrer aldri en rad som allerede er lagret. Første kjøring legger inn
hele historikken Yahoo har nå (ca. 19 MB fordelt på månedsfiler). `universe_log.jsonl` logger når aksjer kommer inn i
eller forsvinner fra watchlisten, mangler hos Yahoo eller slutter å få nye kurser.

`data.py` henter automatisk aksjer fra arkivet når de mangler i dagens Yahoo-uttrekk, med riktig utbyttejustering
(kolonnen `tr` er totalavkastningen fra dagen før, regnet ut da raden ble lagret).

## Filer

| Fil | Innhold |
|---|---|
| `config.json` | Horisonter, holdout-dato, t-krav, kostnader, Gate 0-grenser |
| `data.py` | Innlesing av kurser + arkiv, felles handelskalender |
| `costs.py` | Spread-anslag og kostnad per handel |
| `harness.py` | Selve testen, logg, holdout-lås, rapport, CLI |
| `gate0_insiders.py` | Gate 0 |
| `archive_prices.py` | Kursarkiv og universlogg |
| `insider2.py` | Opportunistisk-flagg for innsidekjøp |
| `herd.py` | Flokk-filteret: topper i forumet, skyggeblokkering |
| `phase1.py` | Alle Fase 1-testene + Gate 1-status |
| `tests/` | Enhetstester på syntetiske kurser: `python -m unittest discover -s research/tests -t .` |

## Kjente begrensninger

- Spread-anslaget fra dagskurser er grovt for små, illikvide aksjer. Gulvet er 0,05 % og standardverdien 0,5 % når det
  mangler historikk.
- Kjøp på åpningen antar at ordren kommer med i åpningsauksjonen.
- Arkivet beskytter mot overlevelsesskjevhet fra nå av. Aksjer som forsvant før arkivet startet, er fortsatt borte.
