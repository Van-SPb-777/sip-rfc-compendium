# -*- coding: utf-8 -*-
"""
ПРОВЕРКА: в переводе потерян хвост-анонс.

Английский блок часто заканчивается двоеточием, за которым в следующем
блоке идёт пример или таблица:

    ... see Section 3. Example:
    ... Table 3 extends ... :
    ... as follows:

Если русский текст кончается точкой, а английский — двоеточием, значит
анонс («Пример:», «Следующим образом:») при переводе потерян. В книге
получается текст, обещающий пример, за которым сразу идёт таблица без
подписи.

Проверяем только блоки прозы и заголовки; сравниваем последний значимый
символ. Случаи, где двоеточие в переводе заменено точкой осознанно
(например, длинная цитата), редки и видны глазами.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

KINDS = ("prose", "prose_cont")


def scan(num):
    obj = store.load(num)
    if not obj or obj.get("excluded") or obj.get("skip_translation"):
        return []
    out = []
    bl = obj["blocks"]
    for i, b in enumerate(bl):
        if b.get("kind") not in KINDS:
            continue
        en = (b.get("en") or "").rstrip()
        ru = (b.get("ru") or "").rstrip()
        if not en or not ru:
            continue
        if not en.endswith(":"):
            continue
        if ru.endswith(":"):
            continue
        # шум отсекаем: если в конце русского текста всё же стоит слово-анонс
        # («пример», «следующим образом», «таблица»), это не потеря
        tail = ru[-60:].lower()
        if any(w in tail for w in ("пример", "следующ", "таблиц", "рисун",
                                   "ниже", "как показано", "образом")):
            continue
        nxt = bl[i + 1]["kind"] if i + 1 < len(bl) else ""
        out.append((i, nxt))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot = 0
    for n in nums:
        hits = scan(n)
        if hits:
            print("RFC %-5d потерян анонс: %s" % (n, hits[:6]))
            tot += len(hits)
    print()
    print("ИТОГО:", tot)
