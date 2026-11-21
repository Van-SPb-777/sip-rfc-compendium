# -*- coding: utf-8 -*-
"""Общие функции: поиск текста блока в исходнике RFC."""
import os
import re
BASE = os.path.dirname(os.path.abspath(__file__))

_SRC_CANDS = (os.path.join(BASE, os.pardir, "rfc-sip"),
              os.path.join(BASE, os.pardir, os.pardir, "rfc-sip"))
SRC = os.path.abspath(
    os.environ.get("RFC_SRC")
    or next((p for p in _SRC_CANDS if os.path.isdir(p)), _SRC_CANDS[0]))

RE_PAGE_FOOT = re.compile(r"\[Page \d+\]")
RE_PAGE_HEAD = re.compile(
    r"^RFC \d+\s+.*\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{4}\s*$")


def load_src(num):
    """Исходник без колонтитулов. Возвращает список строк (как есть).

    Пустые строки, примыкающие к снятому колонтитулу, — след разрыва
    страницы; они выбрасываются, чтобы таблица через разрыв не получила
    пустые строки. Одиночные пустые строки внутри текста сохраняются.
    """
    p = os.path.join(SRC, "rfc%d.txt" % num)
    if not os.path.exists(p):
        return None
    raw = open(p, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
    lines = []
    after_break = False
    for ln in raw.split("\n"):
        if RE_PAGE_FOOT.search(ln) or RE_PAGE_HEAD.match(ln) or ln.strip() == "\x0c":
            # хвостовые пустые строки перед колонтитулом — тоже разрыв
            while lines and not lines[-1].strip():
                lines.pop()
            after_break = True
            continue
        if "\x0c" in ln:
            ln = ln.replace("\x0c", "")
        if after_break and not ln.strip():
            continue
        if ln.strip():
            after_break = False
        lines.append(ln)
    return lines


def tokenize(lines):
    """Плоский поток слов с координатами: [(line_idx, start, end), ...]."""
    toks = []
    for li, ln in enumerate(lines):
        for m in re.finditer(r"\S+", ln):
            toks.append((li, m.start(), m.end()))
    return toks


class SrcIndex(object):
    """Индекс исходника: поток слов и поиск подпоследовательности."""

    def __init__(self, lines):
        self.lines = lines
        self.toks = tokenize(lines)
        self.words = [lines[li][a:b] for (li, a, b) in self.toks]
        # первый/последний токен каждой строки
        self.line_first = {}
        self.line_last = {}
        for k, (li, a, b) in enumerate(self.toks):
            self.line_first.setdefault(li, k)
            self.line_last[li] = k
        # индекс по первым 6 словам (для быстрого поиска)
        self.by_head = {}
        for i in range(len(self.words) - 5):
            key = tuple(self.words[i:i + 6])
            self.by_head.setdefault(key, []).append(i)

    def find(self, block_tokens):
        """Вернуть список позиций (индексов в self.toks), где блок совпал целиком."""
        n = len(block_tokens)
        if n == 0:
            return []
        if n < 6:
            # короткий блок — линейный поиск
            out = []
            for i in range(len(self.words) - n + 1):
                if self.words[i:i + n] == block_tokens:
                    out.append(i)
            return out
        key = tuple(block_tokens[:6])
        cands = self.by_head.get(key, [])
        out = []
        for i in cands:
            if i + n > len(self.words):
                continue
            if self.words[i:i + n] == block_tokens:
                out.append(i)
        return out

    def gaps(self, start, n):
        """Промежутки между соседними словами и границы строк.

        Возвращает список (line_idx, gap_text) длиной n-1 где gap_text —
        исходная подстрока между концом слова k и началом слова k+1.
        """
        res = []
        for k in range(start, start + n - 1):
            li1, a1, b1 = self.toks[k]
            li2, a2, b2 = self.toks[k + 1]
            if li1 == li2:
                res.append((li1, self.lines[li1][b1:a2]))
            else:
                # между строками: сшиваем хвост и начала; для анализа хватает
                res.append((li2, "\n"))
        return res
