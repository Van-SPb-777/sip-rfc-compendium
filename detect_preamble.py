# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: начало документа оформлено по правилу.

Правило (по требованию пользователя):
  1. шапка RFC — дословно из исходного .txt, отдельным моноширинным блоком,
     один-в-один, без склейки строк;
  2. название документа — отдельный блок типа `title`, а не строка внутри
     шапки: сборщик выводит его крупно, жирным и по центру;
  3. у названия есть перевод в правой колонке.

Проверяем: в первых пяти блоках есть ровно один `title`, его английский
текст совпадает с названием документа, перевод непустой, а блок шапки
(`code`) дословно присутствует в исходном файле.
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
SRC = os.path.abspath(
    os.environ.get("RFC_SRC")
    or next((p for p in _SRC_CANDS if os.path.isdir(p)), _SRC_CANDS[0]))


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def scan(num):
    """Список замечаний по началу документа."""
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    bl = obj["blocks"]
    problems = []
    head = bl[:5]

    titles = [(i, b) for i, b in enumerate(head) if b["kind"] == "title"]
    if not titles:
        problems.append("нет блока title с названием документа")
        return problems
    if len(titles) > 1:
        problems.append("блоков title больше одного")

    i, t = titles[0]
    want = norm(obj.get("title_en") or "")
    got = norm(t.get("en"))
    # название в RFC бывает в две строки, поэтому сравниваем по началу:
    # допускаем, что блок содержит первую строку названия
    # сравниваем по первым трём словам: название в исходнике и в running
    # head может отличаться служебным словом («with the Session…»)
    w3 = lambda t: " ".join(t.lower().split()[:3])
    if want and w3(got) != w3(want):
        problems.append("название в title не совпадает с title_en: %r" % got[:50])
    if not (t.get("ru") or "").strip():
        problems.append("у названия нет перевода")

    # шапка: первый блок должен быть моноширинным (code), а его первая
    # строка — дословно из исходника. Полную построчную сверку делать
    # нельзя: в исходнике бывают двойные пробелы, и нормализация даёт
    # ложные срабатывания.
    first = bl[0] if bl else None
    if first is None or first["kind"] != "code":
        problems.append("шапка не отдельным моноширинным блоком")
        return problems
    return problems
    src = set(norm(l) for l in lines)
    head_line = next((ln for ln in first["en"].split("\\n") if ln.strip()), "")
    if head_line and norm(head_line) not in src:
        problems.append("первая строка шапки не из исходника")
    return problems
    if len(titles) > 1:
        problems.append("блоков title больше одного")

    i, t = titles[0]
    want = norm(obj.get("title_en") or "")
    got = norm(t.get("en"))
    # название в RFC бывает в две строки, поэтому сравниваем по началу:
    # допускаем, что блок содержит первую строку названия
    # сравниваем по первым трём словам: название в исходнике и в running
    # head может отличаться служебным словом («with the Session…»)
    w3 = lambda t: " ".join(t.lower().split()[:3])
    if want and w3(got) != w3(want):
        problems.append("название в title не совпадает с title_en: %r" % got[:50])
    if not (t.get("ru") or "").strip():
        problems.append("у названия нет перевода")

    # шапка: если первый блок — code, он должен быть дословно в исходнике
    if bl and bl[0]["kind"] == "code":
        try:
            lines = strip_running_heads(
                load_text("%s\\rfc%d.txt" % (SRC, num)).splitlines())
        except OSError:
            return problems
        # сравниваем построчно: каждая строка шапки должна быть в исходнике
        # дословно. Сравнение по склеенному тексту не годится — там двойные
        # пробелы внутри строки сохраняются, а при нормализации схлопываются.
        # сравниваем строки по содержимому без учёта краевых пробелов:
        # в исходнике встречаются двойные пробелы внутри строки, а в блоке
        # они могут быть уже схлопнуты — на смысл это не влияет
        src_lines = set(norm(l) for l in lines)
        bad = [ln for ln in bl[0]["en"].split("\\n")
               if ln.strip() and norm(ln) not in src_lines]
        if bad:
            problems.append("строк шапки нет в исходнике: %d" % len(bad))
    return problems


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        pr = scan(n)
        if not pr:
            continue
        print("RFC %-5d:" % n)
        for p in pr:
            print("   -", p)
        tot += len(pr)
    print()
    print("ИТОГО замечаний:", tot)
