# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: блок целиком повторяет кусок соседнего блока.

Встречается в шапках RFC: полная шапка попадает и в первый блок, и ещё раз
в следующем — вместе с названием документа. В книге шапка и название
печатаются дважды.

Признак: текст следующего блока (без пробельных различий) целиком входит в
текст предыдущего блока или наоборот.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

MIN = 40


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    bl = obj["blocks"]
    out = []
    for i in range(len(bl) - 1):
        a = norm(bl[i].get("en"))
        b = norm(bl[i + 1].get("en"))
        if len(a) < MIN or len(b) < MIN:
            continue
        # название документа законно повторяется внутри шапки
        if "title" in (bl[i].get("kind"), bl[i + 1].get("kind")):
            continue
        # сравниваем только блоки сопоставимой длины: иначе ловятся
        # случайные совпадения общих фраз
        if min(len(a), len(b)) / max(len(a), len(b)) < 0.8:
            continue
        if b in a or a in b:
            out.append((i, i + 1, len(a), len(b)))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        hits = scan(n)
        if hits:
            print("RFC %-5d повтор блока: %s" % (n, hits[:5]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
