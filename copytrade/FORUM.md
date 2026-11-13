# Forum-signaler forover – forhåndsregistrering

Låst **13. november 2026**, samme dag som backtesten ble kjørt. Bakgrunn: [Combining Trading Signals into One Number](https://claude.ai/artifact/KT7vuVjugYJR1LqtKgqNtf).

## Spørsmålet

Gir innlegg fra brukere med mange stjerner på Nordnet Social signaler som slår OSEBX, når vi bare bruker det systemet faktisk visste da innlegget kom?

## Backtesten (13.11.2026)

`copytrade/backtest_forum.py`, innlegg 3. aug.–12. nov. 2026, inngang neste åpning etter innlegget, meravkastning mot OSEBX per handel. t er regnet på ukesnitt fordi handler overlapper i tid.

| Test | Signal | Hold | Handler | Mot OSEBX | Slo OSEBX | t (uke) |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | 3 stjerner, positivt | 5 d | 321 | +0,41 % | 51 % | 1,09 |
| T2 | 3 stjerner, positivt | 20 d | 139 | +1,50 % | 60 % | 0,74 |
| T3 | 2 stjerner, positivt | 5 d | 493 | −0,26 % | 48 % | −1,60 |
| T4 | 2 stjerner, positivt | 20 d | 178 | −0,02 % | 47 % | −0,59 |
| T5 | 0–1 stjerner, positivt (kontroll) | 5 d | 712 | −0,22 % | 48 % | −1,47 |
| T6 | 0–1 stjerner, positivt (kontroll) | 20 d | 213 | +0,17 % | 47 % | −1,56 |
| T7 | 3 stjerner, negativt | 5 d | 181 | −0,66 % | 48 % | −1,63 |
| T8 | 3 stjerner, negativt | 20 d | 87 | +0,83 % | 45 % | 0,59 |

Ingen test nådde kravet t ≥ 3. Backtesten bruker **dagens** stjerner. Stjernene belønner nylig avkastning, så 3-stjerners brukeres positive innlegg om aksjer de eier ser delvis gode ut av konstruksjon. Tallene er derfor en øvre grense.

## Regler forover (endres ikke)

| Del | Låst valg |
| --- | --- |
| Tester | De samme 8 som over. Alle rapporteres; ingen legges til, fjernes eller byttes. |
| Hvilke innlegg | Innlegg postet etter oppstart (`forum_started_at` i `ledger.json`) i tråder for aksjer i watchlisten, med sentiment fra en modell (ikke regel-scoring). |
| Frysing | Når `paper.py` ser et scoret innlegg første gang, lagres brukerens stjerner fra siste profilsjekk og sentimentet i `forum_signals.jsonl`. Filen får bare nye linjer og endres aldri. Brukere uten profilsjekk på det tidspunktet lagres uten stjerner og teller aldri. |
| Signal | Positivt: sentiment ≥ 0,3. Negativt: sentiment ≤ −0,3. |
| Inngang | Første åpning etter at systemet frøs innlegget (ikke etter selve innlegget). Da handler vi aldri på en åpning som allerede har vært. |
| Utgang | Åpning 5 eller 20 handelsdager senere. |
| Størrelse | 10 000 kr per handel. Én åpen posisjon per aksje per test. |
| Mål | Meravkastning mot OSEBX over de samme dagene. |
| Krav | Minst 100 lukkede handler, og t ≥ 3 på ukesnitt (t ≤ −3 for T7–T8, der vi venter negativ meravkastning). |
| Feiler den | Testen regnes som ikke bestått. Terskel, holdetid og grupper skal ikke justeres for å prøve igjen. |

## Kjente svakheter

- Stjernene er fra siste profilsjekk, som kan være opptil 14 dager gammel.
- Bare innlegg i tråder for aksjer i watchlisten.
- Kurtasje, spread og skatt er ikke trukket fra.
- Med 8 tester vil én av dem kunne se god ut av flaks; derfor kreves t ≥ 3.

Papirhandel, ikke investeringsråd.
