# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: слово разорвано переносом на границе блоков.

В исходнике длинное слово может переноситься по дефису: строка кончается
«Identity-», следующая начинается «Info.». Если разборщик принял дефис за
конец предложения, слово оказывается разрезано между двумя блоками — и в
книге появляется обрыв посреди слова.

Признак: блок заканчивается буквой и дефисом, а следующий начинается со
строчной буквы.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

KINDS = ("prose", "prose_cont", "heading")


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    bl = obj["blocks"]
    out = []
    for i in range(len(bl) - 1):
        a, b = bl[i], bl[i + 1]
        if a.get("kind") not in KINDS or b.get("kind") not in KINDS:
            continue
        ea = (a.get("en") or "").rstrip()
        eb = (b.get("en") or "").lstrip()
        if not ea or not eb:
            continue
        if not re.search(r"[A-Za-zА-Яа-я]-$", ea):
            continue
        if not re.match(r"[a-zа-я]", eb):
            continue
        out.append((i, i + 1, ea[-18:], eb[:18]))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        hits = scan(n)
        if hits:
            print("RFC %-5d разрывов слова: %s" % (n, hits[:6]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
