# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: в книгу просочился остаток оглавления.

В начале RFC стоит оглавление на несколько страниц. Разборщик его
вырезает, но иногда несколько строк всё же попадают в тело отдельным
блоком — в PDF это выглядит как обрывок вида

    3.2.3.  Mapping SRTP Packets to Cryptographic Contexts . 10

то есть текст плюс точки и номер страницы. Такой блок в книге лишний.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

RE_SECT = re.compile(r"^\\s*\\d+(\\.\\d+)*\\.?\\s+[A-Z]")
RE_NUM = re.compile(r"^\s*\d+(\.\d+)+\.?\s+\S")
RE_TAIL = re.compile(r"(\.\s?\d+|\s\d+)\s*$")


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        # таблицы и схемы не проверяем: в них тоже бывают номера в начале строк
        if b.get("kind") in ("table", "diagram", "abnf", "sip"):
            continue
        lines = [l for l in (b.get("en") or "").split("\n") if l.strip()]
        if len(lines) < 2:
            continue
        # вид 1: строка оглавления с точками и номером страницы
        toc = sum(1 for l in lines if RE_TAIL.search(l) and (" . " in l or "..." in l))
        # вид 2: несколько строк подряд начинаются с многоуровневого номера
        # раздела и не заканчиваются знаком конца предложения — так выглядит
        # оглавление, у которого номера страниц обрезаны при разборе
        num = sum(1 for l in lines if RE_NUM.match(l) and not l.rstrip().endswith((".", ":", ";")))
        # одиночная строка оглавления, из которой при разборе срезались
        # точки и номер страницы: стоит прямо перед заголовком и не имеет
        # знака конца предложения
        if (i < 20 and i + 1 < len(obj["blocks"])
                and obj["blocks"][i + 1].get("kind") == "heading"
                and len(lines) == 1 and len(lines[0]) <= 90
                and RE_SECT.match(lines[0]) and not lines[0].rstrip().endswith((".", ":", ";"))):
            out.append(i)
        if toc >= 2 and toc >= 0.5 * len(lines):
            out.append(i)
        elif num >= 2 and num >= 0.5 * len(lines) and max(len(l) for l in lines) <= 90:
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
            print("RFC %-5d остатки оглавления: %s" % (n, hits))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
