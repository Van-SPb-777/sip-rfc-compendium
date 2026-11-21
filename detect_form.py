# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: поля формы (разделы IANA и «Authors' Addresses») склеены в строку.

В RFC такие разделы набраны формой: каждое поле с новой строки,
«Поле: значение». Разборщик иногда сливает несколько полей в одну строку:

    Magic number(s): None File extension(s): None Macintosh File Type Code(s): None

Отличать от обычной прозы надо по словарю меток: у формы свои, узнаваемые
названия полей. Если в одной строке встретились две и более метки из
списка — это склейка.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

# метки, которые встречаются в формах IANA и в разделе авторов
LABELS = [
    "Contact", "Author", "Change controller", "Magic number(s)",
    "File extension(s)", "Macintosh File Type Code(s)", "Intended usage",
    "Published specification", "Applications which use this media type",
    "Applications which use", "Person & email address to contact",
    "Additional information", "Registration", "Parameter name",
    "Header field", "Formal syntax", "Purpose", "Reference",
    "Predefined value", "Applicable", "String value", "E-mail",
]
RE_LABEL = re.compile(r"(?:%s)\s*:" % "|".join(re.escape(x) for x in LABELS))
KINDS = ("prose", "prose_cont")


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b.get("kind") not in KINDS:
            continue
        for ln in (b.get("en") or "").split("\n"):
            if len(RE_LABEL.findall(ln)) >= 2:
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
            print("RFC %-5d склеено полей формы: %s" % (n, hits[:8]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
