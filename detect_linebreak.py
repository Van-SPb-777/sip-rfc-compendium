# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: потеряны переводы строк исходника (строки склеены в абзац).

В RFC многие участки набраны построчно: примеры, списки URI, таблицы,
псевдографика, поля формы, перечисления вроде

    o  afraid
    o  amazed

Разборщик считает такие строки продолжением абзаца прозы и склеивает их
через пробел. В книге вместо пяти строк получается одна:

    sip:alice@atlanta.com sip:alice:secretword@atlanta.com;transport=tcp …

(так вышло с RFC 3261, §19.1.3 «Example SIP and SIPS URIs»).

КАК ИЩЕТСЯ

1. Для каждого блока вида prose/prose_cont/code/table/diagram находим его
   текст в исходнике rfc<N>.txt (колонтитулы страниц выброшены). Блок
   без переводов строк внутри сопоставляется участку исходника; если
   участок занимает 2+ строки — проверяем, был ли разрыв строки
   осмысленным.

2. Разрыв строки в исходнике считается ЖЁСТКИМ (структурным), если
   следующее слово поместилось бы на предыдущей строке: то есть строка
   кончилась не из-за ширины. Для этого считается свободное место
   (`ширина участка − длина строки`) и длина первого слова следующей
   строки. Если место есть — разрыв сделан намеренно, значит строки
   независимы, и склейка их в абзац — дефект.

   Признак устойчив: в обычном абзаце nroff заполняет строку до края, и
   только последняя строка абзаца бывает короткой. Поэтому одиночный
   «короткий хвост» дефектом не считается (это конец абзаца или стык
   абзацев через разрыв страницы), а вот ДВА и более жёстких разрыва
   подряд — уже структура.

3. Дополнительно ловятся короткие блоки (2–3 строки), целиком состоящие
   из строк-полей: «Content-type: …», «k=<method>», «Fax: …», «o …»,
   «a=<attribute>», URI-схем. У них жёсткий разрыв может быть один, но
   структурность видна по виду самих строк.

Печатает RFC, номер блока и число склеенных строк (строк исходника,
которые в блоке слиты в одну). ИТОГО — в конце.

Отдельно, не входя в ИТОГО, печатаются остатки оглавления: они тоже склеены
из строк, но чинятся удалением блока (это дефект проверки detect_toc).

