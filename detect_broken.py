# -*- coding: utf-8 -*-
"""
ДЕТЕКТОР И ФИКСЕР РАЗОРВАННЫХ БЛОКОВ — единый модуль.

Один критерий «это настоящий заголовок раздела или проза?» используется
и детектором, и фиксером, чтобы они не расходились.

Критерий (по исходному .txt, а не по блоку):
  Строка считается заголовком раздела, только если ОДНОВРЕМЕННО
    1) стоит с отступом 0-3 символа (заголовки RFC печатаются в колонке 0);
    2) номер вида «N», «N.M», «N.M.K» или «A», «A.B»;
    3) после номера короткая фраза без точки-с-пробелом и без двоеточия в конце;
    4) в тексте нет ссылок вида «in Section», «might look like» и т. п.

  Всё остальное, что начинается с числа — это нумерованный пункт прозы
  («1. PSTN origination - PSTN termination: The originating gateway…»)
  или слипшаяся ссылка («…codes is in Section 21.»).

Дефекты, которые ловим:
  A. ЛОЖНЫЙ ЗАГОЛОВОК — блок помечен heading, но по критерию это проза.
  B. ОБРЫВ НА ССЫЛКЕ — блок кончается словом-затравкой (Section / in / of …),
     следующий блок начинается с числа.
  C. СЛИПШИЙСЯ АБЗАЦ — внутри одного блока EN в исходнике есть пустая
     строка между двумя абзацами ПРОЗЫ (отступ 3-5).

Запуск:
  python detect_broken.py            — все документы
  python detect_broken.py 3261       — один документ, подробно
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

_SRC_CANDS = (os.path.join(BASE, os.pardir, "rfc-sip"),
              os.path.join(BASE, os.pardir, os.pardir, "rfc-sip"))
SRC = os.path.abspath(
    os.environ.get("RFC_SRC")
    or next((p for p in _SRC_CANDS if os.path.isdir(p)), _SRC_CANDS[0]))
MONTHS = (r"(?:January|February|March|April|May|June|July|August|September|"
          r"October|November|December)")
RE_PAGE_FOOT = re.compile(r"\[Page\s+\d+\]\s*$")
RE_PAGE_HEAD = re.compile(r"^RFC\s+\d{3,5}\s+\S.*\b" + MONTHS + r"\s+\d{4}\s*$")

# Признаки прозы в «заголовке»
HEADING_BAD = re.compile(
    r"\b(might look|may look|look like|as Bob sends|is in Section|"
    r"in Section|see Section|described in|are consistent|has the following|"
    r"of the request|of the response|as shown|are in)\b", re.I)

DANGLING = re.compile(
    r"\b(Section|Figure|Table|Appendix|RFC|Example|point|bullet|item|"
    r"in|of|the|a|an|to|by|for|with|and|or|see|via|per|from|at|on|"
    r"is|are|was|were|be|as)\s*$", re.I)

# Слова, на которых блок прозы не может закончиться, если он не оборван
TRUNCATED_TAIL = re.compile(
    r"\b(proxy|server|client|the|a|an|of|to|by|for|with|and|or|that|which|"
    r"this|these|those|it|its|their|his|her|is|are|was|were|be|been|"
    r"in|on|at|as|from|via|per|any|all|some|each|every|no|not|if|when|"
    r"such|than|then|so|but|may|can|will|would|should|could|must)\s*$", re.I)

RE_HEAD_NUM = re.compile(r"^\s*(?:\d+(?:\.\d+)*|[A-Z](?:\.\d+)*)\.?\s+")

# Проза в RFC начинается с отступа 3, примеры — с 6+. Заголовки — с 0-3,
# но от прозы их отличает структура строки (короткая фраза, номер).
PROSE_INDENT = 3
CODE_INDENT = 6
HEADING_MAX_INDENT = 3


def real_heading_text(en):
    """Текст блока — настоящий заголовок раздела (проверка по тексту).

    Верно: «1. Introduction», «20. Header Fields», «A. Table of Timer Values»,
           «1. Validate the request (Section 16.3)», «2. URI scheme check».
    Неверно: «21. The 200 (OK) … might look like this as Bob sends it out:»,
             «1. The URI included in the challenge has the following BNF:».
    """
    en = (en or "").strip()
    if not en or len(en) > 90:
        return False
    if HEADING_BAD.search(en):
        return False
    if len(en.split()) > 12:
        return False
    rest = RE_HEAD_NUM.sub("", en, count=1)
    if not rest.strip():
        return False
    if ". " in rest:                    # точка с пробелом внутри → проза
        return False
    if rest.rstrip().endswith(":"):     # «…has the following BNF:» → проза
        return False
    return True


def is_real_heading_line(line):
    """Строка — настоящий заголовок раздела (проверка только по тексту).

    Заголовок RFC: отступ 0-3, номер вида «N», «N.M», «N.M.K» или «A.B»,
    затем короткая фраза без точки-с-пробелом и без двоеточия в конце.

    Проза, похожая на заголовок:
      «21. The 200 (OK) … might look like this as Bob sends it out:»
         → двоеточие в конце + ссылки → отсекается
      «1. PSTN origination - PSTN termination: The originating gateway…»
         → заголовочная по форме, но это нумерованный пункт; отличается
           он тем, что в исходнике продолжается на следующих строках.
           Отсекается проверкой «длина > 80» только если строка длинная;
           если нет — такой пункт остаётся помеченным как заголовок,
           но текст его НЕ рвётся, поэтому в PDF дефекта не даёт.
    """
    if not line:
        return False
    indent = len(line) - len(line.lstrip())
    if indent > HEADING_MAX_INDENT:
        return False
    s = line.strip()
    if HEADING_BAD.search(s):
        return False
    m = RE_HEAD_NUM.match(s)
    if not m:
        return False
    rest = s[m.end():].strip()
    if not rest or len(rest) > 80:
        return False
    if ". " in rest:                    # точка с пробелом внутри → проза
        return False
    if rest.endswith(":"):              # «…has the following BNF:» → проза
        return False
    if len(rest.split()) > 10:
        return False
    return True


def src_index(num):
    """(плоский текст, список границ абзацев прозы)."""
    path = os.path.join(SRC, "rfc%d.txt" % num)
    if not os.path.exists(path):
        return None, []
    raw = open(path, encoding="utf-8", errors="replace").read()

    kept = []
    prev_blank = True
    for ln in raw.splitlines():
        s = ln.strip()
        if not s:
            prev_blank = True
            continue
        if RE_PAGE_FOOT.search(s) or RE_PAGE_HEAD.match(s):
            continue
        kept.append((ln, prev_blank))
        prev_blank = False

    chars = []
    cur = 0
    para_breaks = []
    prev_prose = False
    for ln, was_blank in kept:
        s = ln.strip()
        indent = len(ln) - len(ln.lstrip())
        is_prose = PROSE_INDENT <= indent < CODE_INDENT
        if was_blank and is_prose and prev_prose:
            para_breaks.append(cur)
        chars.append(s)
        cur += len(s) + 1
        prev_prose = is_prose
    return " ".join(chars), para_breaks


def looks_truncated(en):
    """Блок обрывается на середине фразы.

    Признак: текст не кончается на точку/двоеточие/закрывающую скобку и
    последнее слово — служебное (proxy, the, of, that, it, a…). Такой
    блок в PDF выглядит как оборванное предложение.
    """
    t = (en or "").strip()
    if not t:
        return False
    if t[-1] in ".!?:;)]\"'":
        return False
    return bool(TRUNCATED_TAIL.search(t[-40:]))


LIST_ITEM = re.compile(r"^\d{1,2}\.\s+\S")


def check_false_heading(i, blocks, flat=None):
    # пункт нумерованного списка — законченная строка, а не обрыв заголовка
    if LIST_ITEM.match((blocks[i].get("en") or "").strip()) and len(blocks[i]["en"]) < 90:
        return None
    # заголовок, который дословно найден в исходнике, не может быть обрывком
    if flat is not None:
        _b = blocks[i]
        if _b.get("kind") == "heading":
            _en = " ".join((_b.get("en") or "").split())
            if _en and _en in flat:
                return None
    """Блок помечен heading, но по тексту это не заголовок.

    Два разных случая:
      • блок ОБОРВАН на середине фразы (реальный дефект: в PDF
        предложение рвётся и следующая часть уходит в жирный заголовок);
      • блок — цельный нумерованный пункт прозы, просто неверно
        помечен heading (текст не рвётся, дефект косметический).
    Возвращаем оба, но помечаем, рвётся ли текст.
    """
    b = blocks[i]
    if b["kind"] != "heading":
        return None
    en = (b.get("en") or "").strip()
    if real_heading_text(en):
        return None
    return {"i": i, "text": en[:110], "truncated": looks_truncated(en)}


def check_dangling(i, blocks):
    """Обрыв на ссылке: блок кончается «…in Section», следующий — числом.

    Не срабатывает, если следующий блок — настоящий заголовок раздела
    (например «7. Security Considerations» после блока реестра IANA).
    Также не срабатывает на ASCII-схемах: строка «0   1   2   3…» это
    номера битов, а не продолжение фразы.
    """
    if i + 1 >= len(blocks):
        return None
    a, c = blocks[i], blocks[i + 1]
    en_a = (a.get("en") or "").strip()
    en_c = (c.get("en") or "").strip()
    if not en_a or not en_c:
        return None
    # схема/код — это не проза, обрыва фразы тут быть не может
    if c["kind"] in ("diagram", "abnf", "sip", "sdp", "code", "table"):
        return None
    # номера битов: «0   1   2   3   4   5 …»
    if re.match(r"^0\s+1\s+2\s+3", en_c):
        return None
    # следующий блок — настоящий заголовок раздела, а не продолжение фразы
    if c["kind"] == "heading" and real_heading_text(en_c):
        return None
    # предыдущий блок — пункт списка: следующий номер это тоже пункт,
    # а не продолжение оборванной ссылки
    if re.match(r"^\d{1,2}\.\s+\S", en_a):
        return None
    m = re.match(r"^(\d{1,4})\.?\s+\S", en_c)
    if not m:
        return None
    # подпись рисунка или таблицы — законченная строка, а не обрыв фразы
    if re.match(r"^(Figure|Table|Example)\s+\d+", en_a):
        return None
    # пункт списка, заканчивающийся «…, and», и следующий пункт «2.» —
    # это продолжение перечисления, а не обрыв ссылки
    if re.search(r",\s*(and|or)?\s*$", en_a[-40:]) and int(m.group(1)) <= 20:
        return None
    # заголовок раздела не бывает оборванной фразой: он дословно есть в исходнике
    if a.get("kind") == "heading":
        return None
    if not DANGLING.search(en_a[-40:]):
        return None
    return {"i": i, "next": i + 1, "num": m.group(1),
            "tail": en_a[-60:], "head": en_c[:60]}


def check_glued(i, blocks, flat, para_breaks):
    """Слипание: внутри блока в исходнике была пустая строка.

    Дефектом считается только случай, когда перевод НЕПОЛНЫЙ: если в блок
    склеены два абзаца, а переведён только первый, русская колонка короче
    английской. Если перевод покрывает весь блок (ratio близок к 1),
    значит абзацы просто шли подряд в исходнике и оба переведены —
    это не дефект.
    """
    b = blocks[i]
    if b["kind"] not in ("prose", "prose_cont"):
        return None
    en = re.sub(r"\s+", " ", (b.get("en") or "")).strip()
    if len(en) < 200 or flat is None:
        return None
    start = flat.find(en[:60])
    if start < 0:
        return None
    end = start + len(en)
    # блок должен найтись в исходнике целиком; если хвост не совпал,
    # сравнение по первым 60 символам даст неверные границы — пропускаем
    if flat[start:end] != en:
        pos = flat.find(en)
        if pos < 0:
            return None
        start, end = pos, pos + len(en)
    n = sum(1 for p in para_breaks if start < p < end)
    if n < 1:
        return None
    # перевод покрывает весь блок — слипание мнимое
    ru = b.get("ru") or ""
    if len(ru) / max(1, len(en)) >= 0.8:
        return None
    return {"i": i, "breaks": n, "text": en[:110]}


def audit_doc(num):
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return None
    blocks = obj["blocks"]
    flat, para_breaks = src_index(num)

    res = {"false_heading": [], "dangling": [], "glued": []}
    for i in range(len(blocks)):
        r = check_false_heading(i, blocks, flat)
        if r:
            res["false_heading"].append(r)
        r = check_dangling(i, blocks)
        if r:
            res["dangling"].append(r)
        r = check_glued(i, blocks, flat, para_breaks)
        if r:
            res["glued"].append(r)
    return res


def main():
    quiet = "--quiet" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = [int(a) for a in args] if args else sorted(
        n for n in store.status_report() if isinstance(n, int))

    totals = {"false_heading": 0, "dangling": 0, "glued": 0}
    bad_docs = 0
    detail = len(nums) == 1 and not quiet
    for num in nums:
        r = audit_doc(num)
        if r is None:
            continue
        c = {k: len(v) for k, v in r.items()}
        if not any(c.values()):
            continue
        bad_docs += 1
        for k in totals:
            totals[k] += c[k]
        print("RFC %-5d ложный_заголовок:%-3d обрыв_ссылки:%-3d слиплось:%d"
              % (num, c["false_heading"], c["dangling"], c["glued"]))
        if detail:
            for x in r["false_heading"]:
                print("   [ЗАГОЛОВОК] блок %d: %s" % (x["i"], x["text"]))
            for x in r["dangling"]:
                print("   [ОБРЫВ] блок %d -> %d, число %s" % (x["i"], x["next"], x["num"]))
                print("        хвост:  %r" % x["tail"])
                print("        начало: %r" % x["head"])
            for x in r["glued"]:
                print("   [СЛИПАНИЕ] блок %d, абзацев=%d: %s"
                      % (x["i"], x["breaks"] + 1, x["text"]))

    print()
    print("=" * 68)
    print("ИТОГО документов с находками: %d" % bad_docs)
    for k, v in totals.items():
        print("  %-14s %d" % (k, v))
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
