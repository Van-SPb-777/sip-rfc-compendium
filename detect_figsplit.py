# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: псевдографика попала в прозу или разрезана между блоками.

Рисунки и таблицы в RFC нарисованы символами | + - _ и линейками цифр.
Разбор иногда принимает такую графику за текст или режет её разрывом
страницы. В книге это выглядит как обрывки рамок и «поплывшая» таблица.

Три признака:
  А) в блоке ПРОЗЫ есть строки псевдографики (рамка или линейка цифр);
  Б) блок кончается рамкой, а следующий блок начинается рамкой;
  В) подпись «Figure N:» / «Table N:» стоит в блоке, где есть графика.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

RE_BOX = re.compile(r"^\s*\+[-+=]{3,}")
RE_BAR = re.compile(r"^\s*\|.*\|")
RE_RULER = re.compile(r"^\s*0\s+1\s+2\s+3")
RE_CAPTION = re.compile(r"^(Figure|Table)\s+\d+[:.]")
PROSE = ("prose", "prose_cont")


def is_art_line(ln):
    s = ln.strip()
    if not s:
        return False
    if RE_BOX.match(ln) or RE_BAR.match(ln) or RE_RULER.match(ln):
        return True
    return False


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    bl = obj["blocks"]
    out = []
    for i, b in enumerate(bl):
        en = b.get("en") or ""
        if not en:
            continue
        lines = en.split("\n")
        arts = [ln for ln in lines if is_art_line(ln)]
        kind = b.get("kind")
        # А) графика в блоке прозы
        if kind in PROSE and arts:
            out.append((i, "графика в прозе", arts[0].strip()[:40]))
            continue
        # Б2) рамка таблицы приклеена к абзацу
        if kind in PROSE and re.search(r"[+][-]{3,}[+]\s*$", en.strip()):
            out.append((i, "рамка приклеена к абзацу", en.strip()[-40:]))
            continue
        # В) подпись рисунка вместе с графикой
        if RE_CAPTION.match(en.strip()) and arts:
            out.append((i, "подпись с графикой", en.strip()[:40]))
            continue
    # Б) разрезанная таблица
    for i in range(len(bl) - 1):
        a = (bl[i].get("en") or "").rstrip().split("\n")
        c = (bl[i + 1].get("en") or "").lstrip().split("\n")
        if not a or not c:
            continue
        la, lc = a[-1].strip(), c[0].strip()
        if (la.startswith(("+", "|")) and lc.startswith(("+", "|"))):
            out.append((i, "таблица разрезана", la[:40]))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        hits = scan(n)
        if hits:
            print("RFC %-5d %s" % (n, hits[:4]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
