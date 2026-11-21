"""
Парсер текстов RFC на блоки для двуязычной сборки.

Блоки: heading (заголовок раздела), prose (проза), preformatted (ABNF/примеры/код),
table (таблицы), boilerplate (колонтитулы RFC).
"""
import re, os

MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"

# строка колонтитула RFC: "Rosenberg, et. al.  Standards Track  [Page 12]"
RE_PAGE_FOOT = re.compile(r"\[Page\s+\d+\]\s*$")
# верхний колонтитул: "RFC 3261   SIP: Session Initiation Protocol   June 2002"
RE_PAGE_HEAD = re.compile(r"^RFC\s+\d{3,5}\s+\S.*\b" + MONTHS + r"\s+\d{4}\s*$")
# колонтитул, склеенный с текстом или не отделённый form feed:
# "RFC 3261          SIP: Session Initiation Protocol          June 2002"
RE_HEADER_INTERLEAVED = re.compile(
    r"^\s*RFC\s+\d{3,5}\b.*\b" + MONTHS + r"\s+\d{4}\s*$")
# заголовок раздела (без точек-заполнителей — те оставляем на отсев)
# заголовок может начинаться сразу с номера (без отступа):
#   "8.1.1.2 To"          — четыре компонента номера, затем короткое название,
#                            которое короче двух символов — разрешаем.
RE_HEADING = re.compile(
    r"^\s{0,6}(?P<num>\d+(?:\.\d+)*)\.?\s{1,4}(?P<title>[A-Z][^\n]{1,90})$"
)
RE_APPENDIX = re.compile(r"^\s{0,6}(?P<num>[A-Z](?:\.\d+)*)\.?\s{1,4}(?P<title>[A-Z][^\n]{1,90})$")
# строка заголовка НЕ должна содержать точку-завершение и затем заглавную прозу:
# "1. MUST   This word, or the terms ..." — это заголовок+проза в одной строке
RE_HEADING_WITH_PROSE = re.compile(
    r"^\s{0,6}(?P<num>\d+(?:\.\d+)*)\.?\s{1,4}(?P<title>[A-Z][A-Za-z0-9'\- ]{1,40}?)"
    r"\s{2,}(?P<prose>[A-Z][a-z]+.*)$"
)
# строка только с номером страницы или пробелами
RE_BLANKISH = re.compile(r"^[\s\f]*\d{0,4}[\s\f]*$")


def load_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("latin-1", errors="replace")


def strip_running_heads(lines):
    """Убирает колонтитулы страниц RFC (по верху и по низу страниц).

    ВАЖНО: разрыв страницы НЕ должен превращаться в пустую строку.
    Абзац в RFC часто переходит со страницы на страницу:

        «… works in concert with these protocols by»
        (пустые строки, нижний колонтитул «… [Page N]», form feed,
         верхний колонтитул «RFC N … Month YYYY», пустые строки)
        «enabling Internet endpoints …»

    Если всё это вместе с пустыми строками выбросить «как есть», между
    строками 446 и 455 останутся пустые строки, и сборщик блоков решит,
    что абзац кончился. Фраза разрежется пополам: левая колонка обрывается
    на предлоге «by», а продолжение уезжает в следующий блок.

    Поэтому здесь запоминаются сами пустые строки, но пустые строки,
    относящиеся только к разрыву страницы, вырезаются вместе с
    колонтитулами.
    """
    out = []
    # «подвешенные» пустые строки. Если после них встретится колонтитул —
    # они относятся к разрыву страницы и выбрасываются вместе с ним.
    pending_blanks = []
    # признак: мы только что прошли колонтитул, и пустые строки после него
    # тоже относятся к разрыву
    after_header = False

    for ln in lines:
        s = ln.strip()

        if RE_PAGE_FOOT.search(s) or RE_PAGE_HEAD.match(s) \
                or RE_HEADER_INTERLEAVED.match(s):
            pending_blanks = []
            after_header = True
            continue

        if not s or s == "\f":
            pending_blanks.append("")
            continue

        # содержательная строка
        if after_header:
            # пустые строки сразу после колонтитула — часть разрыва страницы
            pending_blanks = []
            after_header = False
        out.extend(pending_blanks)
        pending_blanks = []
        out.append(ln.replace("\f", ""))

    return out


