#!/usr/bin/env python3
"""Bygger nordnet_data/copytrade/dashboard.html fra results.json (én selvstendig fil)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "nordnet_data", "copytrade")


def main(src=None, dst=None):
    src = src or os.path.join(OUT_DIR, "results.json")
    dst = dst or os.path.join(OUT_DIR, "dashboard.html")
    data = open(src, encoding="utf-8").read().replace("</", "<\\/")
    tpl = open(os.path.join(HERE, "dashboard_template.html"), encoding="utf-8").read()
    with open(dst, "w", encoding="utf-8") as f:
        f.write(tpl.replace("__DATA__", data))
    print(f"Dashboard -> {dst} ({os.path.getsize(dst) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
