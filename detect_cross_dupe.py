# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: перевод одного абзаца попал в два блока.

При пересборке блоков старое «склеенное» состояние иногда переносится
на новые границы: перевод блока N уже заканчивался переводом абзаца N+1,
а сам абзац N+1 остался отдельным блоком со своим переводом. В PDF это
видно как повтор абзаца в правой колонке.

Проверка длины такое не ловит: 1358 символов оригинала против 1533
перевода — всего 113 %, порог 220 % далеко.

Как ищем: берём хвост перевода блока (последние два предложения) и
сравниваем его с переводом следующего блока по пересечению слов.
Формы слов расходятся («обработку» против «обработка»), поэтому
сравнение идёт по началам слов, а порог низкий — лучше проверить
руками, чем пропустить.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

RE_SENT = re.compile(r"(?<=[.!?:])\s+")
STOP = set("""и в во на не что с со как а но или для при по из от до за
это этот эта эти этого этой так также только уже его их тем том чем
которые который которая которое которых которым быть был была было
может могут можно если чтобы когда где""".split())


def stems(text):
    """Наборы начал слов длиной 5 — грубое выравнивание словоформ."""
    out = set()
    for w in re.findall(r"[A-Za-zА-Яа-яЁё0-9\-]{3,}", (text or "").lower()):
        if w in STOP:
            continue
        out.add(w[:5])
    return out


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def scan(num, threshold=0.35):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    blocks = obj["blocks"]
    tr = [(i, b) for i, b in enumerate(blocks)
          if b["kind"] in ("prose", "prose_cont")]
    out = []
    for k in range(len(tr) - 1):
        i, b = tr[k]
        j, nb = tr[k + 1]
        ru = (b.get("ru") or "").strip()
        nru = (nb.get("ru") or "").strip()
        if len(ru) < 120 or len(nru) < 40:
            continue
        sents = RE_SENT.split(ru)
        tail = " ".join(sents[-2:])
        if len(tail) < 40:
            continue
        score = jaccard(stems(tail), stems(nru))
        if score >= threshold:
            out.append((i, j, round(score, 2), tail[:70]))
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
        print("RFC %-5d подозрений на дубль: %d" % (n, len(hits)))
        for i, j, sc, t in hits:
            print("   блок %-5d -> %-5d сходство %.2f  хвост: %r" % (i, j, sc, t))
    print()
    print("ИТОГО: документов %d, подозрений %d" % (docs, tot))
