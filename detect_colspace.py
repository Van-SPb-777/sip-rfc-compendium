# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: схлопнутые пробелы в таблицах и схемах.

В сборнике есть блоки, где таблица или схема нарисована пробелами. При
разборе кратные пробелы схлопнулись в один, и выравнивание колонок
потерялось: подписи съехали, строки слиплись. Пример — RFC 3261 §19.1.2,
таблица 1 «Use and default values of URI components»: в исходнике ровные
колонки user/password/host/port, в блоке «user -- o o o o o o ...».

Как ищем:
  1. берём текст блока kind in (diagram, table, code);
  2. ищем этот участок в исходнике rfc-sip/rfc<N>.txt (колонтитулы
     страниц сняты), сравнивая поток слов — так находится и блок,
     в котором потеряны переводы строк;
  3. для каждой пары соседних слов исходника смотрим промежуток: если в
     исходнике между ними 2+ пробела, а в блоке на этом месте пробел
     один (или промежуток потерян), строка считается испорченной.

Печатает RFC, номер блока, число испорченных строк. Запуск:
    python detect_colspace.py            # все документы
    python detect_colspace.py 3261       # один
    python detect_colspace.py 3261,3265  # несколько
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store
import _cs_lib
import _cs_match

SKIP = {2543}          # этот документ не трогаем (см. ПРАВИЛА-ПРАВОК)


def scan(num):
    """Вернуть (hits, nomatch). hits: список dict(i, kind, bad, span)."""
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return None
    src = _cs_lib.load_src(num)
    if src is None:
        return None
    idx = _cs_lib.SrcIndex(src)
    hits, nomatch = [], []
    last = 0
    for i, b in enumerate(obj["blocks"]):
        if b.get("kind") not in ("diagram", "table", "code"):
            continue
        text = _cs_match.clean_block_text(b.get("en") or "")
        words, gaps = _cs_match.words_with_gaps(text)
        if not words:
            continue
        m = _cs_match.match_block(idx, words, last)
        if not m:
            nomatch.append(i)
            continue
        last = m["end"] + 1
        m["start_line"], m["end_line"] = _cs_match.span_lines(idx, m["p"], m["end"])
        bad = _cs_match.bad_line_numbers(idx, m, gaps)
        if bad:
            hits.append({"i": i, "kind": b["kind"], "bad": bad,
                         "match": m, "words": words, "gaps": gaps})
    return hits, nomatch


def doc_numbers(argv):
    args = [a for a in argv if not a.startswith("--")]
    if args:
        nums = []
        for a in args:
            nums.extend(int(x) for x in a.split(",") if x.strip())
        return nums
    return sorted(int(f[3:-5]) for f in os.listdir(store.TRANS)
                  if f.startswith("rfc") and f.endswith(".json"))


def main():
    nums = doc_numbers(sys.argv[1:])
    tot_docs = tot_blocks = tot_lines = 0
    for n in nums:
        if n in SKIP:
            print("RFC %d: пропущен (не трогаем)" % n)
            continue
        r = scan(n)
        if r is None:
            print("RFC %d: нет данных" % n)
            continue
        hits, nomatch = r
        if not hits:
            print("RFC %d: 0" % n)
            continue
        tot_docs += 1
        tot_blocks += len(hits)
        lines = 0
        for h in hits:
            lines += len(h["bad"])
        tot_lines += lines
        print("RFC %d: блоков %d, испорчено строк %d" % (n, len(hits), lines))
        for h in hits:
            m = h["match"]
            print("   блок %-5d %-7s строк %-3d (исходник %d..%d%s)"
                  % (h["i"], h["kind"], len(h["bad"]),
                     m["start_line"] + 1, m["end_line"] + 1,
                     "" if m["exact"] else ", неточное совпадение %.2f" % m["ratio"]))
        if nomatch:
            print("   не найдено в исходнике: %s"
                  % ", ".join(str(i) for i in nomatch))
    print()
    print("ИТОГО: документов %d, блоков %d, испорчено строк %d"
          % (tot_docs, tot_blocks, tot_lines))
    return 1 if tot_blocks else 0


if __name__ == "__main__":
    sys.exit(main())
