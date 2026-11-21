# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: в блок прозы вклеена структура (таблица, ABNF, пример сообщения).

Так выглядит последствие старого поведения разборщика: строки с отступом
3 пробела (тот же, что у обычной прозы) склеивались в один абзац, и вместо
таблицы или грамматики получалась одна длинная строка.

Признаки структуры внутри блока:
  • два и более определения ABNF («name = …»);
  • три и более строки таблицы (две и более группы пробелов по 2+);
  • два и более строк-заголовков сообщения («Via: …», «Content-Length: 142»).

Проверка смотрит только блоки прозы: у блоков ABNF/таблиц/примеров тип уже
правильный, их она не трогает.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

RE_ABNF_DEF = re.compile(r"^\s*[A-Za-z][A-Za-z0-9\-]{0,40}\s*=/?\s*\S", re.M)
RE_TABLE_ROW = re.compile(r"\S {2,}\S")
RE_MSG_HEADER = re.compile(r"^[A-Za-z][A-Za-z0-9\-]{1,40}:\s+\S", re.M)


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b["kind"] not in ("prose", "prose_cont"):
            continue
        en = b.get("en") or ""
        if len(en) < 60:
            continue
        abnf = len(RE_ABNF_DEF.findall(en))
        hdr = len(RE_MSG_HEADER.findall(en))
        rows = 0
        if "\n" in en:
            # таблица в несколько строк
            rows = sum(1 for ln in en.split("\n")
                       if len(RE_TABLE_ROW.findall(ln)) >= 2)
        # таблица, склеенная в одну строку: много «клеток» подряд.
        # Признак имеет смысл ТОЛЬКО для однострочного текста: у блока с
        # переводами строк «клетки» считаются по всем строкам сразу, и
        # любая колонка списка (индекс, перечисление) давала ложное
        # срабатывание. Для многострочных блоков работает rows.
        cells = 0 if "\n" in en else len(RE_TABLE_ROW.findall(en))
        if abnf >= 2:
            out.append((i, "ABNF", abnf, en[:70]))
        elif hdr >= 2:
            out.append((i, "сообщение", hdr, en[:70]))
        elif rows >= 3 or (cells >= 4 and len(en.split()) >= 12):
            out.append((i, "таблица", max(rows, cells), en[:70]))
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
        print("RFC %-5d блоков со структурой внутри прозы: %d" % (n, len(hits)))
        for i, what, cnt, s in hits[:6]:
            print("   блок %-5d (%s, %d) %r" % (i, what, cnt, s))
        tot += len(hits)
    print()
    print("ИТОГО:", tot)
