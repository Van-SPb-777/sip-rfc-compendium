# -*- coding: utf-8 -*-
"""
ПРОТОТИП ПРОВЕРКИ: числа, потерянные при переводе.

Числа в техническом RFC не переводятся: коды ответов (481), таймеры
(64*T1), размеры (32 бита), номера разделов (21). Если в английском
блоке есть число, а в переводе его нет — это почти всегда потеря
смысла, а не стилистическая вольность.

Сравниваем последовательности цифр, игнорируя разделители: «1,5» и «1.5»
дают одну и ту же последовательность. Числа из 1 цифры игнорируем —
слишком много случайных совпадений («0», «1» в перечислениях).
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

# последовательности цифр длиной 2 и более
RE_NUM = re.compile(r"\d{2,}")
# разделители тысяч: запятая («8,000») и пробел («16 000»).
#
# Пробел убираем ТОЛЬКО если перед группой цифр нет точки или цифры —
# иначе номер раздела «21.1.1 100 Trying» превратится в ложное число
# «1100» и проверка будет ругаться на исправный текст.
RE_THOUSANDS_COMMA = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
RE_THOUSANDS_SPACE = re.compile(r"(?<![\d.])(\d{1,3})[ \u00a0\u2009\u202f](?=\d{3}(?!\d))")


def normalize(text):
    """Убрать разделители тысяч, чтобы «8,000», «16 000» и «8000» совпали."""
    t = text or ""
    for _ in range(3):
        t = RE_THOUSANDS_COMMA.sub("", t)
        t = RE_THOUSANDS_SPACE.sub(r"\1", t)
    return t


def numbers(text):
    return set(RE_NUM.findall(normalize(text)))


def looks_like_table(text):
    """Блок похож на таблицу или ASCII-схему: много выровненных пробелов.

    В таких блоках числа стоят в колонках и в перевод не попадают —
    это нормально, колонка схемы переносится как есть. Проверять их
    на «потерю чисел» бессмысленно.
    """
    t = text or ""
    if "+-" in t or "|" in t and t.count("|") >= 4:
        return True
    gaps = len(re.findall(r"\S {2,}\S", t))
    return gaps >= 3


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b["kind"] not in ("heading", "prose", "prose_cont"):
            continue
        en = b.get("en") or ""
        ru = b.get("ru") or ""
        if not ru.strip() or len(en) < 60:
            continue
        if looks_like_table(en):
            continue
        en_n = numbers(en)
        ru_n = numbers(ru)
        lost = en_n - ru_n
        if lost:
            out.append((i, sorted(lost)[:8], en[:80]))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    docs = 0
    for n in nums:
        hits = scan(n)
        if not hits:
            continue
        docs += 1
        tot += len(hits)
        print("RFC %-5d блоков с потерянными числами: %d" % (n, len(hits)))
        for i, lost, s in hits[:5]:
            print("   блок %-5d потеряно %s" % (i, lost))
            print("      EN: %s" % s)
    print()
    print("ИТОГО: документов %d, блоков %d" % (docs, tot))