def looks_like_toc(lines, i):
    """Строка — часть оглавления RFC (много точек-заполнителей или номер страницы справа)."""
    s = lines[i]
    if s.count(".") > 12:
        return True
    if re.search(r"\.\s{2,}\d{1,3}\s*$", s):
        return True
    if re.search(r"\.\s*\.\s*\.\s*\.", s):
        return True
    return False


def _find_abstract_end(lines):
    """
    Находит конец блока Abstract в шапке RFC.

    Возвращает индекс строки, СЛЕДУЮЩЕЙ за последней содержательной
    строкой Abstract, либо None, если Abstract не найден.

    Нужен для включения преамбулы в документ: титул, Status of this Memo,
    Copyright Notice и Abstract берём из шапки, а всё, что после Abstract
    и до первого раздела (обычно Table of Contents), отбрасываем.
    """
    abs_idx = None
    for i, ln in enumerate(lines[:400]):
        if re.match(r"^\s*Abstract\s*$", ln.strip(), re.I):
            abs_idx = i
            break
    if abs_idx is None:
        return None

    # идём вперёд до строки, похожей на заголовок следующего раздела
    # (например, "Table of Contents" или "1  Introduction")
    end = abs_idx + 1
    while end < len(lines) and end < 400:
        s = lines[end].strip()
        if not s:
            end += 1
            continue
        # "Table of Contents" или другой служебный заголовок шапки
        if re.match(r"^(Table of Contents|Table of contents)\s*$", s):
            break
        # обычный заголовок раздела «N Title»
        if is_heading(lines[end]) and not looks_like_toc(lines, end):
            break
        end += 1
    return end


def cut_preamble_and_tail(lines):
    """
    Отрезает хвост начиная с 'Full Copyright Statement'.

    Шапку документа (титул, Status of this Memo, Copyright Notice,
    Abstract) СОХРАНЯЕМ — она является частью RFC и подлежит переводу.
    Отбрасывается только Table of Contents, который заменяется
    собственным оглавлением сборника.

    Раньше здесь шапка отрезалась целиком, из-за чего в документах
    отсутствовали Abstract и Status of this Memo.
    """
    # граница: конец Abstract (если он есть) — начало тела
    abs_end = _find_abstract_end(lines)

    if abs_end is not None:
        start = abs_end
        # перепрыгиваем через Table of Contents, если он идёт следующим
        i = start
        while i < len(lines) and i < 400:
            s = lines[i].strip()
            if not s:
                i += 1
                continue
            if re.match(r"^Table of Contents\s*$", s, re.I):
                # пропускаем TOC до первого настоящего заголовка
                j = i + 1
                while j < len(lines):
                    if looks_like_toc(lines, j):
                        j += 1
                        continue
                    if not lines[j].strip():
                        j += 1
                        continue
                    if is_heading(lines[j]):
                        break
                    j += 1
                # заголовок сохраняем, TOC выкидываем
                body_start = j
            else:
                body_start = i
            break
        else:
            body_start = start
    else:
        # Abstract нет — старое поведение: от конца оглавления
        toc_end = 0
        for i, ln in enumerate(lines[:400]):
            if looks_like_toc(lines, i):
                toc_end = i
        body_start = 0
        for i in range(toc_end, len(lines)):
            if is_heading(lines[i]) and not looks_like_toc(lines, i):
                body_start = i
                break
        if body_start == 0:
            for i, ln in enumerate(lines):
                if is_heading(ln) and not looks_like_toc(lines, i):
                    body_start = i
                    break

    start = 0  # шапку берём от начала
    head = lines[:body_start]
    # из шапки выкидываем строки оглавления и сам заголовок "Table of Contents"
    head_clean = []
    skip_toc = False
    for ln in head:
        s = ln.strip()
        if re.match(r"^Table of Contents\s*$", s, re.I):
            skip_toc = True
            continue
        if skip_toc:
            # TOC продолжается, пока строки выглядят как оглавление или пусты
            if not s or looks_like_toc([ln], 0) or re.search(r"\.\s*\.\s*\.", ln):
                continue
            skip_toc = False
        if looks_like_toc([ln], 0):
            continue
        head_clean.append(ln)
    head = head_clean
    # Хвост НЕ отрезаем: раздел "Full Copyright Statement" является частью RFC
    # и переводится наравне с остальным (это требование сохранности оригинала).
    end = len(lines)
    # дополнительно: если 'Acknowledgments' идёт в конце — обычно это тоже служебная часть,
    # но её оставляем в переводе, поэтому не отрезаем
    #
    # head — преамбула (титул, Status of this Memo, Copyright Notice, Abstract);
    # она теперь входит в результат наравне с телом.
    return head + lines[body_start:end], 0


