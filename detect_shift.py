# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: перевод блока начинается не с начала фразы.

Так выглядит сдвиг границ: блок разрезали в одном месте, а перевод
привязали со сдвигом. Тогда русская колонка начинается с обрывка
(«имеет иное значение идентификатора ветви Via, нежели предыдущий…»),
а начало фразы осталось в предыдущем блоке.

Признак: английский блок начинается нормально (с заглавной буквы,
кавычки или цифры), а русский — со строчной буквы или со скобки,
причём не с цифры.

Чтобы не ловить ложные срабатывания, пропускаем:

  • блоки, где английский сам начинается со строчной или со скобки —
    значит, это продолжение, и русский вправе начинаться так же;
  • блоки-грамматику ABNF (`boundary := …`);
  • блоки со схемами (`->`, рамки, выровненные пробелы);
  • русский текст, начинающийся с обычного связочного слова
    («так», «где», «и», «при», «например») — это законное продолжение мысли;
  • русский текст, начинающийся с латинского термина.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

# первая строка выглядит как правило ABNF
RE_ABNF = re.compile(r"^[a-z][\w\-]*\s*(:=|=)\s")
# русский блок начинается со связочного слова — это нормально
RE_CONNECTOR = re.compile(
    r"^(так|где|и|или|но|а|при|то|что|если|для|в|во|на|по|с|со|к|ко|от|до|из|"
    r"за|под|над|без|через|между|когда|пока|чтобы|хотя|поскольку|однако|"
    r"например|кроме|также|только|именно|это|этот|эта|эти|такой|такая|такие|"
    r"таким|как|чем|тем|потому|поэтому|затем|далее|ниже|выше|обычно|"
    r"клиент|сервер|прокси)\b", re.I)
# маркер списка: "a)", "1)", "(1)", "-"
RE_LIST = re.compile(r"^(\d+\)|[a-zа-я]\)|\(\d+\)|[-•*]\s)")


def looks_like_scheme(t):
    if "+-" in t or t.count("|") >= 4 or "->" in t:
        return True
    return len(re.findall(r"\S {2,}\S", t)) >= 3


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b["kind"] != "prose":
            continue
        en = (b.get("en") or "").strip()
        ru = (b.get("ru") or "").strip()
        if len(en) < 60 or not ru:
            continue
        if RE_ABNF.match(en) or looks_like_scheme(en):
            continue
        # английский сам начинается не с начала фразы — сравнивать нечего
        if en[0].islower() or en[0] == "(":
            continue
        # Русский начинается нормально, если первый символ — заглавная буква,
        # цифра, кавычка, скобка-перечисление, маркер списка или ссылки.
        # Проверяем только два подозрительных начала: строчная буква
        # и скобка без цифры.
        ru_bad = ru[0].islower() or (ru[0] == "(" and not re.match(r"^\(\d", ru))
        if not ru_bad:
            continue
        if RE_LIST.match(ru):
            continue
        # начинается с латинского термина — это нормально
        if ru[0].isalpha() and not ("а" <= ru[0].lower() <= "я"
                                    or ru[0].lower() == "ё"):
            continue
        if RE_CONNECTOR.match(ru):
            continue
        out.append((i, en[:70], ru[:70]))
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
        print("RFC %-5d блоков со сдвигом: %d" % (n, len(hits)))
        for i, en, ru in hits:
            print("   блок %-5d" % i)
            print("      EN: %s" % en)
            print("      RU: %s" % ru)
        tot += len(hits)
    print()
    print("ИТОГО:", tot)
