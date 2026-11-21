# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: список вклеен внутрь абзаца.

Разборщик считает строки с отступом 3–4 пробела продолжением абзаца,
поэтому маркированный список в исходнике превращается в одну длинную
строку:

    ... the receiver can: - reorder text ... - mark where ... - compensate ...

В книге вместо списка получается сплошной абзац. Признак простой: внутри
блока встречается двоеточие, а после него подряд идут два и более
маркеров списка «- », «o », «* » или «(1)».

Ставится в аудитор как проверка 17.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

RE_MARK = re.compile(r"(?:^|[.:;]\s)(?:[-*]|o|\d{1,2}(?:\.\d{1,2})?[.)]|\((?:lowest|highest|низший|высший)\))\s+\S", re.I)
KINDS = ("prose", "prose_cont")


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b.get("kind") not in KINDS:
            continue
        en = b.get("en") or ""
        if len(en) < 120 or ":" not in en:
            continue
        # считаем маркеры списка, идущие после двоеточия
        tail = en[en.rfind(":") + 1:]
        if len(RE_MARK.findall(tail)) >= 2:
            out.append(i)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        hits = scan(n)
        if hits:
            print("RFC %-5d список вклеен в абзац: %s" % (n, hits[:8]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
