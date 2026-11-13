# Kombinert strategi – forhåndsregistrering

Låst **13. november 2026**, før noen resultater for kombinasjonen ble sett.
Bakgrunn: [Combining Trading Signals into One Number](https://claude.ai/artifact/KT7vuVjugYJR1LqtKgqNtf).

## Spørsmålet

Gir stjerne-enighet (en 3-stjerners bruker er positiv til aksjen) høyere meravkastning på innsidekjøpene enn innsidekjøp uten slik enighet?

## Regler (endres ikke)

| Del | Låst valg |
| --- | --- |
| Handler | Nøyaktig de samme som hovedstrategien (CEO/CFO/styreleder, ≥ 500 000 kr, hold 20 handelsdager). Kombinasjonen legger aldri til handler. |
| Stjerne-enighet | Minst ett innlegg fra en 3-stjerners bruker om aksjen, sentiment ≥ 0,3 (samme regel som stjerne-strategien), publisert før åpningen vi handler på og innen de 10 siste handelsdagene. |
| Score | 1 + 0,5 × stjerne-enighet |
| Størrelse | 10 000 kr ved score 1, 15 000 kr ved score 1,5 |
| Hvilke signaler teller | Bare innsidesignaler sett første gang etter at kombinasjonen ble satt i drift (`combo_started_at` i `ledger.json`). |
| Låsing | Stjerne-enigheten for en handel lagres i `ledger.json` (`combo_flags`) første gang handelen har en inngangsdato, og endres aldri etterpå. |
| Test | Snitt meravkastning mot OSEBX for handler med enighet minus handler uten, Welch t-verdi. |
| Krav | t ≥ 3 (Harvey, Liu og Zhu), fordi én test fra en stor mengde mulige kombinasjoner trenger høyere terskel enn 2. |
| Vurdering | Først når 100 kombinerte handler er lukket. Ikke før. |
| Feiler den | Kombinasjonen droppes. Vindu, bonus og terskel skal ikke justeres for å prøve igjen. |

## Det som bevisst er utelatt

- **Sentiment fra hele forumet:** for kort historikk til å sette en vekt.
- **Multiplikasjon, divisjon og lange filterkjeder:** for få handler og for mange måter å overtilpasse.
- **Backtest:** stjernene vi har er dagens, så en backtest ville sett inn i fremtiden.

## Kjente svakheter

- Handler med stjerne-enighet er sjeldne, så testen kan ende uavklart selv ved 100 handler.
- 20-dagers handler overlapper i tid, så t-verdien er noe for optimistisk.
- Kurtasje, spread og skatt er ikke trukket fra.

Papirhandel, ikke investeringsråd.