def looks_like_diagram_line(ln):
    """Строка ASCII-схемы: рамка +-+-, вертикальные черты, номера битов."""
    s = ln
    if re.search(r"[+][-]{2,}[+]", s):
        return True
    if s.count("|") >= 2 and s.count("-") >= 4:
        return True
    if re.search(r"^0\s+1\s+2\s+3\s+4\s+5\s+6", s.strip()):
        return True
    if re.match(r"^\s{0,8}0\s{2,}\d\s+", s):
        return True
    # рамка без содержимого: +-+-+- и т.п.
    if re.fullmatch(r"\s*[+\-\s]+\s*", s) and s.count("+") >= 2:
        return True
    return False


def is_heading(ln, lines=None, i=None):
    """Заголовок раздела: номер идёт в начале строки с минимальным отступом.

    Заголовки RFC стоят в колонке 0 и не имеют отступа. Проза может
    начинаться с трёх пробелов — именно там парсер ошибочно видел
    заголовки вида «1. If the request is an INVITE that contains an
    Expires header field, the UAS core sets a timer…» — это нумерованный
    пункт процедуры, а не раздел. Из-за такой ошибки фраза рвалась:
    первая строка уходила в "heading", а продолжение — в отдельный блок.

    Поэтому заголовком считается только строка БЕЗ отступа (колонка 0).
    Исключение — многострочные заголовки, где продолжение приходит с
    отступом; их собирает вызывающий код.
    """
    lead = len(ln) - len(ln.lstrip())
    if RE_HEADING.match(ln) and lead == 0:
        # заголовок не должен выглядеть как адрес: "545. Technology Square"
        # (ЧИСТОЕ число из 3+ цифр без точек) — это строка адреса.
        # Номер раздела с точками ("8.1.1.2") — всегда заголовок.
        m = RE_HEADING.match(ln)
        num = m.group("num")
        if "." not in num and len(num) >= 3:
            return False
        return True
    if RE_APPENDIX.match(ln) and lead == 0:
        # приложение верхнего уровня ('A. Collected Grammar')
        return True
    return False


def split_heading_prose(ln):
    """Если строка содержит заголовок и сразу прозу ('1. MUST   This word...'),
    возвращает (title, prose), иначе (None, None)."""
    # разбиваем по позиции первого большого пробельного разрыва
    parts = re.split(r"\s{2,}", ln.strip(), maxsplit=1)
    if len(parts) != 2:
        return None, None
    left, right = parts[0].strip(), parts[1].strip()
    # слева должен быть номер + короткое имя заголовка
    m = re.match(r"^(?P<num>\d+(?:\.\d+)*)\.?\s+(?P<title>.+)$", left)
    if not m:
        return None, None
    title = m.group("title").strip()
    # заголовок короткий (несколько слов), проза начинается с заглавной и содержит строчные
    if len(title) > 45:
        return None, None
    if not re.match(r"^[A-Z][a-z]", right):
        return None, None
    return title, right


