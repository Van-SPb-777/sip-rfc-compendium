# -*- coding: utf-8 -*-
"""ПРОВЕРКА urlcase: в переводе изменён регистр URI/URL.

Схема URI и путь чувствительны к регистру (RFC 3986, §3.1: «scheme names
are case-insensitive», но сами схемы и путь принято писать строчными;
примеры RFC 3986 §1.1.2 даны строчными). При переводе первую букву
строки иногда «капитализируют», и пример `ftp://…` превращается в
`Ftp://…` — это уже другой URI.

Практика QA: проверки «Numbers / Tags / Placeholders consistency»
(Smartling, https://www.smartling.com/questions/automated-translation-consistency-checking)
и «Tag, Placeholder and Number Consistency» из контрольных списков
переводчика (JAT, https://jat.org/blog/checklist_for_translators) требуют,
чтобы технические литералы переносились в перевод без изменений.

Как ищем: URI из `en` нет в `ru` дословно, но есть без учёта регистра —
значит изменена только капитализация. Сравнение идёт по всем схемам,
которые встречаются в RFC (http, ftp, mailto, urn, tel, ldap, news…).

Запуск: python detect_urlcase.py [N[,N]]
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

SCHEMES = ("https?|ftps?|sips?|sftp|mailto|urn|tel|telnet|ldap|news|imap|"
           "ssh|file|data|nfs|rtsp|ws|wss")
RE_URI = re.compile(r"\b(?:%s):[^\s<>\"'«»]+" % SCHEMES, re.I)


def clean_uri(u):
    return u.rstrip(".,;:!?)»")


def scan(num):
    """Вернуть список (i, uri_en, вариант_в_ru)."""
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    out = []
    for i, b in enumerate(obj.get("blocks") or []):
        en, ru = b.get("en") or "", b.get("ru") or ""
        if not en or not ru:
            continue
        low = ru.lower()
        for m in RE_URI.finditer(en):
            uri = clean_uri(m.group(0))
            if not uri or uri in ru:
                continue
            if uri.lower() not in low:
                continue
            # нашли вариант в переводе — покажем его
            variant = next((clean_uri(x) for x in RE_URI.findall(ru)
                            if clean_uri(x).lower() == uri.lower()), "")
            out.append((i, uri, variant))
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
        for i, uri, variant in hits:
            print("   блок %-5d EN: %s" % (i, uri))
            print("               RU: %s" % (variant or "—"))
    print()
    print("ИТОГО: %d URI с изменённым регистром в %d документах" % (total, docs))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
