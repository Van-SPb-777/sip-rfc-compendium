# -*- coding: utf-8 -*-
"""
ПРОВЕРКИ: список, размеченный как код; заголовок, слипшийся с абзацем.

1) codelist — блок kind=code/table/diagram состоит из коротких строк вида
   «1. Reasonable Syntax», «5. Proxy-Require». Это перечисление, а не код:
   в книге оно печатается моноширинным и без перевода справа.

2) headglue — блок прозы начинается с «1. Reasonable syntax check The request
   MUST…»: подзаголовок пункта слипся с первым предложением абзаца. В книге
   заголовок выглядит как начало фразы.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

RE_ITEM = re.compile(r"^\s{0,8}\d{1,2}\.\s+[A-ZА-Я][^.;:{}<>=]{2,48}$")
RE_CODE_CHARS = re.compile(r"[{}<>=;]|::|\bint\b|\bchar\b|\bdef\b|--|/\*")
RE_GLUE = re.compile(
    r"^\s*(\d{1,2}\.\s+[A-ZА-Я][^.:]{3,60}[a-zа-я])\s+"
    r"(The|This|A|An|If|When|Each|Every|Any|Для|При|Если|Это|Все|Каждый)\s")
KINDS_CODE = ("code", "table", "diagram", "sip", "abnf", "sdp")


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        en = b.get("en") or ""
        if not en:
            continue
        kind = b.get("kind")
        lines = [l for l in en.split("\n") if l.strip()]
        if kind in KINDS_CODE and len(lines) >= 2:
            items = [l for l in lines
                     if re.match(r"^\s*\d{1,2}\.\s+[A-ZА-Я]", l)
                     and len(l.split()) >= 3]
            if len(items) >= 2:
                out.append((i, "список в коде", items[0].strip()[:40]))
            continue
        # проза внутри непереводимого блока: две и более длинных строк,
        # оканчивающихся точкой, и нет признаков протокола/грамматики
        if kind in ("sip", "sdp", "abnf", "code", "table", "diagram"):
            prose_lines = [l.strip() for l in lines
                           if l.strip().endswith((".", ":")) and len(l.split()) >= 6]
            looks_proto = re.search(r"SIP/2\.0|^\s*[a-z-]+\s*=|[<>]{2}|\bRFC \d{3,4}\b.*\[", en)
            if len(prose_lines) >= 2 and not looks_proto:
                out.append((i, "проза в непереводимом блоке", prose_lines[0][:40]))
            continue
        if kind in ("prose", "prose_cont"):
            m = RE_GLUE.match(en)
            if m:
                out.append((i, "заголовок слипся с абзацем", m.group(1)[:40]))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        hits = scan(n)
        if hits:
            print("RFC %-5d %s" % (n, hits[:4]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
