# -*- coding: utf-8 -*-
"""ПРОВЕРКА paren: у перевода разошлись скобки при сбалансированном EN.

Если английский блок сбалансирован по круглым (или квадратным) скобкам, а
русский — нет, значит в переводе потеряна скобка: либо обрыв внутри
вставной конструкции («…сообщений (та шифровать целые запросы…»), либо
закрывающая скобка уехала в следующий блок, либо добавлена лишняя.

Класс ошибки — punctuation mismatch между исходным и целевым сегментом:
  * MQM, категория Fluency / Linguistic conventions (пунктуация) —
    https://www.themqm.org/mqm-pillars/typology/
  * Verifika, проверки пунктуации и «Ignore punctuation» (пунктуация
    сегментов сравнивается отдельным правилом) —
    https://e-verifika.com/checks_in_detail
  * transread D3.1: «ratio of brackets and punctuation symbols in source
    and target segments» — https://transread.limsi.fr/Deliverables/Deliverable_3.1.pdf
  * CheckMate: «Warn if target does not match source punctuation» —
    https://okapiframework.org/wiki/index.php?title=CheckMate

Смысл: сравниваем НЕ количество скобок (в русском текст законно
переставлен), а дисбаланс: d = открывающих − закрывающих. У нормального
блока d(EN) = d(RU) = 0. Ловим случай d(EN) = 0, d(RU) ≠ 0 — это
однозначный дефект перевода, а не стилистическая перестановка.

Запуск: python detect_paren.py [N[,N]]
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

CYR = re.compile(r"[А-Яа-яЁё]")


def scan(num):
    """Вернуть список (i, скобка, дисбаланс, фрагмент перевода)."""
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return []
    out = []
    for i, b in enumerate(obj.get("blocks") or []):
        if b.get("kind") not in ("prose", "prose_cont"):
            continue
        en, ru = b.get("en") or "", b.get("ru") or ""
        if len(en) < 80 or not ru or not CYR.search(ru):
            continue
        for op, cl in (("(", ")"), ("[", "]")):
            if en.count(op) - en.count(cl) != 0:
                continue          # EN сам разорван — сравнивать нечего
            d = ru.count(op) - ru.count(cl)
            if d:
                out.append((i, op + cl, d, ru[:90].replace("\n", "|")))
                break
    return out


def doc_numbers(argv):
    args = [a for a in argv if not a.startswith("--")]
    if args:
        nums = []
        for a in args:
            nums.extend(int(x) for x in a.split(",") if x.strip())
        return nums
    return sorted(x for x in store.status_report() if isinstance(x, int))


def main():
    total = docs = 0
    for n in doc_numbers(sys.argv[1:]):
        hits = scan(n)
        if not hits:
            continue
        docs += 1
        total += len(hits)
        print("RFC %d: %d" % (n, len(hits)))
        for i, pair, d, frag in hits:
            print("   блок %-5d %s дисбаланс %+d | %s" % (i, pair, d, frag))
    print()
    print("ИТОГО: %d блоков с разошедшимися скобками в %d документах"
          % (total, docs))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
