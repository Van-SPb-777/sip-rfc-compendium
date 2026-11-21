# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: пример SIP-сообщения слипся в абзац.

Примеры протокола в RFC набраны построчно:

    History-Info:<sip:UserA@ims.example.com?Reason=SIP%3B\\
       cause%3D302>;index=1;foo=bar

Если разборщик относит такой пример к прозе, строки склеиваются и в книге
получается сплошной текст с потерянными переносами.

Признаки настоящего примера (любой из двух):
  • строка начала сообщения: метод + URI + «SIP/2.0» (возможны префиксы
    «(1) », «F2 », «UAC->UAS: ») или строка состояния «SIP/2.0 200 OK»
    в начале блока;
  • не меньше трёх разных полей заголовка SIP («Via:», «From:», «To:»,
    «Call-ID:», «CSeq:», «Content-Length:» и т. п.) в одном абзаце.

Раньше достаточно было упоминания «SIP/2.0», из-за чего в находки попадала
обычная проза: «…заменой "HTTP/1.1" на "SIP/2.0"…» (RFC 3261, 22.4) или
«…тело message/sipfrag "SIP/2.0 200 OK"…» (RFC 3515, 2.4.5). Такие абзацы
примером не являются и теперь не трогаются.

Лечится так: вступление остаётся прозой, сами строки берутся из исходного
.txt и ставятся блоком `sip`.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

METHODS = (r"INVITE|ACK|BYE|CANCEL|REGISTER|OPTIONS|SUBSCRIBE|NOTIFY|"
           r"REFER|MESSAGE|PUBLISH|INFO|UPDATE|PRACK")
RE_MSG_START = re.compile(
    r"(?:^|[\s:>])(?:\(\s*\d+\s*\)\s*)?(?:F\d+\s+)?"
    r"(?:" + METHODS + r")\s+\S+\s+SIP/2\.0\b")
RE_STATUS_START = re.compile(r"^\s*(?:F\d+\s+)?SIP/2\.0\s+\d{3}\b")
RE_HEADER = re.compile(
    r"\b(?:Via|From|To|Call-ID|CSeq|Content-Length|Contact|Record-Route|"
    r"History-Info|Max-Forwards|Min-SE|Security-Server|Security-Verify|"
    r"Referred-By|Refer-To|Event|Subscription-State|Unsupported|Require):\s")
KINDS = ("prose", "prose_cont")


def scan_obj(obj):
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    for i, b in enumerate(obj["blocks"]):
        if b.get("kind") not in KINDS:
            continue
        en = b.get("en") or ""
        if "\n" in en:
            continue
        headers = set(m.group(0).lower() for m in RE_HEADER.finditer(en))
        if (RE_MSG_START.search(en) or RE_STATUS_START.search(en)
                or len(headers) >= 3):
            out.append(i)
    return out


def scan(num):
    return scan_obj(store.load(num))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        hits = scan(n)
        if hits:
            print("RFC %-5d слипшийся пример: %s" % (n, hits[:8]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
