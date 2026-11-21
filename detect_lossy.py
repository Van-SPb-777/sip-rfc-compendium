# -*- coding: utf-8 -*-
"""
Поиск «тихой» потери в переводе — текст есть, но он не весь.

Порог 75% ловит грубые обрывы. Но бывает так: RU короче EN на 10-20%,
порог пройден, а по смыслу потерян хвост. Ищем признаки:

  A. RU кончается на предлог/союз («в», «на», «разделе», «и», «для»…) —
     фраза явно не закончена.
  B. EN содержит приглашение к примеру («might look like», «may look like»,
     «would look like», «looks like this») — а в RU его нет.
  C. EN содержит ссылку «Section N» / «Figure N» в хвосте, а в RU нет
     соответствующего «раздел»/«рисунок».
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

# Слова, на которых перевод не может закончиться
BAD_TAIL = re.compile(
    r"\b(в|на|о|об|из|к|по|для|при|с|со|от|до|за|под|над|без|через|"
    r"разделе|разделу|раздела|главе|рисунке|таблице|пункте|"
    r"и|или|но|а|что|как|который|которая|которое|которые|"
    r"the|of|in|to|and|or|is|are)\s*$", re.I)

# Приглашение к примеру в оригинале
LOOK_LIKE = re.compile(
    r"(might|may|would|will)\s+look\s+like|looks\s+like|"
    r"as\s+Bob\s+sends|as\s+shown\s+below|is\s+shown\s+below", re.I)
LOOK_LIKE_RU = re.compile(
    r"может\s+выглядеть|могут\s+выглядеть|выглядит\s+так|"
    r"выглядят\s+так|как\s+отправляет|как\s+показано", re.I)

# Ссылка на раздел/рисунок
REF = re.compile(r"\b(Section|Figure|Table)\s+(\d+(?:\.\d+)*)", re.I)
REF_RU = re.compile(r"(раздел|рисун|таблиц)", re.I)


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b["kind"] not in ("heading", "prose", "prose_cont"):
            continue
        en = (b.get("en") or "").strip()
        ru = (b.get("ru") or "").strip()
        if not en or not ru or len(en) < 120:
            continue
        reasons = []
        # A. RU заканчивается на служебное слово
        if BAD_TAIL.search(ru[-60:]):
            reasons.append("оборвано на служебном слове")
        # B. приглашение к примеру потеряно
        if LOOK_LIKE.search(en) and not LOOK_LIKE_RU.search(ru):
            reasons.append("потеряно «может выглядеть так»")
        # C. ссылка на раздел/рисунок потеряна
        en_refs = set(m.group(2) for m in REF.finditer(en))
        ru_refs = set(re.findall(r"\d+(?:\.\d+)*", ru))
        lost = en_refs - ru_refs
        if lost and REF_RU.search(ru):
            reasons.append("потеряны ссылки %s" % sorted(lost)[:4])
        if reasons:
            out.append((i, b["kind"], round(len(ru) / len(en), 2), reasons, en[:90]))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    total = 0
    for n in nums:
        hits = scan(n)
        if not hits:
            continue
        total += len(hits)
        print("RFC %-5d подозрений: %d" % (n, len(hits)))
        for i, k, r, rs, s in hits[:12]:
            print("   блок %-5d [%s] ratio=%.2f: %s" % (i, k, r, "; ".join(rs)))
            print("      EN: %s" % s)
    print()
    print("ИТОГО подозрений:", total)
