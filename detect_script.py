# -*- coding: utf-8 -*-
"""ПРОВЕРКА script: смешение алфавитов (кириллица в EN, латиница в слове RU).

Два независимых дефекта одного класса — «script consistency»:

1. В `en` попала кириллица. EN берётся дословно из ASCII-исходника RFC
   (правило формата: «The character codes are ASCII», RFC 2223 §3 —
   https://www.rfc-editor.org/rfc/rfc2223), поэтому кириллица там может
   появиться только от правки/подмены текста.
2. В русском слове есть латинские буквы-двойники: «рroduсt», «cлово» с
   латинской c. Это confusable/homoglyph-ошибка; проверки на неё есть в
   Unicode Text Inspector (https://apify.com/maximedupre/unicode-text-inspector)
   и confusables-inspector (https://github.com/opensecurity/confusables-inspector).
   Такое слово выглядит правильно, но поиск, сортировка и копирование
   ломаются.

Дефисные гибриды («SIP-запрос», «Call-ID») — норма, они не считаются:
слово разбивается по дефису, и каждая часть должна быть в одном алфавите.

Запуск: python detect_script.py [N[,N]]
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

CYR = re.compile(r"[А-Яа-яЁё]")
TOKEN = re.compile(r"[А-Яа-яЁёA-Za-z]{2,}")


def scan(num):
    """Вернуть список (i, kind, reason, фрагмент)."""
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    out = []
    for i, b in enumerate(obj.get("blocks") or []):
        en, ru = b.get("en") or "", b.get("ru") or ""
        if CYR.search(en):
            m = CYR.search(en)
            out.append((i, b.get("kind"), "кириллица в EN",
                        en[max(0, m.start() - 30):m.start() + 30]))
        for m in TOKEN.finditer(ru):
            w = m.group(0)
            if CYR.search(w) and re.search(r"[A-Za-z]", w):
                out.append((i, b.get("kind"), "смешение алфавитов в слове",
                            ru[max(0, m.start() - 30):m.end() + 30]))
                break
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
        for i, kind, reason, frag in hits:
            print("   блок %-5d %-7s %-28s %r" % (i, kind, reason, frag))
    print()
    print("ИТОГО: %d находок в %d документах" % (total, docs))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
