# -*- coding: utf-8 -*-
"""Доступ к хранилищу переводов: <каталог>/rfc<NNNN>.json.

Формат файла (исторический, сохранён как есть):
{
  "num": 3261,
  "title_en": "...", "title_ru": "...",
  "status": "PROPOSED STANDARD", "date": "July 2002",
  "blocks": [
     {"kind": "heading", "en": "1. Introduction", "ru": "1. Введение"},
     {"kind": "prose",   "en": "...", "ru": "..."},
     {"kind": "abnf",    "en": "From = ...", "ru": null},
     ...
  ]
}

Каталог переводов задаётся переменной окружения RFC_TRANS; по умолчанию
берётся ..\translations (соседний с toolkit), затем .\translations.

Этот модуль — часть переносимого пакета toolkit; отличается от проектного
store.py только вычислением путей (без абсолютных путей к машине автора).
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
_CANDS = (os.path.join(BASE, os.pardir, "translations"),
          os.path.join(BASE, "translations"))
TRANS = os.path.abspath(
    os.environ.get("RFC_TRANS")
    or next((p for p in _CANDS if os.path.isdir(p)), _CANDS[0]))


def path_for(num):
    return os.path.join(TRANS, "rfc%d.json" % num)


def load(num):
    p = path_for(num)
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def save(num, obj):
    """Записать файл перевода. Внимание: изменяет данные на диске."""
    os.makedirs(TRANS, exist_ok=True)
    obj.setdefault("num", num)
    with open(path_for(num), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    return path_for(num)


def is_done(num):
    """Перевод готов, если файл есть и все heading/prose имеют ru."""
    obj = load(num)
    if not obj:
        return False
    blocks = obj.get("blocks") or []
    if not blocks:
        return False
    for b in blocks:
        if b.get("kind") in ("heading", "prose", "prose_cont"):
            if not (b.get("ru") or "").strip():
                return False
    return True


def status_report():
    nums = []
    if os.path.isdir(TRANS):
        for f in os.listdir(TRANS):
            if f.startswith("rfc") and f.endswith(".json"):
                try:
                    nums.append(int(f[3:-5]))
                except ValueError:
                    pass
    return sorted(nums)


if __name__ == "__main__":
    nums = status_report()
    print("переведено RFC:", len(nums))
    print("  ", nums)
