# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: заголовок раздела потерял тип и стал прозой.

В RFC заголовки вида «14.2. 428 'Use Identity Header' Response Code» иногда
разбираются как обычная проза — из-за кавычек и цифр внутри строки. В книге
такой раздел теряет оформление: нет плашки, нет отступа, нет жирного шрифта.

Признак: блок прозы начинается с номера раздела, короткий (до 90 символов)
и не заканчивается точкой.
"""
import os
import io
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store
import rfc_parse

_SRC_CANDS = (os.path.join(BASE, os.pardir, "rfc-sip"),
              os.path.join(BASE, os.pardir, os.pardir, "rfc-sip"))
SRC = os.path.abspath(
    os.environ.get("RFC_SRC")
    or next((p for p in _SRC_CANDS if os.path.isdir(p)), _SRC_CANDS[0]))

RE_SEC = re.compile(r"^\d{1,2}(?:\.\d{1,2}){0,3}\.?\s+\S")
KINDS = ("prose", "prose_cont")


def standalone_line(lines, text):
    """Стоит ли строка отдельно: перед ней и после неё пусто."""
    t = re.sub(r'\s+', ' ', text).strip()
    for k, ln in enumerate(lines):
        if re.sub(r'\s+', ' ', ln).strip() != t:
            continue
        before = lines[k - 1].strip() if k > 0 else ''
        after = lines[k + 1].strip() if k + 1 < len(lines) else ''
        if not before and not after:
            return True
    return False


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b.get("kind") not in KINDS:
            continue
        en = (b.get("en") or "").strip()
        if not en or len(en) > 90:
            continue
        if not RE_SEC.match(en):
            continue
        # заголовок раздела — минимум два уровня (14.2, 15.1); одиночные
        # числа («1. Who sent the message?») это пункты списков
        if not re.match(r'^\d{1,2}\.\d{1,2}', en):
            continue
        # в заголовке есть слова; строки из одних чисел (OID-таблицы) — не он
        if len(re.findall(r'[A-Za-zА-Яа-я]{2,}', en)) < 2:
            continue
        if en.endswith("."):
            continue
        # сверка с исходником: заголовок стоит отдельной строкой между пустыми
        lines = rfc_parse.strip_running_heads(
            rfc_parse.load_text("%s\\rfc%d.txt" % (SRC, num)).split("\n"))
        if not standalone_line(lines, en):
            continue
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
            print("RFC %-5d потерянных заголовков: %s" % (n, hits[:8]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
