# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: обычный текст попал в блок «код» и выпал из абзаца.

Бывает, что разборщик относит хвост абзаца (перенос строки в ссылке,
продолжение библиографии) к блоку `code` или `diagram`. В книге такой
хвост рисуется отдельной моноширинной рамкой по центру — выглядит как
случайно выделенная область:

    63, RFC 3629, November 2003.

Признак: блок `code`/`diagram` короткий (не больше 3 строк), состоит из
обычных слов (нет псевдографики), и перед ним идёт проза, которая не
закончилась точкой. Значит это продолжение абзаца.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

PSEUDO = set("|+-=_*/\\[]{}<>#")
KINDS = ("code", "diagram")


def looks_like_text(s):
    s = s.strip()
    if not s:
        return False
    letters = sum(1 for c in s if c.isalpha() or c in " .,;:()'\"-")
    if letters / len(s) < 0.85:
        return False
    if any(c in PSEUDO for c in s):
        return False
    return True


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    bl = obj["blocks"]
    out = []
    for i, b in enumerate(bl):
        if b.get("kind") not in KINDS:
            continue
        en = b.get("en") or ""
        lines = [l for l in en.split("\n") if l.strip()]
        if not lines or len(lines) > 3:
            continue
        if not all(looks_like_text(l) for l in lines):
            continue
        # схема — это рисунок, текст в ней нормален
        if b.get("kind") == "diagram":
            continue
        # это должен быть обрывок ФРАЗЫ: несколько слов и знак конца
        joined = " ".join(lines)
        # строка таблицы: между словами длинные пробельные колонки
        if re.search(r"\S {3,}\S", joined):
            continue
        if len(joined.split()) < 5 or not joined.rstrip().endswith((".", ":", ";")):
            continue
        if i == 0:
            continue
        prev = bl[i - 1]
        if prev.get("kind") not in ("prose", "prose_cont"):
            continue
        pe = (prev.get("en") or "").rstrip()
        if pe and pe[-1] not in ".!?:;":
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
            print("RFC %-5d текст в блоке «код»: %s" % (n, hits[:10]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
