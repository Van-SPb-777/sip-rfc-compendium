# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: начало перевода блока дублирует предыдущий блок.

Так выглядит сдвиг перевода на границе: в конце предыдущего блока уже
стоит текст, который должен открывать следующий. В PDF это видно как
повтор в правой колонке — и объём русского текста становится заметно
больше английского (именно это и заметил пользователь в §6 RFC 3261,
где дубль занимал 680 символов).

Признак: первые 80 символов перевода блока встречаются в переводе
предыдущего блока.

Чтобы не ловить повторяющиеся пункты списков (в RFC они бывают
буквально одинаковыми), блоки, начинающиеся с маркера списка,
пропускаются.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

PREFIX = 80
RE_BULLET = re.compile(r"^\s*([*•\-–—]|o\s|\(\d\)|\d\))\s")
TRANSLATABLE = ("prose", "prose_cont", "heading")


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    bl = obj["blocks"]
    out = []
    for i in range(len(bl) - 1):
        a, b = bl[i], bl[i + 1]
        if b["kind"] not in TRANSLATABLE or a["kind"] not in TRANSLATABLE:
            continue
        ra = (a.get("ru") or "").strip()
        rb = (b.get("ru") or "").strip()
        if len(ra) < 200 or len(rb) < 100:
            continue
        if RE_BULLET.match(rb):
            continue
        pref = rb[:PREFIX]
        # дубль — это когда прежний блок КОНЧАЕТСЯ тем же текстом:
        # совпадение зачина у двух соседних абзацев это не дефект
        if pref in ra and ra.rstrip().endswith(rb.strip()[:PREFIX].rstrip()):
            out.append((i + 1, len(rb), pref[:60]))

    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        hits = scan(n)
        if not hits:
            continue
        print("RFC %-5d блоков с дублем в начале: %d" % (n, len(hits)))
        for i, ln, s in hits:
            print("   блок %-5d RU=%d  %r" % (i, ln, s))
        tot += len(hits)
    print()
    print("ИТОГО:", tot)
