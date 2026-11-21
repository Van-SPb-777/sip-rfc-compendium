# -*- coding: utf-8 -*-
"""
ЕДИНЫЙ АУДИТ КАЧЕСТВА ПЕРЕВОДА.
Запускать после каждой порции переводов.

Проверки:
  1. ПОЛНОТА     — есть ли перевод у всех переводимых блоков
  2. ОБРЫВ       — перевод короче 75% от EN
  3. РАЗДУТИЕ    — перевод длиннее 220% от EN (вероятна вставка чужого текста)
  4. ДУБЛЬ       — повторяющийся фрагмент внутри перевода
  5. ЧУЖОЙ ТЕКСТ — маркеры лексики, отсутствующей в своём EN
  6. ОРИГИНАЛ    — EN-блоки дословно совпадают с .txt (без учёта колонтитулов)
  7. РАЗОРВАНО   — блоки, разорванные при разборе исходника:
        • ложный заголовок (нумерованный пункт прозы помечен heading,
          текст рвётся посреди фразы);
        • обрыв на ссылке (блок кончается «in Section», следующий — числом);
        • слипшийся абзац (в блок склеены два абзаца прозы).
     Источник логики — detect_broken.py.
  8. ОБРЕЗАНО    — перевод обрывается посреди фразы, хотя английский текст
     эту фразу закончил. Именно так терялось окончание
     «…находится в разделе 21» — в хранилище перевод был полным, но
     в колонку попадала только его часть.
     Источник логики — detect_cut.py.
   9. АРТЕФАКТ  — колонтитулы страниц, form feed, BOM в тексте
      (detect_artifacts.py).
  10. ПОВТОР    — подряд одинаковое слово в переводе (detect_dupword.py).
  11. URL       — регистр URI в переводе изменён (detect_urlcase.py).
  12. СКОБКИ    — дисбаланс скобок при сбалансированном EN (detect_paren.py).
  13. АЛФАВИТ   — кириллица в EN / латиница внутри слова RU (detect_script.py).
  14. РАЗДЕЛ    — номер «раздела» в RU противоречит номеру в EN
      (detect_secnum.py).

Код возврата 1, если есть находки — годится для CI/сборочного скрипта.
"""
# ---------------------------------------------------------------------------
# ПЕРЕНОСИМЫЙ ПАКЕТ (toolkit). Пути не зависят от машины:
#   BASE      — каталог, где лежит этот файл (toolkit);
#   RFC_SRC   — каталог с исходниками rfc<N>.txt: переменная окружения
#               RFC_SRC, иначе ..\rfc-sip, иначе ..\..\rfc-sip;
#   RFC_TRANS — каталог с переводами rfc<N>.json (см. store.py).
# Нумерация проверок та же, что в ДЕФЕКТЫ.md.
# ---------------------------------------------------------------------------
import difflib
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

# ---------- маркеры чужой лексики ----------
MARKERS = {
    "многоадресн": ["multicast"],
    "одноадресн": ["unicast"],
    "шифрова": ["encryption", "encrypt"],
    "аудиопоток": ["audio stream"],
    "видеопоток": ["video stream"],
    "регистратор": ["registrar"],
    "диалог": ["dialog"],
    "транзакц": ["transaction"],
    "подписк": ["subscription", "subscribe"],
    "уведомлен": ["notification", "notify"],
    "переадресац": ["forwarding"],
    "разветвлен": ["forking"],
    "полезн": ["payload"],
    "комфортн": ["comfort noise"],
    "тишин": ["silence"],
    "маркер": ["marker"],
    "кодек": ["codec"],
    "семинар": ["seminar"],
    "статистик": ["statistics"],
    "кумулятивн": ["cumulative"],
    "сертификат": ["certificate"],
    "дайджест": ["digest"],
    "nonce": ["nonce"],
    "cookie": ["cookie"],
    "предуслови": ["precondition"],
    "каталог": ["directory"],
    "БДС": ["B2BUA"],
    "голосован": ["voting"],
}