def classify_preformatted(block):
    """Определяет, что за блоки с отступом >= 6: ABNF, код SIP, SDP, таблица,
    ASCII-диаграмма. Литеральный список прозы (строки-продолжения) — это проза."""
    text = "\n".join(block)
    # ASCII-диаграмма: рамки из +-+-+- или строки с номерами битов
    has_border = bool(re.search(r"[+\-]{6,}", text)) or text.count("+") >= 4
    has_bits = bool(re.search(r"0\s+1\s+2\s+3\s+4\s+5", text))
    has_pipes = text.count("|") >= 4
    if (has_border and has_pipes) or has_bits:
        return "diagram"
    if re.search(r"^\s*[a-z][a-z0-9-]*\s*=\s*", text, re.M):
        return "abnf"
    if re.search(r"^\s*(INVITE|ACK|BYE|CANCEL|REGISTER|OPTIONS|INFO|UPDATE|PRACK|"
                 r"SUBSCRIBE|NOTIFY|REFER|MESSAGE|SIP/2\.0)\b", text, re.M):
        return "sip"
    if re.search(r"^\s*v=\d", text, re.M) and re.search(r"^\s*m=\w+", text, re.M):
        return "sdp"
    # таблица: несколько строк, и в КАЖДОЙ строке есть 2+ колонки,
    # разделённые 3+ пробелами, причём каждая колонка короткая (слова, а не проза)
    lines_nb = [l for l in block if l.strip()]
    table_like = 0
    for l in lines_nb:
        cells = re.split(r"\s{3,}", l.strip())
        if len(cells) >= 2 and all(len(c) < 40 for c in cells if c):
            table_like += 1
    if lines_nb and table_like >= max(2, int(len(lines_nb) * 0.6)):
        return "table"
    # список/продолжение прозы: строки начинаются с обычного текста, а не с кода
    lines = [l.strip() for l in block if l.strip()]
    prose_like = sum(1 for l in lines if re.match(r"^[A-Za-z(\"'-]", l) and len(l) > 12)
    if lines and prose_like >= max(1, int(len(lines) * 0.7)):
        return "prose_cont"
    return "code"


# ---------- распознавание структурных вставок внутри прозы ----------
# В RFC структурированные вставки (таблицы, ABNF, примеры сообщений) часто
# имеют ТОТ ЖЕ отступ 3 пробела, что и обычная проза. Если не отличить их
# от текста, строки склеиваются в один абзац, и таблица или грамматика
# превращается в нечитаемую строку. Ниже — признаки таких вставок.

# определение ABNF: «name = …», «name =/ …»
RE_ABNF_DEF = re.compile(r"^[A-Za-z][A-Za-z0-9\-]{0,40}\s*=/?\s*\S")
# начало примера сообщения: «INVITE sip:… SIP/2.0», ответ «SIP/2.0 200 OK»
RE_SIP_START = re.compile(
    r"^(?:INVITE|REGISTER|OPTIONS|BYE|CANCEL|ACK|NOTIFY|SUBSCRIBE|PUBLISH|"
    r"INFO|UPDATE|PRACK|REFER|MESSAGE)\s+\S+\s+SIP/2\.0\b")
RE_SIP_STATUS = re.compile(r"^SIP/2\.0\s+\d{3}")
# строка заголовка сообщения: «Via: …», «Content-Length: 142»
RE_MSG_HEADER = re.compile(r"^[A-Za-z][A-Za-z0-9\-]{1,40}:\s+\S")
# продолжение грамматики: «/ …», «[ …», «( …», «*…», комментарий «; …»
RE_ABNF_CONT = re.compile(r"^(?:/|\[|\(|\*|;)")


