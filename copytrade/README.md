# Kopihandel (paper trading)

Copy-trading på papir av offentlige kilder:

1. **Innsidekjøp** fra Newsweb (allerede hentet av `news_ml/fetch_news.py`). CEO, CFO eller styreleder kjøper for minst 500 000 kr → kjøp på neste åpning, selg 20 handelsdager senere. Backtest fra 2022 + live paper trading.
2. **Stjernebrukere på Nordnet Social.** Handlene deres ligger bak innlogging, så vi henter bare stjernene (0–3, offentlig) for profilene som skriver i forumet. Et positivt innlegg fra en 3-stjerners bruker om en aksje i watchlisten = kjøp, hold 20 dager. Bare forover (stjernene er dagens, så en backtest ville sett inn i fremtiden).
3. **Kombinert (fra 13.11.2026).** Samme handler som innsidestrategien, men 15 000 kr i stedet for 10 000 når en 3-stjerners bruker har vært positiv til aksjen de siste 10 handelsdagene før inngang. Testen er om handler med stjerne-enighet slår handler uten. Reglene er låst i `KOMBINERT.md`, og testen vurderes først ved 100 lukkede handler.
4. **Forum-signaler forover (fra 13.11.2026).** De 8 testene fra backtesten av forum-innlegg (3, 2 og 0–1 stjerner; positive og negative innlegg; hold 5 og 20 dager) kjørt live på papir. Stjerner og sentiment fryses når innlegget sees, så backtestens skjevhet (dagens stjerner) forsvinner. Regler og backtest-resultater i `FORUM.md`.

| Fil | Gjør |
|---|---|
| `insiders.py` | Tolker innsidemeldinger: retning, antall, kurs, verdi, rolle, og filtrerer bort spareprogram, opsjoner, honorar o.l. |
| `stars.py` | Henter stjerner og følgere for forumprofilene (natt-workflow `copytrade_stars.yml`) |
| `paper.py` | Backtest + paper trading (innsidekjøp, stjernebrukere, kombinert og forum-signaler) → `nordnet_data/copytrade/results.json` |
| `backtest_forum.py` | Backtest av forum-innlegg fra stjernebrukere (skjev: bruker dagens stjerner) |
| `FORUM.md` | Forhåndsregistrering av forum-testene forover (låst 2026-11-13) |
| `KOMBINERT.md` | Forhåndsregistrering av den kombinerte strategien (låst 2026-11-13) |
| `dashboard.py` | → `nordnet_data/copytrade/dashboard.html` |

`paper.py` og `dashboard.py` kjører i `news_ml.yml` hver hverdag etter børsslutt, etter at kursene er hentet.

**Ærlighet i tallene:** hovedstrategien ble låst før resultatene ble sett. `ledger.json` husker når hvert signal ble sett første gang, og «ekte live» teller bare signaler etter oppstart. Kurtasje, spread og skatt er ikke trukket fra.

**Hvis stjernene ikke blir funnet:** `stars_status.json` viser treffraten, og `debug/profile_*.html` har rå sider å rette regexene i `STAR_RES` mot.