Лечится `fix_linebreak.py`: en восстанавливается из исходника с переводами
строк; блок получает вид по содержимому (code/table/diagram/abnf), а
перевод — если он есть — сохраняется как есть.
"""
import io
import os
import re
import sys
from bisect import bisect_right
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store
import rfc_parse

_SRC_CANDS = (os.path.join(BASE, os.pardir, "rfc-sip"),
              os.path.join(BASE, os.pardir, os.pardir, "rfc-sip"))
SRC = os.path.abspath(
    os.environ.get("RFC_SRC")
    or next((p for p in _SRC_CANDS if os.path.isdir(p)), _SRC_CANDS[0]))
KINDS = ("prose", "prose_cont", "code", "table", "diagram")

# строки-«поля»: заголовок письма, атрибут SDP, определение ABNF, пункт списка
RE_FIELD = re.compile(r"^\s*[A-Za-z][A-Za-z0-9-]{0,32}:\s+\S")
RE_ABNF = re.compile(r"^\s*[A-Za-z][A-Za-z0-9-]{0,32}\s*=/?\s*\S")
RE_MARK = re.compile(r"^\s*(?:o|[-*+]|\d{1,2}[.)]|\(\d{1,2}\)|[a-zA-Z][.)])\s+\S")
RE_PIPE = re.compile(r"[|]|[+][-]{2,}")
RE_SCHEME = re.compile(r"^\s*(?:sips?|tels?|https?|mailto|urn|ftp):")
RE_TOC = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+[A-Z]")


def toc_like(en):
    """Блок — остаток оглавления: строки «N. Название» без конца фразы.

    Такой блок тоже склеен из строк, но чинится он не восстановлением
    переводов строк, а удалением (это отдельный дефект, проверка
    detect_toc). Здесь он только помечается, в дефекты не идёт.
    """
    lines = [ln.strip() for ln in (en or "").split("\n") if ln.strip()]
    if len(lines) < 2:
        return False
    n = sum(1 for ln in lines
            if RE_TOC.match(ln) and not ln.endswith((".", ":", ";")))
    return n >= 2 and n * 2 >= len(lines)


class Source(object):
    """Строки исходника с номерами; колонтитулы страниц выброшены.

    Пустые строки сохранены: по ним отличаем границу абзаца от разрыва
    страницы (rfc_parse.strip_running_heads выбрасывает пустые строки,
    относящиеся к разрыву страницы).
    """

    def __init__(self, num):
        self.num = num
        self.rows = []          # [(номер строки в файле, текст)]
        path = os.path.join(SRC, "rfc%d.txt" % num)
        try:
            raw = rfc_parse.load_text(path).replace("\r\n", "\n")
        except OSError:
            raw = None
        if raw is not None:
            pending, after_header = [], False
            for no, ln in enumerate(raw.split("\n"), 1):
                s = ln.strip()
                if (rfc_parse.RE_PAGE_FOOT.search(s)
                        or rfc_parse.RE_PAGE_HEAD.match(s)
                        or rfc_parse.RE_HEADER_INTERLEAVED.match(s)):
                    pending = []
                    after_header = True
                    continue
                if not s or s == "\f":
                    pending.append((no, ""))
                    continue
                if after_header:
                    pending = []
                    after_header = False
                self.rows.extend(pending)
                pending = []
                self.rows.append((no, ln.replace("\f", "")))
        # индекс «склеенного» текста исходника: позиция -> строка
        self.keep, self.starts, self.parts = [], [], []
        pos = 0
        for idx, (_no, ln) in enumerate(self.rows):
            t = " ".join(ln.split())
            if not t:
                continue
            self.keep.append(idx)
            self.starts.append(pos)
            self.parts.append(t)
            pos += len(t) + 1
        self.plain = " ".join(self.parts)
        self.ends = [s + len(p) for s, p in zip(self.starts, self.parts)]
        lens = [len(l.rstrip()) for (_n, l) in self.rows if l.strip()]
        # Ширина набора. Брать просто самую длинную строку нельзя: в
        # некоторых RFC (2327, 2198) одна-две строки вылезают за поля
        # набора, и тогда «свободное место» считается завышенным — обычные
        # абзацы начинают выглядеть как склеенные. Берём самую длинную
        # строку, которая встречается в документе не менее 5 раз.
        cand = [x for x in lens if x <= 100] or [72]
        cnt = Counter(cand)
        stable = [L for L, k in cnt.items() if k >= 5]
        self.margin = max(stable) if stable else max(cand)

    def span(self, en):
        """Позиция текста блока в склеенном исходнике."""
        t = " ".join((en or "").split())
        if not t:
            return None
        p = self.plain.find(t)
        if p < 0:
            return None
        q = p + len(t)
        i1 = bisect_right(self.starts, p) - 1
        i2 = bisect_right(self.starts, q - 1) - 1
        return (i1, i2, p, q)

    def region(self, sp):
        """[(номер строки, текст, строка целиком внутри блока)]."""
        i1, i2, p, q = sp
        out = []
        for i in range(i1, i2 + 1):
            idx = self.keep[i]
            out.append((self.rows[idx][0], self.rows[idx][1],
                        self.starts[i] >= p and self.ends[i] <= q))
        return out

    def blank_between(self, no_a, no_b):
        """Есть ли настоящая пустая строка между строками no_a и no_b."""
        for no, ln in self.rows:
            if no <= no_a:
                continue
            if no >= no_b:
                break
            if not ln.strip():
                return True
        return False


def structural_line(ln):
    return bool(RE_FIELD.match(ln) or RE_ABNF.match(ln) or RE_MARK.match(ln)
                or RE_PIPE.search(ln) or RE_SCHEME.match(ln))


def inspect(src, en):
    """Разбор участка исходника, занятого блоком. None — если он однострочный."""
    sp = src.span(en)
    if sp is None:
        return None
    reg = src.region(sp)
    full = [(no, ln) for (no, ln, f) in reg if f]
    if len(full) < 2:
        return None
    # ширина участка: отступ продолжений строк абзаца
    inds = [len(ln) - len(ln.lstrip()) for (_no, ln) in full[1:]]
    ts = Counter(inds).most_common(1)[0][0] if inds else 0
    width = src.margin - ts
    # абзацы: между настоящими пустыми строками
    runs, cur = [], [full[0]]
    for k in range(1, len(full)):
        if src.blank_between(full[k - 1][0], full[k][0]):
            runs.append(cur)
            cur = []
        cur.append(full[k])
    runs.append(cur)
    # жёсткие разрывы
    wide = []
    for run in runs:
        for k in range(len(run) - 1):
            no_a, a = run[k]
            no_b, b = run[k + 1]
            nw = re.match(r"\S+", b.strip())
            need = len(nw.group(0)) + 1 if nw else 99
            slack = width - len(a.rstrip())
            if slack >= need:
                wide.append((no_a, slack, need))
    wideset = set(x[0] for x in wide)
    chain = best = 0
    for run in runs:
        chain = 0
        for k in range(len(run) - 1):
            if run[k][0] in wideset:
                chain += 1
                best = max(best, chain)
            else:
                chain = 0
    nstruct = sum(1 for (_no, ln) in full if structural_line(ln))
    return dict(sp=sp, region=reg, full=full, n=len(full), runs=len(runs),
                wide=wide, chain=best, nstruct=nstruct,
                margin=src.margin, width=width)


def check(src, en):
    """Вернуть описание дефекта или None."""
    f = inspect(src, en)
    if not f:
        return None
    tocn = sum(1 for (_no, ln) in f["full"]
               if RE_TOC.match(ln) and not ln.rstrip().endswith((".", ":", ";")))
    f["toc"] = tocn >= 2 and tocn * 2 >= f["n"]
    if f["chain"] >= 2:
        return f
    # короткий блок целиком из строк-полей
    if (f["chain"] >= 1 and f["nstruct"] >= 2
            and f["nstruct"] * 10 >= f["n"] * 6):
        return f
    return None


def scan(num):
    """Список дефектов: dict(i, n, region, ...)."""
    return _scan(num, toc=False)


def scan_toc(num):
    """Блоки-остатки оглавления (отдельный дефект, см. detect_toc)."""
    return _scan(num, toc=True)


def _scan(num, toc):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        # excluded — документ вне собрания; skip_translation — оставлен
        # без перевода (RFC 2543), его правки запрещены
        return []
    try:
        src = Source(num)
    except OSError:
        return []
    if not src.rows:
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b["kind"] not in KINDS:
            continue
        en = b.get("en") or ""
        if "\n" in en:
            continue
        d = check(src, en)
        if not d or d["toc"] != toc:
            continue
        d["i"] = i
        d["kind0"] = b["kind"]
        d["en"] = en
        out.append(d)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    tocs = 0
    docs = 0
    for n in nums:
        hits = scan(n)
        for h in scan_toc(n):
            tocs += 1
            print("RFC %-5d блок %-5d: остаток оглавления (чинится удалением,"
                  " см. detect_toc) — не считается" % (n, h["i"]))
        if not hits:
            continue
        docs += 1
        print("RFC %-5d склеенных строк: %s" % (n, [h["i"] for h in hits]))
        for h in hits:
            print("        блок %-5d kind=%-8s строк: %d  %r"
                  % (h["i"], h["kind0"], h["n"], h["en"][:70]))
        tot += len(hits)
    print()
    print("документов с дефектом: %d" % docs)
    if tocs:
        print("пропущено остатков оглавления: %d (отдельный дефект)" % tocs)
    print("ИТОГО:", tot)
    return 1 if tot else 0


if __name__ == "__main__":
    sys.exit(main())
