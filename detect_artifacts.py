# -*- coding: utf-8 -*-
"""ПРОВЕРКА artifacts: в тексте остались колонтитулы страниц и служебные символы.

Источник правил — формат RFC (ASCII, 58 строк на страницу, разрыв страницы
символом form feed, верхний колонтитул "RFC NNNN ... Month YYYY", нижний
колонтитул "Author ... [Page NN]"):
  * RFC 2223, раздел 3 «Format Rules» — https://www.rfc-editor.org/rfc/rfc2223
  * черновик rfc2223bis, «Running Headers / Running Footers» —
    https://datatracker.ietf.org/doc/html/draft-rfc-editor-rfc2223bis-05
  * утилита rfcstrip, которая срезает именно эту «обвязку» —
    https://github.com/ietf-tools/rfcstrip
  * регулярка нижнего колонтитула из mnot/rfc-refs —
    https://github.com/mnot/rfc-refs/blob/main/extract-refs.py

По правилам проекта (ПРАВИЛА-ПРАВОК.md, п.1) колонтитулы и \\x0c из `en`
убираются. Если они всё-таки попали в блок, книга печатает «[Page 20]»
посреди абзаца или таблицы, а BOM (\\ufeff) даёт невидимый символ в начале
блока. Проверка ищет:
  * BOM и управляющие символы (кроме \\n и \\t) в `en` и `ru`;
  * строку нижнего колонтитула «... [Page NN]»;
  * строку верхнего колонтитула «RFC NNNN ... <Месяц> <год>».

Запуск: python detect_artifacts.py [N[,N]]
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

MONTHS = ("January|February|March|April|May|June|July|August|September|"
          "October|November|December")
RE_FOOTER = re.compile(r"^\s*\S.*\s{2,}\[Page \d+\]\s*$")
RE_HEADER = re.compile(r"^\s*RFC\s+\d+\s+.*\b(?:%s)\s+\d{4}\s*$" % MONTHS)
BAD_CTRL = re.compile(r"[\ufeff\x0b\x0c\x00-\x08\x0e-\x1f]")


def scan(num):
    """Вернуть список (i, kind, reason, фрагмент)."""
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    out = []
    for i, b in enumerate(obj.get("blocks") or []):
        for field in ("en", "ru"):
            text = b.get(field) or ""
            if not text:
                continue
            m = BAD_CTRL.search(text)
            if m:
                out.append((i, b.get("kind"), "%s: служебный символ %r"
                            % (field, m.group(0)), text[max(0, m.start() - 30):m.start() + 30]))
                continue
            for line in text.split("\n"):
                if RE_FOOTER.match(line):
                    out.append((i, b.get("kind"), "%s: нижний колонтитул" % field,
                                line.strip()[:70]))
                    break
                if RE_HEADER.match(line):
                    out.append((i, b.get("kind"), "%s: верхний колонтитул" % field,
                                line.strip()[:70]))
                    break
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
        for i, kind, reason, frag in hits:
            print("   блок %-5d %-7s %s | %r" % (i, kind, reason, frag))
    print()
    print("ИТОГО: %d находок в %d документах" % (total, docs))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
