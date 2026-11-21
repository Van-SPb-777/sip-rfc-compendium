# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: два одинаковых блока подряд.

Появляется при ручных правках: блок делят на части, а старая копия
остаётся рядом. В книге абзац или пункт списка повторяется дважды.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    bl = obj["blocks"]
    out = []
    for i in range(len(bl) - 1):
        a = re.sub(r"\\s+", " ", bl[i].get("en") or "").strip()
        b = re.sub(r"\\s+", " ", bl[i + 1].get("en") or "").strip()
        if a and a == b:
            out.append((i, i + 1))
    return out


if __name__ == "__main__":
    for n in sorted(x for x in store.status_report() if isinstance(x, int)):
        h = scan(n)
        if h:
            print("RFC %-5d дубли подряд: %s" % (n, h))