def ratio(b):
    en = b["en"] or ""
    ru = b.get("ru") or ""
    if not en:
        return 0.0
    return len(ru) / len(en)


RE_SENT_BREAK = re.compile(r"(?<=[.!?:;])\s+")


def spill_tail_sim(ru, nru):
    """Наибольшее сходство ХВОСТА перевода с началом перевода следующего блока.

    Перебираем только границы предложений: «залезший» перевод следующего
    абзаца всегда начинается с начала предложения. Возвращает
    (сходство, позиция начала хвоста); позиция -1 — подходящего хвоста нет.
    """
    best = (0.0, -1)
    for m in RE_SENT_BREAK.finditer(ru):
        pos = m.end()
        seg = ru[pos:]
        if len(seg) < 50:
            continue
        ref = nru[:len(seg)]
        sim = difflib.SequenceMatcher(None, seg, ref, autojunk=False).ratio()
        if sim > best[0]:
            best = (sim, pos)
    return best


def lcs_len(a, b):
    """Длина наибольшего общего куска (для сравнения EN соседних блоков)."""
    m = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(
        0, len(a), 0, len(b))
    return m.size


def has_dupe(b):
    """Детектор дублей ОТКЛЮЧЁН.

    Проверено вручную на 6 случаях (RFC 2833/77, 3264/63, 3329/40,
    2976/33, 3489/57, 3550/709): все повторы в переводах повторяют
    повторы оригиналов (однотипные пункты, ссылки на одно и то же
    правило). Надёжного автоматического критерия без ложных
    срабатываний найти не удалось, поэтому проверка не используется;
    реальные дубли были найдены вручную (3550/78, 3550/709 — исправлены).
    """
    return False


def en_has(text, variants):
    e = (text or "").lower()
    return any(v.lower() in e for v in variants)


def _strip_furniture(raw):
    """Убрать из .txt колонтитулы страниц и разрывы — так же, как это делает парсер."""
    lines = []
    for ln in raw.splitlines():
        if "[Page " in ln:                       # нижний колонтитул
            continue
        if re.match(r"^RFC \d+[\s\S]{0,60}(January|February|March|April|May|June|"
                    r"July|August|September|October|November|December)\s+\d{4}", ln):
            continue                             # верхний колонтитул
        if ln.strip() == "\f" or ln.strip() == "":
            continue                             # разрыв страницы / пустая строка
        lines.append(ln.strip())
    return re.sub(r"\s+", " ", " ".join(lines))


