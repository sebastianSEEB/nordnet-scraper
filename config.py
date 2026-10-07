"""All settings live here. Nothing needs changing for normal use."""
import os
from pathlib import Path

ROOT = Path(__file__).parent
DEMO = os.environ.get("RIPPLE_DEMO") == "1"
DB_PATH = ROOT / ("ripple_demo.db" if DEMO else "ripple.db")

# ticker: (company name used for news search, sector)
UNIVERSE = {
    # Norway
    "EQNR.OL": ("Equinor", "Energy"),
    "AKRBP.OL": ("Aker BP", "Energy"),
    "VAR.OL": ("Var Energi", "Energy"),
    "AKSO.OL": ("Aker Solutions", "Energy services"),
    "SUBC.OL": ("Subsea 7", "Energy services"),
    "TGS.OL": ("TGS ASA", "Energy services"),
    "MOWI.OL": ("Mowi", "Seafood"),
    "SALM.OL": ("SalMar", "Seafood"),
    "LSG.OL": ("Leroy Seafood", "Seafood"),
    "BAKKA.OL": ("Bakkafrost", "Seafood"),
    "FRO.OL": ("Frontline tankers", "Shipping"),
    "HAFNI.OL": ("Hafnia tankers", "Shipping"),
    "GOGL.OL": ("Golden Ocean", "Shipping"),
    "WAWI.OL": ("Wallenius Wilhelmsen", "Shipping"),
    "DNB.OL": ("DNB Bank", "Banks"),
    "STB.OL": ("Storebrand", "Insurance"),
    "GJF.OL": ("Gjensidige", "Insurance"),
    "NHY.OL": ("Norsk Hydro", "Materials"),
    "YAR.OL": ("Yara International", "Materials"),
    "ORK.OL": ("Orkla", "Consumer"),
    "TEL.OL": ("Telenor", "Telecom"),
    "KOG.OL": ("Kongsberg Gruppen", "Industrials"),
    "NOD.OL": ("Nordic Semiconductor", "Tech"),
    # Sweden
    "VOLV-B.ST": ("Volvo trucks", "Industrials"),
    "SAND.ST": ("Sandvik", "Industrials"),
    "SKF-B.ST": ("SKF bearings", "Industrials"),
    "ATCO-A.ST": ("Atlas Copco", "Industrials"),
    "SEB-A.ST": ("SEB bank", "Banks"),
    "SHB-A.ST": ("Handelsbanken", "Banks"),
    "SWED-A.ST": ("Swedbank", "Banks"),
    "ERIC-B.ST": ("Ericsson", "Tech"),
    # Denmark / Finland
    "MAERSK-B.CO": ("Maersk", "Shipping"),
    "DSV.CO": ("DSV logistics", "Industrials"),
    "NOVO-B.CO": ("Novo Nordisk", "Health"),
    "NOKIA.HE": ("Nokia", "Tech"),
    "NDA-FI.HE": ("Nordea", "Banks"),
    # Eurozone
    "HLAG.DE": ("Hapag-Lloyd", "Shipping"),
    "BMW.DE": ("BMW", "Autos"),
    "MBG.DE": ("Mercedes-Benz", "Autos"),
    "VOW3.DE": ("Volkswagen", "Autos"),
    "SAP.DE": ("SAP", "Tech"),
    "SIE.DE": ("Siemens", "Industrials"),
    "ASML.AS": ("ASML", "Tech"),
    "ASM.AS": ("ASM International", "Tech"),
    "TTE.PA": ("TotalEnergies", "Energy"),
    "ENI.MI": ("Eni", "Energy"),
    "BNP.PA": ("BNP Paribas", "Banks"),
    "GLE.PA": ("Societe Generale", "Banks"),
    "SAN.MC": ("Banco Santander", "Banks"),
    "BBVA.MC": ("BBVA", "Banks"),
}

# Known business links (customer -> supplier). Add your own: (a, b, sign).
# sign +1 = good news for a is good for b; -1 = good for a is bad for b.
SEED_LINKS = [
    ("AKRBP.OL", "AKSO.OL", +1),
    ("EQNR.OL", "AKSO.OL", +1),
    ("EQNR.OL", "SUBC.OL", +1),
]

P = dict(
    lookback_days=252,      # history used to build the network
    min_link=0.25,          # min residual correlation to count as linked
    max_links=8,            # links kept per company
    min_headlines=2,        # headlines needed in last day to call it "news"
    min_sentiment=0.15,     # |average sentiment| needed
    min_price_z=1.5,        # company's own abnormal move must confirm (std devs)
    min_expected=0.004,     # ignore peers whose expected reaction is < 0.4%
    lag_fraction=0.5,       # peer counts as lagging if it moved < 50% of expected
    min_peers=2, max_peers=5,
    hold_days=5,
    notional=10_000,        # paper money per trade
    start_capital=100_000,
    cost=0.001,             # 0.1% each way
    check_minutes=15,       # real-mode check interval
    demo_seconds=4,         # demo-mode: one simulated day every N seconds
)
