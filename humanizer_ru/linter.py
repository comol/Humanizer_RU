"""Линтер читаемости: находки по правилам + метрики + оценка 0–100.

Оценка — не «вероятность ИИ». Это сумма штрафов за то, что мешает читателю:
обёртки чат-бота, штампы, канцелярит, ровный ритм, стены текста. Показывать
её имеет смысл парой «было N — стало M», чтобы правка была измеримой.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from . import metrics as M
from .rules import (BOLD_RX, EMOJI_RX, GENRE_MUTE, GENRES, INTENSIFIER_RX, IS_RX, LEVEL_ORDER,
                    RULES, SOFTENERS, STACK_START_RX, TERM_SENSITIVE, VERB_NOUN_ENDINGS,
                    VERB_REPEAT_IGNORE, VERB_SUFFIX_RX, ZERO_WIDTH_RX)
from .terms import overlaps, term_spans
from .textprep import Prepared, prepare

BAND_CLEAN = 85
BAND_EDIT = 60


@dataclass
class Finding:
    level: str
    code: str
    title: str
    line: int
    excerpt: str
    advice: str
    category: str
    count: int = 1


@dataclass
class Report:
    genre: str
    words: int
    sentences: int
    score: int
    band: str
    penalties: list[dict]
    findings: list[Finding]
    metrics: dict
    muted: list[str]
    notes: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    def count(self, level: str) -> int:
        return sum(f.count for f in self.findings if f.level == level)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["errors"] = len(self.errors)
        return d


_WORD_CH = re.compile(r"[А-Яа-яЁёA-Za-z0-9-]")


def _excerpt(src: str, m: re.Match, width: int = 32) -> str:
    a, b = m.span()
    # Показываем совпадение целыми словами, а не по границе регэкспа.
    while a > 0 and _WORD_CH.match(src[a - 1]) and _WORD_CH.match(src[a]):
        a -= 1
    while b < len(src) and _WORD_CH.match(src[b]) and _WORD_CH.match(src[b - 1]):
        b += 1
    left = src[max(0, a - width):a].lstrip()
    right = src[b:b + width].rstrip()
    core = src[a:b]
    return (("…" if a - width > 0 else "") + left + "«" + core + "»" + right +
            ("…" if b + width < len(src) else "")).strip()


def _verb_stems(sentence: str) -> set[str]:
    stems = set()
    for w in re.findall(r"[а-яё]{5,}", sentence.lower()):
        if w.endswith(VERB_NOUN_ENDINGS) or not VERB_SUFFIX_RX.search(w):
            continue
        stem = VERB_SUFFIX_RX.sub("", w)[:6]
        if len(stem) >= 4 and not any(stem.startswith(x) for x in VERB_REPEAT_IGNORE):
            stems.add(stem)
    return stems


def _band(score: int) -> str:
    if score >= BAND_CLEAN:
        return "чисто"
    if score >= BAND_EDIT:
        return "точечная правка"
    return "переписать"


def lint(text: str, genre: str = "auto") -> Report:
    if genre not in GENRES:
        raise ValueError(f"genre must be one of {GENRES}")
    muted = GENRE_MUTE.get(genre, set())
    prep = prepare(text)
    findings: list[Finding] = []
    notes: list[str] = []

    def add(level, code, title, line, excerpt, advice, category, count=1):
        if category in muted or code in muted:
            return
        findings.append(Finding(level, code, title, line, excerpt, advice, category, count))

    # 1. Правила по строкам. Цитаты и таблицы не проверяем: цитата — чужой текст.
    for ln in prep.lines:
        if ln.kind in ("blank", "table", "quote"):
            continue
        if ZERO_WIDTH_RX.search(ln.raw):
            add("note", "zero-width", "Невидимый символ", ln.no,
                "символ нулевой ширины (их ставят и CMS с рассылками — проверь источник)",
                "Удалить, если символ не нужен для переноса.", "artifact")
        if ln.kind == "hr":
            add("note", "hr", "Разделитель «---» в теле", ln.no, ln.raw.strip()[:20],
                "Границы задают заголовки и абзацы, а не линии.", "hr")
            continue
        for rule in RULES:
            src = ln.raw if rule.scope == "raw" else ln.text
            if not src:
                continue
            spans = term_spans(src) if rule.category in TERM_SENSITIVE else []
            if rule.unless is not None:
                spans = spans + [m.span() for m in rule.unless.finditer(src)]
            for m in rule.pattern.finditer(src):
                if spans and overlaps(m.span(), spans):
                    continue
                add(rule.level, rule.code, rule.title, ln.no, _excerpt(src, m), rule.advice,
                    rule.category)
        if ln.kind == "heading" and EMOJI_RX.search(ln.text):
            add("note", "emoji", "Эмодзи в заголовке", ln.no, ln.text.strip()[:60],
                "Оставить, только если это голос автора или формат площадки.", "emoji")
        elif ln.kind == "list" and EMOJI_RX.match(ln.text.strip()):
            add("note", "emoji", "Эмодзи как маркер списка", ln.no, ln.text.strip()[:60],
                "Обычный маркер читается не хуже.", "emoji")

    words = prep.words or 1

    # 2. Плотности по всему тексту.
    is_hits = IS_RX.findall(prep.prose_text)
    if len(is_hits) >= 2 and len(is_hits) / words * 200 >= 2:
        add("low", "is-density", "Много «является»", 0,
            f"«является» ×{len(is_hits)} на {words} слов",
            "Связка «быть» в настоящем времени в русском не нужна: перестроить фразы.",
            "is-density", count=len(is_hits))
    intens = INTENSIFIER_RX.findall(prep.prose_text)
    if len(intens) >= 3 and len(intens) / words * 100 > 1.5:
        add("note", "intensifier", "Усилители", 0,
            f"{len(intens)} на {words} слов: " + ", ".join(sorted(set(w.lower() for w in intens))[:6]),
            "Удалить усилитель и проверить: если смысл не изменился, он был лишним.",
            "intensifier", count=len(intens))

    # 3. Сигналы уровня предложений.
    for s in prep.sentences:
        low = s.lower()
        hits = sum(low.count(w) for w in SOFTENERS)
        if hits >= 3:
            add("low", "hedge", "Каскад смягчений", 0, f"{hits} смягчения: {s[:70]}",
                "Оставить одно смягчение или дать прямое утверждение.", "hedge")

    rh = M.rhythm(prep)
    if rh.get("sentences"):
        very_long = rh["very_long"]
        long_only = [i for i in rh["long"] if i not in very_long]
        for i in very_long:
            add("low", "long-sentence", "Очень длинное предложение", 0,
                f"{prep.sentence_words[i]} слов: {prep.sentences[i][:70]}…",
                "Разбить на два-три: длиннее 30 слов читатель теряет начало.", "long-sentence")
        if long_only:
            add("note", "long-sentence", "Длинные предложения", 0,
                f"{len(long_only)} шт. длиннее {M.LONG_SENTENCE} слов, например: {prep.sentences[long_only[0]][:60]}…",
                "Проверить чтением вслух; где сбивается дыхание — точка.", "long-sentence",
                count=len(long_only))
        if rh["sentences"] >= 8 and rh["cv"] < M.CV_FLAT:
            add("low", "rhythm-flat", "Ровный ритм", 0,
                f"CV длин предложений {rh['cv']} (живой текст ≥{M.CV_TARGET}); средняя {rh['mean_len']} слов",
                "Чередовать: короткое для акцента, длинное для развития мысли.", "rhythm")
        if rh["sentences"] >= 10 and rh["short_share"] == 0:
            add("note", "rhythm-noshort", "Нет коротких предложений", 0,
                "ни одного предложения до 8 слов — нет пауз и акцентов",
                "Одну мысль в абзаце сказать коротко.", "rhythm")
        for i in M.parcellation_runs(prep):
            add("low", "parcellation", "Парцелляция", 0,
                " ".join(prep.sentences[i:i + 3])[:70],
                "Склеить обрубки в полное предложение — акцент останется, спектакль уйдёт.",
                "parcellation")

    # 4. Повтор глагольной основы в соседних предложениях (слабый сигнал).
    for a, b in zip(prep.sentences, prep.sentences[1:]):
        common = _verb_stems(a) & _verb_stems(b)
        if common:
            add("note", "verb-repeat", "Повтор глагола", 0,
                f"«{sorted(common)[0]}…» в соседних предложениях: {b[:60]}",
                "Второй глагол подобрать под его подлежащее, если повтор не намеренный.",
                "verb-repeat")

    # 5. Стопка абзацев без связок.
    stacked = [no for p, no in zip(prep.paragraphs, prep.paragraph_lines) if STACK_START_RX.match(p)]
    if len(stacked) >= 2:
        add("low", "paragraph-stack", "Стопка абзацев", 0,
            f"абзацы со строк {', '.join(map(str, stacked[:5]))} начинаются с «кроме того / также / более того»",
            "Связать абзацы по смыслу: отсылка, подхват мысли, «но», «поэтому», контраст.",
            "paragraph-stack", count=len(stacked))

    # 6. Структура. Порог «стены» зависит от жанра: в статье абзац на 150 слов — норма.
    st = M.structure(prep, M.WALL_BY_GENRE.get(genre, M.WALL_PARAGRAPH))
    if st["truncated"]:
        add("error", "truncated", "Обрыв на полуслове", prep.lines[-1].no if prep.lines else 0,
            prep.paragraphs[-1][-70:] if prep.paragraphs else "",
            "Дописать или обрезать по последнему полному предложению.", "truncated")
    elif st["unfinished"]:
        add("note", "unfinished", "Нет точки в конце", prep.lines[-1].no if prep.lines else 0,
            prep.paragraphs[-1][-70:] if prep.paragraphs else "",
            "Проверить, что текст не оборван; если закончен — поставить точку.", "truncated")
    for i in st["walls"]:
        add("low", "wall", "Стена текста", prep.paragraph_lines[i],
            f"абзац на {len(re.findall(r'[А-Яа-яЁёA-Za-z0-9]+', prep.paragraphs[i]))} слов "
            f"(порог для жанра — {st['wall_limit']})",
            "Разбить: один абзац — одна мысль.", "wall")
    if st["paragraphs"] >= M.PARA_MIN and st["para_cv"] < M.PARA_CV_FLAT:
        add("note", "paragraph-flat", "Абзацы одной длины", 0,
            f"{st['paragraphs']} абзацев, CV={st['para_cv']}",
            "Шаблонная нарезка выдаёт генерацию; длина абзаца — от мысли, а не от сетки.",
            "rhythm")
    if st["list_items"] >= M.LISTICLE_MIN and st["list_share"] > M.LISTICLE_SHARE:
        add("note", "listicle", "Текст из списков", 0,
            f"{st['list_items']} пунктов, {int(st['list_share'] * 100)}% строк",
            "Списком — только перечисления; рассуждение пишется абзацами.", "listicle")
    if st["headings"] >= 3 and rh.get("sentences", 0) and rh["sentences"] / st["headings"] < 3:
        add("note", "heading-density", "Заголовок на каждые два предложения", 0,
            f"{st['headings']} заголовков на {rh['sentences']} предложений",
            "Подзаголовки нужны длинному тексту; короткому хватает абзацев.", "heading-density")
    if words >= 100 and st["em_dash_density"] > M.EM_DASH_DENSITY and st["em_dash"] >= 4:
        add("note", "em-dash", "Много тире", 0,
            f"{st['em_dash']} тире, {st['em_dash_density']} на 100 слов",
            "Тире — нормальная пунктуация; проверить только, не заменяет ли оно глагол и связку.",
            "em-dash")
    bold = len(BOLD_RX.findall(prep.original))
    if words >= 200 and bold > words / 200 + 1:
        add("note", "bold", "Много жирного", 0, f"{bold} выделений на {words} слов",
            "Жирный — для одного главного, иначе он перестаёт работать.", "bold")

    # 7. Морфология, если есть pymorphy3.
    morph = M.morphology(prep)
    if morph is None:
        notes.append("pymorphy3 не установлен: сущ./глаг. и цепочки родительных не считались "
                     "(pip install pymorphy3)")
    else:
        for chain in morph["genitive_chains"]:
            add("low", "gen-chain", "Цепочка родительных", 0, chain,
                "Разбить: глагол вместо отглагольного, «который» вместо третьего родительного.",
                "bureau")
        if morph["noun_verb_ratio"] > M.NV_TARGET and morph["verbs"] >= 5:
            add("note", "nominal", "Много существительных", 0,
                f"сущ./глаг. = {morph['noun_verb_ratio']} (цель ≤{M.NV_TARGET}), отглагольных: {morph['nominalizations']}",
                "Текст держится на существительных: вернуть глаголы.", "bureau")

    findings.sort(key=lambda f: (LEVEL_ORDER[f.level], f.line or 10 ** 6, f.code))

    # 8. Оценка.
    score, penalties = _score(findings, words, rh, st)
    metrics = {"rhythm": rh, "structure": st, "morphology": morph}
    return Report(genre=genre, words=prep.words, sentences=rh.get("sentences", 0), score=score,
                  band=_band(score), penalties=penalties, findings=findings, metrics=metrics,
                  muted=sorted(muted), notes=notes)


def _score(findings: list[Finding], words: int, rh: dict, st: dict) -> tuple[int, list[dict]]:
    score = 100.0
    pens: list[dict] = []

    def pen(reason: str, points: float):
        nonlocal score
        points = round(points)
        if points > 0:
            score -= points
            pens.append({"reason": reason, "points": -points})

    n_err = sum(f.count for f in findings if f.level == "error")
    n_high = sum(f.count for f in findings if f.level == "high")
    n_low = sum(f.count for f in findings if f.level == "low" and f.category not in ("rhythm", "wall", "long-sentence"))
    n_note = sum(f.count for f in findings if f.level == "note")
    per100 = lambda n: n / words * 100

    # Штраф считаем в основном по плотности на 100 слов, а не по числу находок:
    # иначе живой лонгрид на 3000 слов с шестью «данный» проигрывал машинному
    # тексту на 300 слов с двумя. Число находок даёт небольшую добавку, чтобы
    # десять канцеляризмов всё же весили больше одного.
    if n_err:
        pen(f"ошибки: {n_err}", min(60, 30 * n_err))
    if n_high:
        pen(f"пустышки и штампы: {n_high} ({per100(n_high):.1f}/100 слов)",
            min(40, 2 * n_high + 10 * per100(n_high)))
    if n_low:
        pen(f"канцелярит и сигналы: {n_low} ({per100(n_low):.1f}/100 слов)",
            min(35, 0.8 * n_low + 12 * per100(n_low)))
    if n_note:
        pen(f"оформление и мелочи: {n_note}", min(8, 0.4 * n_note + per100(n_note)))
    if any(f.code == "rhythm-flat" for f in findings):
        pen(f"ровный ритм (CV={rh['cv']})", min(15, (M.CV_TARGET - rh["cv"]) / M.CV_TARGET * 25))
    long_total = len(rh.get("long", [])) if rh.get("sentences") else 0
    # Штраф только если категория не снята жанром (тогда находок long-sentence нет).
    if long_total and any(f.category == "long-sentence" for f in findings):
        pen(f"длинные предложения: {long_total} из {rh['sentences']}",
            min(10, long_total / rh["sentences"] * 25))
    walls = sum(1 for f in findings if f.code == "wall")
    if walls:
        pen(f"стены текста: {walls}", min(9, 3 * walls))
    final = max(0, min(100, round(score)))
    return final, pens


# ---------------------------------------------------------------------------
# Текстовый отчёт
# ---------------------------------------------------------------------------
def format_report(r: Report, name: str = "-") -> str:
    from .rules import LEVEL_TITLE
    out = []
    out.append(f"humanizer-ru · {name} · жанр: {r.genre} · {r.words} слов, {r.sentences} предложений")
    out.append(f"ОЦЕНКА: {r.score}/100 → {r.band}   "
               f"(≥{BAND_CLEAN} чисто · {BAND_EDIT}–{BAND_CLEAN - 1} точечная правка · <{BAND_EDIT} переписать)")
    for p in r.penalties:
        out.append(f"  {p['points']:>4}  {p['reason']}")
    for level in ("error", "high", "low", "note"):
        items = [f for f in r.findings if f.level == level]
        if not items:
            continue
        out.append("")
        out.append(f"{LEVEL_TITLE[level]} ({sum(f.count for f in items)}):")
        for f in items:
            loc = f"стр. {f.line:<3}" if f.line else "текст  "
            out.append(f"  {loc} [{f.code}] {f.excerpt}")
            out.append(f"           → {f.advice}")
    rh, st = r.metrics["rhythm"], r.metrics["structure"]
    out.append("")
    if rh.get("sentences"):
        out.append(f"Ритм: предложений {rh['sentences']}, средняя {rh['mean_len']} слов "
                   f"(min {rh['min_len']} / max {rh['max_len']}), CV={rh['cv']}, "
                   f"коротких (≤8) {int(rh['short_share'] * 100)}%, вопросов {rh['questions']}")
    out.append(f"Структура: абзацев {st['paragraphs']}, заголовков {st['headings']}, пунктов {st['list_items']}, "
               f"тире {st['em_dash']} ({st['em_dash_density']}/100 слов)")
    morph = r.metrics.get("morphology")
    if morph:
        out.append(f"Морфология: сущ./глаг. = {morph['noun_verb_ratio']}, отглагольных {morph['nominalizations']}")
    if r.muted:
        out.append(f"Снято по жанру «{r.genre}»: {', '.join(r.muted)}")
    for n in r.notes:
        out.append(f"Примечание: {n}")
    if r.errors:
        out.append("")
        out.append("ГЕЙТ НЕ ПРОЙДЕН: есть ошибки — текст не готов.")
    return "\n".join(out)
