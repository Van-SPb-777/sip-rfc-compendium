# -*- coding: utf-8 -*-
"""
Поиск блоков, где перевод обрывается посреди фразы.

Обе колонки должны читаться как законченный текст. Признак обрыва:
текст не заканчивается точкой/двоеточием/закрывающей скобкой и последнее
слово — предлог/союз/артикль/служебное слово.

Проверяются ОБЕ колонки, но результат разный:

  • RU обрывается, а EN продолжается — это ДЕФЕКТ ПЕРЕВОДА, в колонке
    не хватает окончания фразы. Такие находки блокируют сборку.

  • EN обрывается — это НЕ дефект: парсер разрезал предложение по
    структуре исходника (абзац переходил через разрыв страницы, или
    в источнике текст физически оборван). Продолжение стоит в следующем
    блоке, и в PDF колонка читается сверху вниз. Такие находки только
    печатаются для сведения, в broken не попадают.

Определение «RU короче, чем нужно»: RU заканчивается на служебном слове,
а EN — нет (значит EN эту фразу закончил, а RU потерял окончание).
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import store

# Предлоги, союзы, артикли, служебные слова на конце
TAIL_EN = re.compile(
    r"\b(the|a|an|of|in|on|at|to|for|with|by|from|and|or|but|is|are|was|were|"
    r"be|been|that|which|this|these|those|it|its|as|if|when|then|than|such|"
    r"any|all|some|each|every|no|not|may|can|will|would|should|could|must|"
    r"only|also|however|thus|see|via|per|into|over|under|between|within)\s*$",
    re.I)
TAIL_RU = re.compile(
    r"\b(в|во|на|о|об|обо|из|к|ко|по|для|при|с|со|от|до|за|под|над|без|через|"
    r"между|и|или|но|а|что|как|который|которая|которое|которые|которых|"
    r"этот|эта|это|эти|этого|этой|либо|только|также|такой|такая|такие|"
    r"тогда|если|чтобы|чем|тем|их|его|её|ее|свой|свои|которым|котором|"
    r"которыми|какие|каких|каким|какими|ещё|еще|"
    # существительные в косвенных падежах: фраза обрывается на «в разделе»
    r"раздел|раздела|разделу|разделом|разделе|"
    r"разделы|разделов|разделам|разделами|разделах|"
    r"рисунок|рисунка|рисунку|рисунком|рисунке|"
    r"рисунки|рисунков|рисункам|рисунками|рисунках|"
    r"таблица|таблицы|таблице|таблицу|таблицей|таблиц|"
    r"пункт|пункта|пункту|пунктом|пункте|"
    r"пункты|пунктов|пунктам|пунктами|пунктах|"
    r"глава|главы|главе|главу|главой|глав|"
    r"приложение|приложения|приложению|приложением|приложении)\s*$", re.I)

# Допустимые окончания, которые не считаем обрывом
OK_END = ".!?:;)]}\"»…"


def looks_cut(text, tail_re):
    t = (text or "").strip()
    if not t:
        return False
    if t[-1] in OK_END:
        return False
    return bool(tail_re.search(t[-50:]))


def scan(num):
    """(дефекты перевода, сведения об обрывах оригинала)."""
    obj = store.load(num)
    if not obj or obj.get("excluded"):
        return [], []
    ru_bad, en_info = [], []
    blocks = obj["blocks"]
    for i, b in enumerate(blocks):
        if b["kind"] not in ("heading", "prose", "prose_cont"):
            continue
        en = b.get("en") or ""
        ru = b.get("ru") or ""
        if len(en) < 80:
            continue
        # шапку RFC не проверяем: там русский текст — переложение, а не перевод
        if "Request for Comments:" in en:
            continue
        en_cut = looks_cut(en, TAIL_EN)
        ru_cut = bool(ru.strip()) and looks_cut(ru, TAIL_RU)
        # перевод оборван, а оригинал — нет: окончание фразы потеряно
        if ru_cut and not en_cut:
            ru_bad.append((i, ru[-70:]))
        elif (ru and not en_cut and en.rstrip().endswith('.')
              and re.search(r'[A-Za-zА-Яа-яЁё0-9]$', ru.rstrip())):
            # вторая форма обрыва: русский текст просто не заканчивается
            # точкой, хотя английский закончил предложение. Так выглядят
            # переводы, сделанные до того, как блок стал длиннее
            ru_bad.append((i, "нет завершения: " + ru[-60:]))
        elif en_cut:
            en_info.append((i, en[-70:]))
    return ru_bad, en_info


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nums = ([int(a) for a in args[0].split(",")] if args
            else sorted(x for x in store.status_report() if isinstance(x, int)))
    tot_bad = tot_info = 0
    for n in nums:
        bad, info = scan(n)
        if not bad and not info:
            continue
        tot_bad += len(bad)
        tot_info += len(info)
        print("RFC %-5d дефектов перевода: %-3d обрывов оригинала: %d"
              % (n, len(bad), len(info)))
        for i, s in bad[:6]:
            print("   [ПЕРЕВОД] блок %-5d ...%r" % (i, s))
    print()
    print("ИТОГО: дефектов перевода %d, обрывов оригинала %d" % (tot_bad, tot_info))