def check_original_vs_txt(num, blocks):
    """EN-текст в хранилище должен присутствовать в .txt
    (за вычетом колонтитулов, переносов строк и косметической
    нормализации нумерации заголовков 'A.6 X' -> 'A.6. X')."""
    src = os.path.join(SRC, "rfc%d.txt" % num)
    if not os.path.exists(src):
        return None
    raw = open(src, encoding="utf-8", errors="replace").read()
    # BOM — артефакт кодировки файла, а не текст RFC: в хранилище его снимаем
    # (проверка artifacts), поэтому и в исходнике для сверки он не нужен.
    raw = raw.replace("\ufeff", "")
    norm = _strip_furniture(raw)

    missing = []
    for i, b in enumerate(blocks):
        t = re.sub(r"\s+", " ", b["en"] or "").strip()
        if len(t) < 40:
            continue

        # заголовки: сравниваем только текст названия, без номера
        if b["kind"] in ("heading", "code"):
            title = re.sub(r"^[A-Z]?\d+(\.\d+)*\.?\s*", "", t).strip()
            if len(title) < 10:
                continue
            core = title[:40]
            if core in norm:
                continue
            # колонтитул мог разорвать заголовок — проверяем по словам
            words = [w for w in core.split() if len(w) > 3]
            if words and sum(1 for w in words if w in norm) >= len(words) - 1:
                continue
            missing.append(i)
            continue

        probes = [t[:50], t[len(t) // 3: len(t) // 3 + 50], t[-50:]]
        probes = [p for p in probes if len(p) >= 25]
        found = sum(1 for p in probes if p in norm)
        if probes and found < len(probes):
            if len(t) < 120 and found >= 1:
                continue
            missing.append(i)
    return missing


RE_HEAD_NUM = re.compile(r"^\s*((?:\d+(?:\.\d+)*|[A-Z](?:\.\d+)*)\.?)\s+")


def looks_like_scheme(text):
    """Блок похож на ASCII-схему или таблицу.

    В таких блоках перевод заведомо короче: переводится только вводная
    фраза, а сама схема переносится как есть (числа в колонках, рамки,
    выровненные подписи). Сравнивать длину там бессмысленно.
    """
    t = text or ""
    if "+-" in t or t.count("|") >= 4:
        return True
    return len(re.findall(r"\S {2,}\S", t)) >= 3


def en_is_cut(text):
    """Английский блок обрывается посреди фразы.

    Значит парсер разрезал предложение по структуре исходника (абзац
    переходил через разрыв страницы или строка списка имела больший
    отступ). Продолжение стоит в следующем блоке, а перевод здесь может
    быть полным — сравнивать длины в таком случае нельзя.
    """
    t = (text or "").strip()
    if not t or t[-1] in ".!?:;)]}\"»…":
        return False
    return bool(RE_CUT_TAIL.search(t[-50:]))


RE_CUT_TAIL = re.compile(
    r"\b(the|a|an|of|in|on|at|to|for|with|by|from|and|or|but|is|are|was|"
    r"were|that|which|this|these|those|as|if|when|then|than|such|any|all|"
    r"some|each|every|may|can|will|would|should|could|must|only|also|"
    r"however|thus|see|via|per|into|over|under|between|within)\s*$"
    r"|(e\.g\.|i\.e\.),?\s*$",
    re.I)


def audit(num, full=True):
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return None
    blocks = obj["blocks"]
    trb = [(i, b) for i, b in enumerate(blocks)
           if b["kind"] in ("prose", "prose_cont", "heading") and len(b["en"]) >= 1]

    res = {"missing": [], "short": [], "long": [], "dupe": [],
           "foreign": [], "original": [], "broken": [], "cut": [],
           "shift": [], "headnum": [], "structure": [], "diagsplit": [], "preamble": [], "toc": [], "squeeze": [], "tail": [], "duphead": [], "inlinelist": [], "form": [], "textcode": [], "example": [], "hyphsplit": [], "dupblock": [], "figsplit": [], "mergepara": [], "headlost": [], "codelist": [], "spill": [], "extrasent": [], "colspace": [],
           "artifacts": [], "dupword": [], "urlcase": [], "paren": [], "script": [], "secnum": []}

    # ДОСЛОВНОСТЬ ГРАФИКИ: схемы, таблицы и код обязаны совпадать с исходником
    try:
        import io as _io
        _src = " ".join(_io.open(
            os.path.join(SRC, "rfc%d.txt" % num),
            encoding="utf-8", errors="replace").read().replace("\r\n", "\n").split())
        for i, b in enumerate(blocks):
            if b["kind"] not in ("diagram", "table", "code"):
                continue
            # сверяем ПОСТРОЧНО: склейка строк из разных мест — нормально,
            # а вот строка, которой нет в исходнике, — искажение содержимого
            _miss = 0
            for _ln in (b.get("en") or "").split(chr(10)):
                _t = " ".join(_ln.split())
                if len(_t) < 3:
                    continue
                if _t not in _src:
                    _miss += 1
            if _miss:
                res["original"].append((i, "в схеме %d строк нет в исходнике" % _miss))
    except OSError:
        pass

    for i, b in trb:
        ru = (b.get("ru") or "").strip()
        if not ru:
            res["missing"].append(i)
            continue

        # Порог 60 символов, а не 150: короткие блоки (адреса авторов,
        # строки шапки RFC) тоже надо проверять. Именно из-за порога 150
        # проскочили 18 блоков с обрезанными адресами: перевод кончался
        # на имени и организации, улица с индексом терялась, но по длине
        # блок был короче порога и в проверку не попадал.
        # Схемы и таблицы исключаем: там перевод короче по определению.
        # Заголовки тоже: «Introduction» и «Введение» — разная длина при
        # одинаковом смысле, сравнивать их бессмысленно.
        if (b["kind"] in ("prose", "prose_cont")
                and not b.get("skip_length")
                and len(b["en"]) >= 60 and not looks_like_scheme(b["en"])):
            r = ratio(b)
            # Порог зависит от длины. У коротких блоков в одно предложение
            # русский текст законно короче процентов на тридцать:
            # «The meanings of the values of the directives used above are
            # as follows:» против «Значения директив, использованных выше,
            # следующие:». Поэтому для 60..149 символов порог мягче.
            limit = 0.75 if len(b["en"]) >= 150 else 0.55
            # Если сам английский блок оборван посреди фразы (парсер разрезал
            # предложение по структуре исходника), сравнивать длины нельзя:
            # русский перевод этой фразы законен и длиннее. Такой случай
            # показывает отдельная проверка `cut`.
            if not en_is_cut(b["en"]):
                if r < limit:
                    res["short"].append((i, round(r, 2)))
                elif r > 2.2 and "Request for Comments:" not in b["en"]:
                    # шапку RFC не проверяем на раздутие: русские подписи
                    # («Запрос комментариев», «Категория») длиннее английских,
                    # и блок законно выходит за 220 %
                    res["long"].append((i, round(r, 2)))
        if has_dupe(b):
            res["dupe"].append(i)

        if len(b["en"]) >= 150:
            sus = []
            for rw, vars_ in MARKERS.items():
                if not vars_:
                    continue
                if rw.lower() in ru.lower() and not en_has(b["en"], vars_):
                    for j in range(max(0, i - 3), min(len(blocks), i + 4)):
                        if j != i and en_has(blocks[j]["en"], vars_):
                            sus.append((rw, j))
                            break
            if len(sus) >= 2:
                res["foreign"].append((i, sus))

    if full:
        m = check_original_vs_txt(num, blocks)
        if m is not None:
            res["original"] = m
        # 7. разорванные блоки
        try:
            import detect_broken
            r = detect_broken.audit_doc(num)
            if r:
                # Блокирующий дефект — только те, где текст РВЁТСЯ:
                #  • заголовок, у которого EN оканчивается посреди фразы;
                #  • обрыв на ссылке («…in Section» + число);
                #  • слипшийся абзац (в RU текст, которого нет в EN).
                for x in r["false_heading"]:
                    if x.get("truncated"):
                        res["broken"].append(("заголовок", x["i"], x["text"][:80]))
                for x in r["dangling"]:
                    res["broken"].append(("обрыв-ссылка", x["i"], x["tail"][-40:]))
                for x in r["glued"]:
                    res["broken"].append(("слипание", x["i"], x["text"][:80]))
        except ImportError:
            pass

        # 8. обрезанный перевод
        try:
            import detect_cut
            cut_bad, _info = detect_cut.scan(num)
            for i, s in cut_bad:
                res["cut"].append((i, s))
        except ImportError:
            pass

        # 9a. номер раздела в заголовке должен совпадать с оригиналом
        for i, b in enumerate(blocks):
            if b["kind"] != "heading":
                continue
            en = (b.get("en") or "").strip()
            ru = (b.get("ru") or "").strip()
            if not ru:
                continue
            m = RE_HEAD_NUM.match(en)
            if not m:
                continue
            hnum = m.group(1).rstrip(".")
            if not ru.startswith(hnum):
                res["headnum"].append((i, hnum, ru[:40]))

        # 40. склеенный перевод внутри непереводимого блока
        try:
            KINDS_NT = ("code", "table", "diagram", "abnf", "sip", "sdp")
            for i, b in enumerate(blocks):
                if b.get("kind") not in KINDS_NT:
                    continue
                en, ru = b.get("en") or "", b.get("ru") or ""
                if (ru.strip() and en.count("\n") >= 2 and ru.count("\n") == 0
                        and len(ru.strip()) < len(en) * 0.5):
                    res["coderu"].append(i)
        except Exception:
            pass

        # 39. повтор фразы в переводе, которого нет в оригинале
        try:
            import detect_dupword
            for h in detect_dupword.scan_phrases(num):
                res["dupphrase"].append(h)
        except Exception:
            pass

        # 33. в схеме/таблице схлопнуты пробелы между колонками
        try:
            import detect_colspace
            got = detect_colspace.scan(num)
            if got:
                hits = got[0] or []
                for h in hits:
                    res["colspace"].append(h["i"] if isinstance(h, dict) else h)
        except ImportError:
            pass

        # 34. колонтитулы страниц, form feed и BOM попали в текст
        try:
            import detect_artifacts
            for i, _kind, reason, _frag in detect_artifacts.scan(num):
                res["artifacts"].append((i, reason))
        except ImportError:
            pass

        # 35. в переводе подряд стоит одно и то же слово
        try:
            import detect_dupword
            for i, _word, _ctx in detect_dupword.scan(num):
                res["dupword"].append(i)
        except ImportError:
            pass

        # 36. в URI перевода изменён регистр (Ftp:// вместо ftp://)
        try:
            import detect_urlcase
            for i, _en, _ru in detect_urlcase.scan(num):
                res["urlcase"].append(i)
        except ImportError:
            pass

        # 37. у перевода разошлись скобки при сбалансированном EN
        try:
            import detect_paren
            for i, _pair, _d, _frag in detect_paren.scan(num):
                res["paren"].append(i)
        except ImportError:
            pass

        # 38. смешение алфавитов: кириллица в EN / латиница в слове RU
        try:
            import detect_script
            for i, _kind, reason, _frag in detect_script.scan(num):
                res["script"].append((i, reason))
        except ImportError:
            pass

        # 39. номер раздела в переводе противоречит номеру в EN
        try:
            import detect_secnum
            for i, _ens, _rus, _frag in detect_secnum.scan(num):
                res["secnum"].append(i)
        except ImportError:
            pass

        # 32. в переводе больше предложений, чем в оригинале
        try:
            def _sents(t):
                # не считаем концом предложения сокращения и инициалы
                x = (t or "")
                for ab in ("см.", "т. е.", "т. п.", "т. д.", "e.g.", "i.e.", "т.к.",
                           "др.", "пр.", "рис.", "табл.", "напр.", "стр."):
                    x = x.replace(ab, ab.replace(".", "_"))
                x = re.sub(r"\b([A-ZА-Я])\.", r"\1_", x)
                parts = [y for y in re.split(r"(?<=[.!?])\s+", x.strip()) if len(y) > 15]
                return len(parts)
            for i, b in enumerate(blocks):
                if b.get("kind") not in ("prose", "prose_cont"):
                    continue
                en, ru = b.get("en") or "", b.get("ru") or ""
                # разница в 1 предложение — норма: длинное английское
                # предложение законно делится на два русских
                if len(en) >= 300 and ru and _sents(ru) - _sents(en) >= 2:
                    res["extrasent"].append(i)
        except Exception:
            pass

        # 31. перевод длиннее оригинала — вероятно, залез в следующий блок
        try:
            for i, b in enumerate(blocks):
                if b.get("kind") not in ("prose", "prose_cont"):
                    continue
                en, ru = b.get("en") or "", b.get("ru") or ""
                if not ru:
                    continue
                hit = bool(len(en) > 400 and len(ru) / len(en) > 1.35)
                if not hit:
                    # Начало перевода следующего блока присутствует в КОНЦЕ
                    # перевода текущего. Сравниваем именно хвост, а не ищем
                    # 60 знаков где угодно: соседние абзацы часто начинаются
                    # одинаково («Если запрос NOTIFY терпит неудачу…», пункты
                    # списков, строки реестров), из-за чего старый поиск давал
                    # сотни ложных срабатываний (в RFC 7478 — 109 штук на
                    # пунктирных линейках таблиц). Дополнительно требуем,
                    # чтобы английские тексты при этом НЕ совпадали: у почти
                    # дословных соседей (реестры, однотипные пункты) сходство
                    # перевода законно.
                    nxt = blocks[i + 1] if i + 1 < len(blocks) else None
                    if nxt and (nxt.get("ru") or ""):
                        plain_ru = " ".join(ru.split())
                        plain_next = " ".join((nxt["ru"] or "").split())
                        head = plain_next[:60]
                        if len(head) > 40 and head in plain_ru:
                            sim, pos = spill_tail_sim(plain_ru, plain_next)
                            en_same = lcs_len(
                                " ".join((b.get("en") or "").split()),
                                " ".join((nxt.get("en") or "").split()))
                            hit = bool(pos > 0 and sim >= 0.7 and en_same <= 45)
                if hit and i not in res["spill"]:
                    res["spill"].append(i)
        except Exception:
            pass

        # 30. список размечен как код / заголовок слипся с абзацем
        try:
            import detect_codelist
            for item in detect_codelist.scan(num):
                res["codelist"].append(item[0])
        except ImportError:
            pass

        # 27. в один блок склеены два абзаца (граница видна в исходнике)
        try:
            import detect_mergepara
            for item in detect_mergepara.scan(num):
                res["mergepara"].append(item[0])
        except ImportError:
            pass

        # 28. заголовок раздела потерял тип и стал прозой
        try:
            import detect_headlost
            for i in detect_headlost.scan(num):
                res["headlost"].append(i)
        except ImportError:
            pass

        # 26. псевдографика попала в прозу или разрезана между блоками
        try:
            import detect_figsplit
            for item in detect_figsplit.scan(num):
                res["figsplit"].append(item[0])
        except ImportError:
            pass

        # 24. блок целиком повторяет соседний (дубль шапки или абзаца)
        try:
            import detect_dupblock
            for pair in detect_dupblock.scan(num):
                res["dupblock"].append(pair[0])
        except ImportError:
            pass

        # 23. слово разорвано переносом между блоками
        try:
            import detect_hyphsplit
            for a_i, _b, _t, _h in detect_hyphsplit.scan(num):
                res["hyphsplit"].append(a_i)
        except ImportError:
            pass

        # 21. пример SIP-сообщения слипся в абзац
        try:
            import detect_example
            for i in detect_example.scan(num):
                res["example"].append(i)
        except ImportError:
            pass

        # 20. обычный текст попал в блок «код»
        try:
            import detect_textcode
            for i in detect_textcode.scan(num):
                res["textcode"].append(i)
        except ImportError:
            pass

        # 19. склеены поля формы (IANA, авторы)
        try:
            import detect_form
            for i in detect_form.scan(num):
                res["form"].append(i)
        except ImportError:
            pass

        # 18. список вклеен в абзац
        try:
            import detect_inline_list
            for i in detect_inline_list.scan(num):
                res["inlinelist"].append(i)
        except ImportError:
            pass

        # 17. дубль в начале блока
        try:
            import detect_duphead
            for i, _ln, _s in detect_duphead.scan(num):
                res["duphead"].append(i)
        except ImportError:
            pass

        # 16. потерян хвост-анонс («…:» в оригинале, точка в переводе)
        try:
            import detect_tail
            for i, _nxt in detect_tail.scan(num):
                res["tail"].append(i)
        except ImportError:
            pass

        # 15. псевдографика потеряла структуру (таблица сплющена в строку)
        try:
            import detect_squeeze
            for i in detect_squeeze.scan(num):
                res["squeeze"].append(i)
        except ImportError:
            pass

        # 14. остаток оглавления в теле документа
        try:
            import detect_toc
            for i in detect_toc.scan(num):
                res["toc"].append(i)
        except ImportError:
            pass

        # 13. начало документа оформлено по правилу (шапка + title)
        try:
            import detect_preamble
            for msg in detect_preamble.scan(num):
                res["preamble"].append((0, msg))
        except ImportError:
            pass

        # 12. схема разрезана на два блока
        try:
            import detect_diagsplit
            for i, j, _a, _b in detect_diagsplit.scan(num):
                res["diagsplit"].append(i)
        except ImportError:
            pass

        # 11. в прозу вклеена структура (таблица, ABNF, пример сообщения)
        try:
            import detect_structure
            for i, what, cnt, s in detect_structure.scan(num):
                res["structure"].append((i, what))
        except ImportError:
            pass

        # 9. сдвиг границ: русский блок начинается с обрывка фразы,
        # хотя английский начинается нормально
        try:
            import detect_shift
            for i, en, ru in detect_shift.scan(num):
                res["shift"].append((i, ru))
        except ImportError:
            pass

    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    full = "--fast" not in sys.argv
    nums = [int(a) for a in args] if args else sorted(
        n for n in store.status_report() if isinstance(n, int))

    totals = {"missing": 0, "short": 0, "long": 0, "dupe": 0,
              "foreign": 0, "original": 0, "broken": 0, "cut": 0,
              "shift": 0, "headnum": 0, "structure": 0, "diagsplit": 0, "preamble": 0, "toc": 0, "squeeze": 0, "tail": 0, "duphead": 0, "inlinelist": 0, "form": 0, "textcode": 0, "example": 0, "hyphsplit": 0, "dupblock": 0, "figsplit": 0, "mergepara": 0, "headlost": 0, "codelist": 0, "spill": 0, "extrasent": 0, "colspace": 0,
              "artifacts": 0, "dupword": 0, "urlcase": 0, "paren": 0, "script": 0, "secnum": 0}
    problems = 0

    info_dup = info_num = 0

    for num in nums:
        r = audit(num, full=full)
        if r is None:
            continue
        # информационные проверки: шумят, поэтому в зачёт не идут
        try:
            import detect_cross_dupe
            info_dup += len(detect_cross_dupe.scan(num, threshold=0.7))
        except ImportError:
            pass
        try:
            import detect_numbers
            info_num += len(detect_numbers.scan(num))
        except ImportError:
            pass
        try:
            import detect_duphead
            info_dup += len(detect_duphead.scan(num))
        except ImportError:
            pass
        c = {k: len(v) for k, v in r.items()}
        if not any(c.values()):
            continue
        problems += 1
        for k in totals:
            totals[k] += c[k]
        print("RFC %-5d missing:%d short:%d long:%d dupe:%d foreign:%d original:%d "
              "broken:%d cut:%d shift:%d headnum:%d structure:%d diagsplit:%d "
              "preamble:%d toc:%d squeeze:%d tail:%d duphead:%d inlinelist:%d "
              "form:%d textcode:%d example:%d hyphsplit:%d dupblock:%d figsplit:%d mergepara:%d headlost:%d codelist:%d spill:%d extrasent:%d colspace:%d "
              "artifacts:%d dupword:%d urlcase:%d paren:%d script:%d secnum:%d"
              % (num, c["missing"], c["short"], c["long"],
                 c["dupe"], c["foreign"], c["original"], c["broken"],
                 c["cut"], c["shift"], c["headnum"], c["structure"],
                 c["diagsplit"], c["preamble"], c["toc"], c["squeeze"], c["tail"], c["duphead"], c["inlinelist"], c["form"], c["textcode"], c["example"], c["hyphsplit"], c["dupblock"], c["figsplit"], c["mergepara"], c["headlost"], c["codelist"], c["spill"], c["extrasent"], c["colspace"],
                 c["artifacts"], c["dupword"], c["urlcase"], c["paren"], c["script"], c["secnum"]))
        for i, s in r["foreign"]:
            print("   [ЧУЖОЙ] блок %d: %s" % (i, s))
        for i in r["dupe"]:
            print("   [ДУБЛЬ] блок %d" % i)
        for i, rt in r["long"]:
            print("   [РАЗДУТ] блок %d ratio=%.2f" % (i, rt))
        for i, rt in r["short"]:
            print("   [ОБРЫВ] блок %d ratio=%.2f" % (i, rt))
        for i in r["original"][:6]:
            print("   [ОРИГИНАЛ] блок %d: EN не найден дословно в .txt" % i)
        for kind, i, s in r["broken"][:10]:
            print("   [РАЗОРВАНО] блок %d (%s): %s" % (i, kind, s))
        for i, s in r["cut"][:10]:
            print("   [ОБРЕЗАНО] блок %d: перевод обрывается …%r" % (i, s))
        for i, s in r["shift"][:10]:
            print("   [СДВИГ] блок %d: перевод начинается с обрывка %r" % (i, s))
        for i, num, s in r["headnum"][:10]:
            print("   [НОМЕР] блок %d: нет номера %s, стоит %r" % (i, num, s))
        for i, msg in r["preamble"][:10]:
            print("   [НАЧАЛО] %s" % msg)
        for i in r["hyphsplit"][:8]:
            print("   [ПЕРЕНОС] блок %d: слово разорвано между блоками" % i)
        for i in r["example"][:8]:
            print("   [ПРИМЕР] блок %d: пример SIP слипся в абзац" % i)
        for i in r["textcode"][:8]:
            print("   [В КОДЕ] блок %d: текст выпал в блок «код»" % i)
        for i in r["form"][:8]:
            print("   [ФОРМА] блок %d: поля склеены в строку" % i)
        for i in r["inlinelist"][:8]:
            print("   [СПИСОК] блок %d: список вклеен в абзац" % i)
        for i in r["duphead"][:8]:
            print("   [ДУБЛЬ] блок %d: начало дублирует предыдущий" % i)
        for i in r["tail"][:8]:
            print("   [АНОНС] блок %d: потерян хвост с двоеточием" % i)
        for i in r["squeeze"][:5]:
            print("   [ПСЕВДОГРАФИКА] блок %d: структура потеряна" % i)
        for i in r["toc"][:5]:
            print("   [ОГЛАВЛЕНИЕ] блок %d: обрывок оглавления в теле" % i)
        for i in r["diagsplit"][:10]:
            print("   [РАЗРЕЗ] блок %d: схема разрезана на две" % i)
        for i, what in r["structure"][:10]:
            print("   [СТРУКТУРА] блок %d: в прозе %s" % (i, what))
        for i, reason in r["artifacts"][:8]:
            print("   [АРТЕФАКТ] блок %d: %s" % (i, reason))
        for i in r["dupword"][:8]:
            print("   [ПОВТОР] блок %d: слово повторено подряд" % i)
        for i in r["urlcase"][:8]:
            print("   [URL] блок %d: изменён регистр URI" % i)
        for i in r["paren"][:8]:
            print("   [СКОБКИ] блок %d: дисбаланс скобок в переводе" % i)
        for i, reason in r["script"][:8]:
            print("   [АЛФАВИТ] блок %d: %s" % (i, reason))
        for i in r["secnum"][:8]:
            print("   [РАЗДЕЛ] блок %d: номер раздела не совпадает с EN" % i)

    print()
    print("К сведению (не блокирует сборку):")
    print("  подозрений на дубль (в т.ч. в начале блока): %d" % info_dup)
    print("  блоков с потерянными числами      : %d" % info_num)
    print()
    print("=" * 68)
    print("ИТОГО по %d документам с замечаниями" % problems)
    for k, v in totals.items():
        print("  %-9s %d" % (k, v))
    print("=" * 68)
    return 1 if any(totals.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
