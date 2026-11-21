# -*- coding: utf-8 -*-
"""ПРОВЕРКА dupword: в переводе подряд стоит одно и то же слово.

Класс ошибки — «repeated words» из контрольных списков QA перевода:
  * Okapi CheckMate, набор проверок качества (repeated words, corrupted
    characters) — https://okapiframework.org/wiki/index.php?title=CheckMate
  * каталог сервисов CEF AT: «Repeated words, Corrupted characters,
    Patterns» — https://cef-at-service-catalogue.eu/catalogue/browse/fd8c9fcf-032f-4326-ae15-f537d183690e/
  * MQM, категория Fluency/Linguistic conventions (опечатки, пунктуация) —
    https://www.themqm.org/mqm-pillars/typology/

Ловим только кириллические слова из 2+ букв, разделённые ОДНИМ пробелом
(в таблицах и схемах кратные пробелы — выравнивание колонок, это не дефект).
Технические повторы латиницы (REC REC-xml..., URI URI, ISO ISO/IEC) и
конструкции вида «что что-то» намеренно не считаются: они законны.

Запуск: python detect_dupword.py [N[,N]]
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

RE_DUP = re.compile(r"(?<![\w-])([А-Яа-яЁё]{2,})[ \u00a0]\1(?![\w-])", re.I)
CYR = re.compile(r"[А-Яа-яЁё]")


def scan(num):
    """Вернуть список (i, word, контекст)."""
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    out = []
    for i, b in enumerate(obj.get("blocks") or []):
        if b.get("kind") not in ("prose", "prose_cont", "heading"):
            continue
        ru = b.get("ru") or ""
        if not CYR.search(ru):
            continue
        for m in RE_DUP.finditer(ru):
            out.append((i, m.group(0),
                        ru[max(0, m.start() - 45):m.end() + 35].replace("\n", "|")))
    return out


def doc_numbers(argv):
    args = [a for a in argv if not a.startswith("--")]
    if args:
        nums = []
        for a in args:
            nums.extend(int(x) for x in a.split(",") if x.strip())
        return nums
    return sorted(x for x in store.status_report() if isinstance(x, int))


def main():
    total = docs = 0
    for n in doc_numbers(sys.argv[1:]):
        hits = scan(n)
        if not hits:
            continue
        docs += 1
        total += len(hits)
        print("RFC %d: %d" % (n, len(hits)))
        for i, word, ctx in hits:
            print("   блок %-5d %-12r %s" % (i, word, ctx))
    print()
    print("ИТОГО: %d повторов в %d документах" % (total, docs))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

# повтор фразы из двух слов: «Поле заголовка Поле заголовка»
PHRASE = re.compile(r"\b((?:[А-Яа-яЁёA-Za-z]{3,})(?:\s+[А-Яа-яЁёA-Za-z]{3,})?)\s+\1\b", re.I)


def scan_phrases(num):
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b.get("kind") not in ("prose", "prose_cont"):
            continue
        ru = b.get("ru") or ""
        en = (b.get("en") or "").lower()
        # если в оригинале тоже есть повтор (шапка таблицы), это не дефект
        if re.search(r"\\b(\\w{3,})\\s+\\1\\b", en):
            continue
        for m in PHRASE.finditer(ru):
            if m.group(1).lower() in en:
                continue
            out.append(i)
            break
    return out
