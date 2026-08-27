"""Метрики уровня текста: ритм предложений, структура, морфология (опционально).

Ритм и структура — на stdlib. Морфология (соотношение существительных к
глаголам, цепочки родительных) считается только если установлен pymorphy3;
без него линтер работает, просто эти строки в отчёте отсутствуют.

Пороги взяты как ориентиры из ilyautov/humanizer-ru (MIT) и «Чуковского»:
CV длин предложений ниже 0.35 — монотонно; предложение длиннее 30 слов —
тяжёлое; абзац длиннее 120 слов — стена текста. Для статьи порог стены выше:
на Хабре и Инфостарте абзац на 150–200 слов с одной мыслью — норма лонгрида,
а не дефект (проверено на 16 живых статьях).
"""

from __future__ import annotations

import re
import statistics
from typing import Optional

from .terms import TERM_LEMMAS
from .textprep import URL, WORD, Prepared

CV_FLAT = 0.35
CV_TARGET = 0.45
LONG_SENTENCE = 30
VERY_LONG_SENTENCE = 45
WALL_PARAGRAPH = 120
WALL_BY_GENRE = {"article": 200, "academic": 220, "fiction": 260}
PARA_CV_FLAT = 0.35
PARA_MIN = 6
LISTICLE_MIN = 6
LISTICLE_SHARE = 0.5
EM_DASH_DENSITY = 3.0   # на 100 слов; ниже — обычная русская пунктуация