def looks_structural(ln):
    """Строка начинает структурированную вставку (таблица/ABNF/сообщение)."""
    ind = len(ln) - len(ln.lstrip())
    s = ln.strip()
    # Определение ABNF проверяем при ЛЮБОМ отступе: в приложениях с собранной
    # грамматикой строки стоят в колонке 0 («INVITEm = %x49.4E…»), и старое
    # условие «отступ >= 2» их пропускало — грамматика склеивалась в абзац.
    if RE_ABNF_DEF.match(s):
        return True
    if ind < 2:
        return False
    if RE_SIP_START.match(s) or RE_SIP_STATUS.match(s):
        return True
    # строка таблицы: минимум две группы пробелов по 2+ и хотя бы три «клетки»
    if len(re.findall(r"\S {2,}\S", ln)) >= 2 and len(s.split()) >= 3:
        return True
    return False


def looks_structural_cont(ln, started_with_abnf):
    """Строка продолжает уже начатую структурную вставку."""
    s = ln.strip()
    if not s:
        return False
    if looks_structural(ln):
        return True
    if RE_MSG_HEADER.match(s):
        return True
    if started_with_abnf and RE_ABNF_CONT.match(s):
        return True
    if len(re.findall(r"\S {2,}\S", ln)) >= 2:
        return True
    return False


