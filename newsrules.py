"""Which Oslo Børs announcements count as real news (shared by the app and the backtest)."""
import re

ROUTINE = re.compile(r"notifiable trad|mandatory notification|primary insider|ex[- ]?div|ex[- ]?date|"
                     r"buy[- ]?back|share repurchase|key information|total number of|voting rights|"
                     r"annual general meeting|general meeting|financial calendar|invitation to|"
                     r"presentation of|will (present|publish|report)|webcast|share capital|"
                     r"major shareholding|disclosure of large", re.I)
MATERIAL_CATS = re.compile(r"INSIDE INFORMATION|FINANCIAL REPORT|NON-REGULATORY PRESS|ADDITIONAL REGULATED", re.I)


def is_material(category, title):
    return bool(MATERIAL_CATS.search(category or "")) and not ROUTINE.search(title or "")
