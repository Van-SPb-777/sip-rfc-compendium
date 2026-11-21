# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: схема-«псевдокартинка» разрезана на два блока.

В RFC схемы занимают по 20–40 строк. Один из старых скриптов разбиения
резал блоки по 26 строк, и рисунок оказывался в двух рамках: верх в
одном блоке, низ в другом. Читается как две отдельные картинки.

Признак: два соседних блока типа `diagram`, тексты которых в исходном
`.txt` идут подряд (между ними нет ничего, кроме пробелов и переводов
строк). Значит это одна схема, разрезанная искусственно.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store
from rfc_parse import load_text, strip_running_heads  # noqa: E402

_SRC_CANDS = (os.path.join(BASE, os.pardir, "rfc-sip"),
              os.path.join(BASE, os.pardir, os.pardir, "rfc-sip"))
SRC_DIR = os.path.abspath(
    os.environ.get("RFC_SRC")
    or next((p for p in _SRC_CANDS if os.path.isdir(p)), _SRC_CANDS[0]))


def looks_like_figure(s):
    """Рисунок из отступных строк без знаков конца предложения."""
    lines = [l for l in (s or "").split("\n") if l.strip()]
    if len(lines) < 2:
        return False
    indented = sum(1 for l in lines if len(l) - len(l.lstrip()) >= 4)
    returns = sum(1 for l in lines if l.rstrip().endswith((".", ":", ";")))
    return indented >= 2 and returns <= len(lines) * 0.2


def is_ascii(s):
    """Есть ли в тексте псевдографика: рамки, стрелки, линейки."""
    s = s or ""
    return sum(1 for c in s if c in "|+-=>") >= 3


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def src_flat(num):
    p = "%s\\rfc%d.txt" % (SRC_DIR, num)
    try:
        lines = strip_running_heads(load_text(p).splitlines())
    except OSError:
        return None
    return " ".join(l.strip() for l in lines if l.strip())


def scan(num, flat=None):
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    if flat is None:
        flat = src_flat(num)
    if not flat:
        return []
    bl = obj["blocks"]
    out = []
    for i in range(len(bl) - 1):
        a, b = bl[i], bl[i + 1]
        # схема может развалиться на блоки РАЗНЫХ типов: прозу с одной
        # строкой «User A User B | |», код со стрелками и собственно diagram.
        # Поэтому проверяем любую пару соседей, если хотя бы один из них
        # содержит псевдографику.
        # случай 3: рисунок из отступных строк без псевдографики
        # (списки приоритетов, перечни в табличном виде). Разборщик режет
        # его по пустым строкам, а пустые строки внутри рисунка — часть
        # рисунка, они разделяют группы.
        if (a["kind"] in ("table", "diagram")
                and b["kind"] in ("table", "diagram")
                and looks_like_figure(a["en"]) and looks_like_figure(b["en"])
                and (norm(a["en"]) + " " + norm(b["en"])) in flat):
            out.append((i, i + 1, len(a["en"]), len(b["en"])))
            continue

        # случай 1: два блока-схемы подряд
        # случай 2: короткий «огрызок» схемы (1–2 строки с рамками) перед
        # блоком-схемой — так схема распадается на части разных типов
        frag = (len([l for l in (a["en"] or "").split("\n") if l.strip()]) <= 2
                and "|" in (a["en"] or ""))
        if not ((a["kind"] == "diagram" and b["kind"] == "diagram")
                or (frag and b["kind"] == "diagram")):
            continue
        na, nb = norm(a["en"]), norm(b["en"])
        if not na or not nb:
            continue
        if (na + " " + nb) in flat:
            out.append((i, i + 1, na.count(" ") + 1, nb.count(" ") + 1))
    return out


def merge(num, i, flat=None):
    """Склеить пару схем в один блок. Возвращает True, если склеено."""
    obj = store.load(num)
    bl = obj["blocks"]
    a, b = bl[i], bl[i + 1]
    na, nb = norm(a["en"]), norm(b["en"])
    if not (na and nb):
        return False
    if flat is None:
        flat = src_flat(num)
    if (na + " " + nb) not in flat:
        return False
    a["en"] = (a["en"].rstrip() + "\n" + b["en"].lstrip()).rstrip()
    a["ru"] = ""
    del bl[i + 1]
    store.save(num, obj)
    return True


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    apply = "--apply" in sys.argv
    tot = 0
    for n in nums:
        hits = scan(n)
        if not hits:
            continue
        print("RFC %-5d разрезанных схем: %d" % (n, len(hits)))
        if apply:
            # склеиваем с конца, чтобы индексы не съезжали
            for i, j, _, _ in reversed(hits):
                merge(n, i)
        tot += len(hits)
    print()
    print("всего:", tot, "(склеено)" if apply else "(только проверка)")
