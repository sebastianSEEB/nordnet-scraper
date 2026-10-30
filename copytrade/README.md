# Kopihandel (paper trading)

Copy-trading på papir av to kilder som er offentlige:

1. **Innsidekjøp** fra Newsweb (allerede hentet av `news_ml/fetch_news.py`). CEO, CFO eller styreleder kjøper for minst 500 000 kr → kjøp på neste åpning, selg 20 handelsdager senere. Backtest fra 2022 + live paper trading.
2. **Stjernebrukere på Nordnet Social.** Handlene deres ligger bak innlogging, så vi henter bare stjernene (0–3, offentlig) for profilene som skriver i forumet. Et positivt innlegg fra en 3-stjerners bruker om en aksje i watchlisten = kjøp, hold 20 dager. Bare forover (stjernene er dagens, så en backtest ville sett inn i fremtiden).

| Fil | Gjør |
|---|---|
| `insiders.py` | Tolker innsidemeldinger: retning, antall, kurs, verdi, rolle, og filtrerer bort spareprogram, opsjoner, honorar o.l. |
| `stars.py` | Henter stjerner og følgere for forumprofilene (natt-workflow `copytrade_stars.yml`) |
| `paper.py` | Backtest + paper trading → `nordnet_data/copytrade/results.json` |
| `dashboard.py` | → `nordnet_data/copytrade/dashboard.html` |

`paper.py` og `dashboard.py` kjører i `news_ml.yml` hver hverdag etter børsslutt, etter at kursene er hentet.

**Ærlighet i tallene:** hovedstrategien ble låst før resultatene ble sett. `ledger.json` husker når hvert signal ble sett første gang, og «ekte live» teller bare signaler etter oppstart. Kurtasje, spread og skatt er ikke trukket fra.

**Hvis stjernene ikke blir funnet:** `stars_status.json` viser treffraten, og `debug/profile_*.html` har rå sider å rette regexene i `STAR_RES` mot.
