"""
Kjøp/salg-uttalelser i forumet fra stjernebrukere
=================================================
Nordnet viser ikke handlene til andre brukere uten innlogging, så det nærmeste
vi kommer "kjøp og selg når de gjør det" er når brukeren selv SKRIVER at hen
har kjøpt eller solgt. Denne modulen leser innleggsteksten med enkle regler
(ingen sentiment-modell) og gir:

    +1  brukeren sier hen har kjøpt / økt / gått inn
    -1  brukeren sier hen har solgt / gått ut / tatt gevinst
     0  ingen tydelig handling (spørsmål, planer, andres handler osv.)

Står begge deler i samme innlegg, vinner det som står SIST
("solgte for tre uker siden ... nå kjøpte jeg tilbake" = kjøp).
Reglene er bevisst strenge: bedre å gå glipp av en handel enn å kopiere en
som aldri skjedde.
"""

import re

# Hvert verb sjekkes i sin egen setning. Det teller bare når handlingen er
# brukerens egen: setningen nevner jeg/eg/meg, eller starter med verbet
# ("Kjøpte en post på 48,30"). Spørsmål, planer, ønsker, nektelser og andres
# handler ("Varner har kjøpt", "aksjonærene har solgt") teller ikke.
_BUY_V = (r"kjøpte|kjøpt|kjøpe\s+(?:dem|den|de)\s+tilbake|økte|økt|fylte|fylt|plukket\s+opp"
          r"|tok\s+(?:en|ei|et)\s+(?:post|posisjon|slant)|la\s+meg\s+inn|lagt\s+meg\s+inn"
          r"|gikk\s+inn|gått\s+inn|inne\s+igjen|er\s+inne|sikret\s+meg")
_SELL_V = (r"solgte|solgt|selde|seld|gikk\s+(?:helt\s+)?ut|gått\s+(?:helt\s+)?ut|er\s+(?:helt\s+)?ute"
           r"|kvittet\s+meg|(?:tok|tatt|sikret)\s+(?:litt\s+|noe\s+)?gevinst|realiserte|reduserte|dumpet")
BUY_RE = re.compile(r"\b(?:" + _BUY_V + r")\b", re.I)
SELL_RE = re.compile(r"\b(?:" + _SELL_V + r")\b", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.!?·\n])\s+")
_ME = re.compile(r"\b(?:jeg|eg|meg|min|mine|mitt)\b", re.I)
_STARTS_WITH_VERB = re.compile(r"^\W*(?:(?:og|men|så|nå|i\s+dag|idag|har|ja|nei|neida|da)\W+){0,2}(?:"
                               + _BUY_V + "|" + _SELL_V + r")\b", re.I)
# Ord rett før verbet som betyr at handelen ikke har skjedd (planer, ønsker,
# nektelser, passiv) - gjelder uansett om "jeg" står der.
_HYPOTHETICAL = re.compile(
    r"\b(?:skal|vil|ville|kommer\s+til\s+å|vurderer|tenker|burde|bør|hvis|dersom|kanskje|håper|"
    r"ønske|ønsker|skulle|kunne|hadde\s+vært|aldri|ikke|ble|blitt|bli|å)\b[^.!?]{0,20}$", re.I)
# Andres handler - overstyres hvis "jeg/meg" står rett før verbet.
_OTHERS = re.compile(
    r"\b(?:de|dem|han|hun|folk|noen|hvem|investorer|innsider\w*|selskapet|fondet|banken|"
    r"\w+ene|\w+ne)\b[^.!?]{0,20}$", re.I)


def _last(rx, sentences):
    """Posisjon (setning, tegn) for siste egne handling, eller None."""
    best = None
    for si, sent in enumerate(sentences):
        if sent.rstrip().endswith("?"):
            continue
        own_sentence = bool(_ME.search(sent)) or bool(_STARTS_WITH_VERB.search(sent))
        if not own_sentence:
            continue
        for m in rx.finditer(sent):
            before = sent[max(0, m.start() - 30):m.start()]
            if _HYPOTHETICAL.search(before):
                continue
            if _OTHERS.search(before) and not _ME.search(before[-12:]):
                continue
            best = (si, m.start())
    return best


def classify(text):
    t = (text or "").strip()
    if not t or "Kommentaren er slettet" in t:
        return 0
    sentences = _SENT_SPLIT.split(t)
    b, s = _last(BUY_RE, sentences), _last(SELL_RE, sentences)
    if b is None and s is None:
        return 0
    if s is None:
        return 1
    if b is None:
        return -1
    return 1 if b > s else -1