def parse_rfc(path):
    """Возвращает список блоков: dicts с полями kind, text, heading."""
    raw_lines = load_text(path).splitlines()
    lines = strip_running_heads(raw_lines)
    body, offset = cut_preamble_and_tail(lines)

    blocks = []
    i = 0
    n = len(body)

    while i < n:
        ln = body[i]

        # пустые строки — пропускаем, они разделители
        if not ln.strip():
            i += 1
            continue

        # заголовок раздела (возможно, вместе с прозой в одной строке)
        if is_heading(ln) and not looks_like_toc(body, i):
            t_title, t_prose = split_heading_prose(ln)
            m = RE_HEADING.match(ln) or RE_APPENDIX.match(ln)
            if t_title:
                num = m.group("num") if m else ""
                title = t_title
            else:
                title = m.group("title").strip() if m else ln.strip()
                num = m.group("num") if m else ""
            # многострочный заголовок: продолжение с отступом
            # (только если заголовок НЕ совмещён с прозой в одной строке)
            j = i + 1
            extra = []
            if not t_prose:
                while j < n and body[j].strip() and not body[j].strip()[0].isdigit() \
                        and len(body[j]) - len(body[j].lstrip()) >= 3 and len(extra) < 2:
                    if is_heading(body[j]):
                        break
                    extra.append(body[j].strip())
                    j += 1
            full_title = " ".join([title] + extra).strip()
            blocks.append({"kind": "heading", "num": num, "title": full_title,
                           "text": (num + ". " + full_title) if num else full_title})
            # проза из той же строки — отдельным блоком, но с продолжением
            # абзаца (следующие строки с отступом, идущие сразу за ней)
            if t_prose:
                cont = []
                while j < n:
                    cur = body[j]
                    if not cur.strip():
                        break
                    ind2 = len(cur) - len(cur.lstrip())
                    if ind2 >= 6:
                        break
                    if is_heading(cur) and not looks_like_toc(body, j):
                        break
                    cont.append(cur.strip())
                    j += 1
                full_prose = " ".join([t_prose] + cont)
                full_prose = re.sub(r"\s{2,}", " ", full_prose).strip()
                blocks.append({"kind": "prose", "text": full_prose})
            i = j
            continue

        # блок с отступом >= 6 — preformatted (ABNF/код/примеры/таблица)
        indent = len(ln) - len(ln.lstrip())
        if indent >= 6:
            group = []
            while i < n:
                cur = body[i]
                if not cur.strip():
                    # пустая строка внутри блока — добавляем, если дальше ещё отступ
                    k = i + 1
                    while k < n and not body[k].strip():
                        k += 1
                    if k < n and (len(body[k]) - len(body[k].lstrip())) >= 6:
                        group.append("")
                        i += 1
                        continue
                    break
                if (len(cur) - len(cur.lstrip())) < 6:
                    break
                group.append(cur)
                i += 1
            kind = classify_preformatted(group)
            if kind == "prose_cont" and blocks and blocks[-1]["kind"] == "prose":
                # это продолжение предыдущего абзаца прозы — приклеиваем
                cont = " ".join(l.strip() for l in group if l.strip())
                cont = re.sub(r"\s{2,}", " ", cont).strip()
                if cont:
                    blocks[-1]["text"] = (blocks[-1]["text"] + " " + cont).strip()
                continue
            blocks.append({"kind": kind, "text": "\n".join(group)})
            continue

        # ASCII-диаграмма — собираем ВСЕ подряд идущие строки схемы целиком,
        # сохраняя переводы строк и выравнивание (независимо от отступа)
        if looks_like_diagram_line(ln):
            group = []
            while i < n:
                cur = body[i]
                if not cur.strip():
                    # пустая строка допустима внутри схемы, если дальше схема продолжается
                    k = i + 1
                    while k < n and not body[k].strip():
                        k += 1
                    if k < n and looks_like_diagram_line(body[k]):
                        group.append("")
                        i += 1
                        continue
                    break
                if looks_like_diagram_line(cur):
                    group.append(cur)
                    i += 1
                    continue
                # содержимое схемы: строка внутри рамки/с вертикальными чертами
                if group and ("|" in cur or re.search(r"[+][-]{2,}", cur)):
                    group.append(cur)
                    i += 1
                    continue
                break
            diagram = "\n".join(group).strip("\n")
            if diagram:
                blocks.append({"kind": "diagram", "text": diagram})
            continue

        # обычный абзац прозы: собираем строки до пустой строки или до отступа >= 6
        para = []
        structural = False
        while i < n:
            cur = body[i]
            if not cur.strip():
                break
            ind = len(cur) - len(cur.lstrip())
            if ind >= 6 and para:
                break
            if is_heading(cur) and not looks_like_toc(body, i):
                break
            # Структурная вставка с отступом 3: таблица, ABNF, пример сообщения.
            # Раньше такие строки склеивались с абзацем — из-за этого таблицы
            # и грамматика превращались в одну длинную строку.
            if looks_structural(cur):
                if para:
                    break       # абзац закончился, вставка пойдёт отдельным блоком
                structural = True
                break
            para.append(cur.strip())
            i += 1

        if para:
            text = " ".join(para)
            text = re.sub(r"\s{2,}", " ", text).strip()
            if text:
                blocks.append({"kind": "prose", "text": text})
            continue

        if structural:
            group = []
            started_abnf = bool(RE_ABNF_DEF.match(body[i].strip()))
            while i < n:
                cur = body[i]
                if not cur.strip():
                    # пустая строка внутри вставки допустима, если дальше
                    # вставка продолжается
                    k = i + 1
                    while k < n and not body[k].strip():
                        k += 1
                    if k < n and looks_structural_cont(body[k], started_abnf):
                        group.append("")
                        i += 1
                        continue
                    break
                if not group:
                    group.append(cur)
                    i += 1
                    continue
                if not looks_structural_cont(cur, started_abnf):
                    break
                group.append(cur)
                i += 1
            if group:
                kind = classify_preformatted(group)
                blocks.append({"kind": kind, "text": "\n".join(group)})
            continue

        i += 1

    return blocks


if __name__ == "__main__":
    import sys, json
    D = os.path.abspath(os.environ.get("RFC_SRC") or os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "rfc-sip"))
    for num in (2119, 2976, 5806):
        p = os.path.join(D, "rfc%d.txt" % num)
        bl = parse_rfc(p)
        kinds = {}
        for b in bl:
            kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
        print("RFC %d: блоков %d -> %s" % (num, len(bl), kinds))
        print("  первые 8:")
        for b in bl[:8]:
            print("    [%-10s] %s" % (b["kind"], b["text"][:70].replace("\n", " | ")))
        print()
