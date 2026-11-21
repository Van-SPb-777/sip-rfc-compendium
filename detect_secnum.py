# -*- coding: utf-8 -*-
"""ПРОВЕРКА secnum: номер раздела в переводе противоречит номеру в оригинале.

В RFC ссылки на разделы — часть смысла: «see Section 16.3» отсылает к
конкретному разделу. Если переводчик (или сдвиг блоков) поставил другой
номер, читатель уходит не туда. Класс ошибки — number consistency:
  * Verifika, «Number Formatting as in Source» —
    https://e-verifika.com/help_udchecks
  * Smartling, «Tag, Placeholder, and Number Consistency» —
    https://www.smartling.com/questions/automated-translation-consistency-checking
  * JAT, «Are numbers and units expressed consistently» —
    https://jat.org/blog/checklist_for_translators

Правило нарочно узкое, чтобы не давать ложных срабатываний:
  * берём только блоки prose/prose_cont, где есть и EN-ссылки вида
    «Section 5.2» / «Sections 5.2», и русские «раздел 5.2» / «п. 5.2»;
  * если хотя бы одна пара номеров совпадает или один номер является
    продолжением другого (5 и 5.2), блок считается нормальным;
  * находка — только когда множества номеров полностью расходятся.

Потерянную ссылку (EN «Section 5.2» есть, а в RU раздела нет вовсе) это
правило не ловит: такой случай требует перевода, а не сверки номеров;
он разобран в отчёте отдельно.

Запуск: python detect_secnum.py [N[,N]]
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

RE_EN = re.compile(r"\bSections?\s+(\d+(?:\.\d+)*)")
RE_RU = re.compile(r"(?:раздел\w*|пункт\w*|п\.)\s*(\d+(?:\.\d+)*)", re.I)


def related(a, b):
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def scan(num):
    """Вернуть список (i, номера_EN, номера_RU, фрагмент)."""
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    out = []
    for i, b in enumerate(obj.get("blocks") or []):
        if b.get("kind") not in ("prose", "prose_cont"):
            continue
        en, ru = b.get("en") or "", b.get("ru") or ""
        if not ru:
            continue
        ens = RE_EN.findall(en)
        rus = RE_RU.findall(ru)
        if not ens or not rus:
            continue
        if any(related(a, c) for a in ens for c in rus):
            continue
        out.append((i, ens, rus, ru[:80].replace("\n", "|")))
    return out


def doc_numbers(argv):
    args = [a for a in argv if not a.startswith("--")]
    if args:
        nums = []
        for a in args:
            nums.extend(int(x) for x in a.split(",") if x.strip())
        return nums
    return sorted(x for x in store.status_report() if isinstance(x, int))


def main():
    total = docs = 0
    for n in doc_numbers(sys.argv[1:]):
        hits = scan(n)
        if not hits:
            continue
        docs += 1
        total += len(hits)
        print("RFC %d: %d" % (n, len(hits)))
        for i, ens, rus, frag in hits:
            print("   блок %-5d EN %s vs RU %s | %s" % (i, ens, rus, frag))
    print()
    print("ИТОГО: %d расхождений номеров разделов в %d документах"
          % (total, docs))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
