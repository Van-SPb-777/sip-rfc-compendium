# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: раздел выпал из документа.

Заголовки в RFC нумерованы: 1, 2, 3, 3.1, 3.2, 4… Если в хранилище
последовательность идёт «1, 2, 4», значит заголовок раздела потерян —
его случайно удалили или он разобрался как проза и потом был вычищен.

Проверяются только заголовки верхнего уровня и подразделы внутри одного
родителя: пропуск «3.1 → 3.3» тоже дефект, а «3.2 → 4» — нормально.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
_SRC_CANDS = (os.path.join(BASE, os.pardir, "rfc-sip"),
              os.path.join(BASE, os.pardir, os.pardir, "rfc-sip"))
SRC = os.path.abspath(
    os.environ.get("RFC_SRC")
    or next((p for p in _SRC_CANDS if os.path.isdir(p)), _SRC_CANDS[0]))
sys.path.insert(0, BASE)
import store

RE_NUM = re.compile(r"^(\d{1,2})(?:\.(\d{1,2}))?\.?\s+\S")


def nums(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b.get("kind") != "heading":
            continue
        m = RE_NUM.match((b.get("en") or "").strip())
        if not m:
            continue
        out.append((i, int(m.group(1)), int(m.group(2)) if m.group(2) else None))
    return out


def in_source(num, section):
    """Есть ли такой раздел в исходнике: номер отдельной строкой."""
    import io, os
    path = os.path.join(SRC, "rfc%d.txt" % num)
    try:
        src = io.open(path, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
    except OSError:
        return True
    return bool(re.search(r"^\s*%s\.\s+\S" % re.escape(str(section)), src, re.M))


def scan(num):
    seq = nums(num)
    present = {t for _i, t, _s in seq}
    bad = []
    prev_top = None
    prev_sub = None
    for i, top, sub in seq:
        if top != prev_top:
            # новый раздел верхнего уровня: номер должен идти подряд
            if prev_top is not None and top not in (prev_top, prev_top + 1):
                if (top > prev_top + 1 and in_source(num, prev_top + 1)
                        and (prev_top + 1) not in present):
                    bad.append((i, "после %d идёт %d" % (prev_top, top)))
            prev_top, prev_sub = top, sub
            continue
        if sub is not None and prev_sub is not None and sub > prev_sub + 1:
            bad.append((i, "в разделе %d пропущен %d.%d" % (top, top, prev_sub + 1)))
        prev_sub = sub if sub is not None else prev_sub
    return bad


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ns = ([int(a) for a in args[0].split(",")] if args
          else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in ns:
        hits = scan(n)
        if hits:
            print("RFC %-5d пропуск раздела: %s" % (n, hits[:4]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
