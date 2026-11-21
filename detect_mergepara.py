# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: в один блок склеены два абзаца.

Признак надёжный и внешний — исходный .txt. Если текст блока в исходнике
занимает место, где между строками была ПУСТАЯ строка, значит в оригинале
там граница абзаца, а в книге она потеряна: два абзаца склеились в один.

Пустые строки от колонтитулов и разрывов страниц заранее убираются
(strip_running_heads), поэтому остаются только настоящие границы абзацев.
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


def source_of(num):
    """Склеенный текст исходника и позиции границ абзацев."""
    path = "%s\\rfc%d.txt" % (SRC, num)
    try:
        lines = rfc_parse.strip_running_heads(rfc_parse.load_text(path).split("\n"))
    except OSError:
        return None, []
    flat = []
    breaks = []
    pos = 0
    prev_blank = True
    for ln in lines:
        if not ln.strip():
            prev_blank = True
            continue
        t = ln.strip()
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
    flat, breaks = source_of(num)
    if not flat:
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b.get("kind") not in ("prose", "prose_cont"):
            continue
        en = norm(b.get("en"))
        if len(en) < 250:
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
        inside = [p for p in breaks if start < p < end]
        if inside:
            out.append((i, len(inside)))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        hits = scan(n)
        if hits:
            print("RFC %-5d склеенных абзацев: %s" % (n, hits[:6]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
