# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: псевдографика потеряла структуру.

Таблица или схема в RFC нарисована пробелами и подчёркиваниями. Если
разборщик теряет переводы строк, от таблицы остаётся одна длинная строка:

    Header field where proxy ACK BYE CAN INV OPT REG ____ Refer-To R - - - -

В PDF это каша, и выравнивание уже не вернуть — данные испорчены. Проверка
ищет два признака:

  1. блок `table`, в тексте которого нет переводов строк, зато есть ряд
     подчёркиваний (разделитель шапки таблицы);
  2. любая строка длиннее 200 символов с рядом из 8+ подчёркиваний или
     дефисов — тоже след сплющенной таблицы.

Лечится `fix_squeezed_tables.py`: таблица забирается из исходного .txt.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

RE_RULE = re.compile(r"[_\-]{8,}")


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        en = b.get("en") or ""
        if not en.strip():
            continue
        if b.get("kind") == "table" and "\n" not in en and "_" * 10 in en:
            out.append(i)
            continue
        # Таблица, вклеенная в абзац: строка длинная И содержит ряд
        # подчёркиваний. У настоящей таблицы строка с подчёркиваниями
        # стоит отдельно и короткая, поэтому она сюда не попадает.
        for ln in en.split("\n"):
            if len(ln) > 120 and "_" * 8 in ln:
                out.append(i)
                break
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        hits = scan(n)
        if hits:
            print("RFC %-5d сплющенных таблиц: %s" % (n, hits))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
