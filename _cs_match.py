# -*- coding: utf-8 -*-
"""Поиск блока в исходнике: точное совпадение слов, при неудаче — локальное
выравнивание difflib (допускает мелкие расхождения вроде потерянной ';')."""
import os
import difflib
import re

import _cs_lib

FURN_FOOT = _cs_lib.RE_PAGE_FOOT
FURN_HEAD = _cs_lib.RE_PAGE_HEAD
RE_FURN_ANY = re.compile(r"\[Page \d+\]")


def clean_block_text(en):
    """Убрать из текста блока колонтитулы страниц (если парсер их втянул)."""
    out = []
    for ln in (en or "").split("\n"):
        if FURN_FOOT.search(ln):
            continue
        if FURN_HEAD.match(ln):
            continue
        out.append(ln)
    return "\n".join(out)


def words_with_gaps(text):
    words, gaps = [], []
    pos = 0
    for m in re.finditer(r"\S+", text):
        if words:
            gaps.append(text[pos:m.start()])
        words.append(m.group(0))
        pos = m.end()
    return words, gaps


def _best_after(cands, last):
    after = [p for p in cands if p >= last]
    return after[0] if after else cands[-1]


def match_block(idx, words, last=0, min_ratio=0.8):
    """Вернуть dict(p, mapping, ratio, exact) или None.

    p       — индекс первого слова в исходнике
    mapping — список (j_block, k_source) для совпавших слов подряд
    ratio   — доля совпавших слов блока
    """
    cands = idx.find(words)
    if cands:
        p = _best_after(cands, last)
        mapping = [(j, p + j) for j in range(len(words))]
        return {"p": p, "mapping": mapping, "ratio": 1.0, "exact": True,
                "end": p + len(words) - 1}
    # локальное выравнивание: якорь — первые 4..2 слова
    for k in (4, 3, 2):
        if len(words) < k:
            continue
        anchors = idx.find(words[:k])
        best = None
        for a in anchors:
            lo = max(0, a - 3)
            hi = min(len(idx.words), a + int(len(words) * 1.4) + 20)
            win = idx.words[lo:hi]
            sm = difflib.SequenceMatcher(None, words, win, autojunk=False)
            blocks = [b for b in sm.get_matching_blocks() if b.size]
            if not blocks:
                continue
            matched = sum(b.size for b in blocks)
            ratio = matched / float(len(words))
            if best is None or ratio > best[1]:
                best = (a, ratio, lo, blocks)
        if best and best[1] >= min_ratio:
            a, ratio, lo, blocks = best
            mapping = []
            for b in blocks:
                for t in range(b.size):
                    mapping.append((b.a + t, lo + b.b + t))
            p = mapping[0][1]
            return {"p": p, "mapping": mapping, "ratio": ratio, "exact": False,
                    "end": mapping[-1][1]}
    return None


def span_lines(idx, p, end):
    li0 = idx.toks[p][0]
    li1 = idx.toks[end][0]
    return li0, li1


def bad_line_numbers(idx, m, bgaps):
    """Номера строк исходника, где потеряны кратные пробелы."""
    bad = set()
    mapping = m["mapping"]
    for a in range(len(mapping) - 1):
        j1, k1 = mapping[a]
        j2, k2 = mapping[a + 1]
        if j2 != j1 + 1 or k2 != k1 + 1:
            continue
        li1, b1 = idx.toks[k1][0], idx.toks[k1][2]
        li2, a2 = idx.toks[k2][0], idx.toks[k2][1]
        if li1 != li2:
            continue
        sg = idx.lines[li1][b1:a2]
        if "  " not in sg:
            continue
        if "  " in bgaps[j1]:
            continue
        bad.add(li1)
    return sorted(bad)
