# -*- coding: utf-8 -*-
"""
ПРОВЕРКА paracount: структура абзацев блока должна совпадать с исходником.

В RFC абзацы разделены пустыми строками, а определения и пункты часто
набраны с отступом. Разборщик иногда склеивает несколько таких абзацев в
один блок (или наоборот режет один абзац надвое). В книге это выглядит как
«перевод уехал»: абзацы EN и RU не совпадают по границам.

Как считаем:
  * берём текст блока, ищем его в исходнике (после снятия колонтитулов);
  * в найденном участке считаем границы абзацев: пустая строка;
  * сравниваем с числом абзацев внутри блока (по пустым строкам).
"""
import os
import io
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store
import rfc_parse

_SRC_CANDS = (os.path.join(BASE, os.pardir, "rfc-sip"),
              os.path.join(BASE, os.pardir, os.pardir, "rfc-sip"))
SRC = os.path.abspath(
    os.environ.get("RFC_SRC")
    or next((p for p in _SRC_CANDS if os.path.isdir(p)), _SRC_CANDS[0]))


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def source_flat(num):
    path = "%s\\rfc%d.txt" % (SRC, num)
    try:
        lines = rfc_parse.strip_running_heads(rfc_parse.load_text(path).split("\n"))
    except OSError:
        return None, []
    flat, breaks, pos, prev_blank = [], [], 0, True
    for ln in lines:
        if not ln.strip():
            prev_blank = True
            continue
        # двойные пробелы внутри строки (в RFC после точки их часто два)
        # схлопываем: в хранилище они уже схлопнуты, иначе find() не сработает
        t = re.sub(r"\s+", " ", ln).strip()
        if prev_blank and flat:
            breaks.append(pos)
        flat.append(t)
        pos += len(t) + 1
        prev_blank = False
    return " ".join(flat), breaks


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    flat, breaks = source_flat(num)
    if not flat:
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b.get("kind") not in ("prose", "prose_cont"):
            continue
        en = norm(b.get("en"))
        if len(en) < 120:
            continue
        start = flat.find(en[:60])
        if start < 0:
            continue
        end = start + len(en)
        if flat[start:end] != en:
            pos = flat.find(en)
            if pos < 0:
                continue
            start, end = pos, pos + len(en)
        inside = sum(1 for p in breaks if start < p < end)
        if inside >= 1:
            out.append((i, inside))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    total = 0
    docs = 0
    for n in nums:
        hits = scan(n)
        if hits:
            docs += 1
            total += len(hits)
            print("RFC %-5d склеенных блоков: %d  %s" % (n, len(hits), [h[0] for h in hits][:6]))
    print()
    print("ИТОГО: %d блоков в %d документах" % (total, docs))