def _cv(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    if not mean:
        return 0.0
    return statistics.pstdev(values) / mean


def rhythm(prep: Prepared) -> dict:
    lengths = prep.sentence_words
    n = len(lengths)
    if not n:
        return {"sentences": 0}
    diffs = [abs(a - b) for a, b in zip(lengths, lengths[1:])]
    return {
        "sentences": n,
        "mean_len": round(statistics.mean(lengths), 1),
        "cv": round(_cv(lengths), 3),
        "min_len": min(lengths),
        "max_len": max(lengths),
        "mean_diff": round(statistics.mean(diffs), 1) if diffs else 0.0,
        "short_share": round(sum(1 for x in lengths if x <= 8) / n, 2),
        "long": [i for i, x in enumerate(lengths) if x > LONG_SENTENCE],
        "very_long": [i for i, x in enumerate(lengths) if x > VERY_LONG_SENTENCE],
        "questions": sum(1 for s in prep.sentences if s.rstrip().endswith("?")),
    }


def parcellation_runs(prep: Prepared, max_words: int = 3, min_run: int = 3) -> list[int]:
    """Индексы начала серий из min_run и более подряд предложений не длиннее max_words."""
    runs = []
    streak = 0
    for i, n in enumerate(prep.sentence_words):
        if n <= max_words:
            streak += 1
            if streak == min_run:
                runs.append(i - min_run + 1)
        else:
            streak = 0
    return runs


def structure(prep: Prepared, wall_limit: int = WALL_PARAGRAPH) -> dict:
    para_words = [len(WORD.findall(p)) for p in prep.paragraphs]
    nonblank = [ln for ln in prep.lines if ln.kind != "blank"]
    list_share = (prep.list_items / len(nonblank)) if nonblank else 0.0
    em_dash = prep.prose_text.count("—")
    words = prep.words or 1
    return {
        "paragraphs": len(para_words),
        "para_cv": round(_cv(para_words), 3),
        "wall_limit": wall_limit,
        "walls": [i for i, w in enumerate(para_words) if w > wall_limit],
        "list_items": prep.list_items,
        "list_share": round(list_share, 2),
        "headings": prep.headings,
        "em_dash": em_dash,
        "em_dash_density": round(em_dash / words * 100, 1),
        "truncated": truncation(prep) == "error",
        "unfinished": truncation(prep) == "note",
    }


# Слова, на которых предложение не заканчивают: обрыв после них — почти наверняка лимит модели.
_CUT_WORDS = {
    "и", "а", "но", "или", "либо", "что", "чтобы", "как", "если", "когда", "хотя", "потому",
    "в", "во", "на", "для", "с", "со", "к", "ко", "по", "при", "из", "от", "до", "за", "под",
    "над", "о", "об", "обо", "у", "без", "через", "между", "про", "не", "ни", "то", "же",
    "который", "которая", "которое", "которые", "которых", "которым", "также", "то есть",
    "это", "этот", "эта", "эти", "тот", "та", "те", "его", "её", "их", "свой", "свою", "их",
}


def truncation(prep: Prepared) -> str | None:
    """Оборван ли текст на полуслове.

    "error" — почти наверняка лимит модели: последнее слово предлог, союз или
    местоимение, либо фраза кончается запятой, тире, открытой скобкой.
    "note"  — нет точки в конце, но фраза выглядит законченной: у живого автора
    это чаще забытая точка («И до новых встреч в эфире»), чем обрыв.
    None    — всё в порядке; в том числе если строка кончается ссылкой
    («подписывайтесь на канал https://…») или текст кончается списком.
    """
    for ln in reversed(prep.lines):
        if ln.kind == "blank":
            continue
        if ln.kind != "prose":
            return None
        tail = ln.raw.rstrip()
        last_url = None
        for last_url in URL.finditer(tail):
            pass
        if last_url is not None and last_url.end() == len(tail):
            return None
        last = ln.text.rstrip()
        words = WORD.findall(last)
        if len(words) < 5:
            return None
        if last[-1] in ".!?…:;»)\"'*_]}":
            return None
        if last[-1] in ",—–-(" or words[-1].lower() in _CUT_WORDS:
            return "error"
        return "note"
    return None


def is_truncated(prep: Prepared) -> bool:
    return truncation(prep) == "error"


# ---------------------------------------------------------------------------
# Морфология (опционально, pymorphy3)
# ---------------------------------------------------------------------------
_NOMINAL_SUFFIXES = ("ение", "ание", "ация", "изация", "ировка", "ость", "ство")
_VERBAL = {"VERB", "INFN", "GRND", "PRTF", "PRTS"}
_TRANSPARENT = {"ADJF", "ADJS", "NUMR", "PRTF"}
GEN_CHAIN_NOUNS = 4
_morph_cache = None


def _flush_chain(run: list[str], chains: list[str]) -> None:
    """Цепочка считается по существительным; прилагательные внутри не в счёт."""
    if not run:
        return
    m = _morph()
    nouns_in_run = sum(1 for w in run if m.parse(w)[0].tag.POS == "NOUN")
    if nouns_in_run >= GEN_CHAIN_NOUNS:
        chains.append(" ".join(run))


def _morph():
    global _morph_cache
    if _morph_cache is None:
        import pymorphy3  # type: ignore
        _morph_cache = pymorphy3.MorphAnalyzer()
    return _morph_cache


def morphology_available() -> bool:
    try:
        import pymorphy3  # noqa: F401
        return True
    except ImportError:
        return False


def morphology(prep: Prepared) -> Optional[dict]:
    if not morphology_available():
        return None
    m = _morph()
    nouns = verbs = nominal = 0
    chains: list[str] = []
    for sentence in prep.sentences:
        run: list[str] = []
        for w in WORD.findall(sentence):
            if not re.search(r"[А-Яа-яЁё]", w):
                run = []
                continue
            p = m.parse(w)[0]
            pos = p.tag.POS
            if pos == "NOUN":
                nouns += 1
                lemma = p.normal_form
                if lemma.endswith(_NOMINAL_SUFFIXES) and lemma not in TERM_LEMMAS:
                    nominal += 1
                if "gent" in p.tag or not run:
                    run.append(w)
                else:
                    _flush_chain(run, chains)
                    run = [w]
            elif pos in _TRANSPARENT and run:
                # Прилагательное внутри цепочки («порядок формирования складских остатков»)
                # цепочку не рвёт, но и не удлиняет.
                run.append(w)
            else:
                if pos in _VERBAL:
                    verbs += 1
                _flush_chain(run, chains)
                run = []
        _flush_chain(run, chains)
    ratio = round(nouns / verbs, 2) if verbs else float(nouns)
    return {
        "nouns": nouns,
        "verbs": verbs,
        "noun_verb_ratio": ratio,
        "nominalizations": nominal,
        "genitive_chains": chains[:10],
    }


NV_TARGET = 2.5
