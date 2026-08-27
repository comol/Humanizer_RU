"""Подготовка текста к проверке.

Что делаем:
- снимаем YAML-frontmatter, блоки кода, инлайн-код и ссылки (это не проза);
- классифицируем строки: проза, заголовок, ярлык («Задача 2:», «Итого»),
  пункт списка, таблица, цитата, реплика диалога, разделитель;
- режем прозу на предложения без внешних зависимостей (razdel не тянем:
  для метрик ритма хватает аккуратного регэкспа с защитой сокращений).

Ярлык — короткая строка без точки в конце, которой автор размечает текст
вместо markdown-заголовка (так выглядит экспорт с Хабра или из CMS). В абзацы и
ритм она не входит, иначе три ярлыка подряд линтер примет за парцелляцию.

Перевод строки внутри абзаца считаем границей предложения, если строка не
оборвана на запятой и следующая начинается с заглавной: в экспорте из CMS
каждый абзац — строка, часто без точки в конце. Переносы по ширине
(hard wrap) обычно продолжаются строчной буквой и не рвутся.

Экспорт с Хабра, из Confluence или Word часто вообще не ставит пустых строк
между абзацами: каждая строка — абзац на 30–100 слов. Если медианная строка
прозы длиннее PARAGRAPH_LINE_WORDS слов, считаем каждую строку абзацем,
иначе десять абзацев подряд склеятся в одну «стену текста». Переносы по
ширине (10–13 слов в строке) под этот порог не попадают.

Номера строк сохраняются: всё, что вырезаем, заменяем пробелами или переводами
строк той же длины, чтобы находки указывали на реальную строку файла.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CODE_BLOCK = re.compile(r"```.*?(?:```|\Z)", re.S)
INLINE_CODE = re.compile(r"`[^`\n]+`")
URL = re.compile(r"(?:https?://|www\.)\S+")
FRONTMATTER = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*\n", re.S)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+•]|\d{1,3}[.)])\s+(.*)$")
TABLE_ROW = re.compile(r"^\s*\|")
BLOCKQUOTE = re.compile(r"^\s*>")
HR = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
DIALOGUE = re.compile(r"^\s*[«\"]?\s*[—–]\s")
MD_BOLD = re.compile(r"\*\*|__")
WORD = re.compile(r"[А-Яа-яЁёA-Za-z0-9]+(?:[-'’][А-Яа-яЁёA-Za-z0-9]+)*")
LABEL_MAX_WORDS = 4
PARAGRAPH_LINE_WORDS = 20
_LABEL_START = re.compile(r"^\s*[«\"(\[]?[А-ЯЁA-Z0-9]")
_LABEL_END = re.compile(r"[.!?…,;—–-]\s*$")

# Сокращения, после которых точка не конец предложения.
_ABBR = re.compile(
    r"\b(?:т\.\s?е|т\.\s?д|т\.\s?п|т\.\s?к|т\.\s?н|руб|коп|тыс|млн|млрд|стр|рис|табл|"
    r"см|ср|напр|др|пр|гг|г|ул|кв|им|проф|акад|изд|ред|ч|п|пп|ст|абз|англ|лат|прим|"
    r"тел|ок|обл|пос|св|шт|ед|мин|сек|доп|рег|орг|отв|кол-во|т\.\s?ч)\.",
    re.I,
)
_SENT_SPLIT = re.compile(
    r"(?<=[.!?…])\s+(?=[^\sa-zа-яё])"                # обычная граница; «4-ку... не разобрался» — пауза, не точка
    r"|(?<![,;—–(\-\s])\n(?=\s*[А-ЯЁA-Z0-9«\"(\[])"  # конец строки без точки + заглавная
)
_DOT = ""


def _blank_keep_lines(m: re.Match) -> str:
    return "\n" * m.group(0).count("\n")


def strip_frontmatter(text: str) -> str:
    m = FRONTMATTER.match(text)
    if not m:
        return text
    return "\n" * m.group(0).count("\n") + text[m.end():]


def split_sentences(paragraph: str) -> list[str]:
    """Режет абзац на предложения, не ломая сокращения, версии 8.3.24 и инициалы."""
    s = _ABBR.sub(lambda m: m.group(0)[:-1] + _DOT, paragraph)
    s = re.sub(r"(?<=\d)\.(?=\d)", _DOT, s)
    s = re.sub(r"(?<![А-ЯЁA-Zа-яёa-z])([А-ЯЁA-Z])\.(?=\s?[А-ЯЁA-Z][а-яёa-z.])", r"\1" + _DOT, s)
    parts = _SENT_SPLIT.split(s)
    return [re.sub(r"\s*\n\s*", " ", p.replace(_DOT, ".")).strip() for p in parts if p.strip()]


def word_count(s: str) -> int:
    return len(WORD.findall(s))


@dataclass
class Line:
    no: int
    raw: str    # без кода, но со ссылками (нужно артефактам вроде utm_source)
    text: str   # то, что проверяем правилами стиля; "" — строку не проверяем
    kind: str   # prose | heading | label | list | table | quote | hr | blank


@dataclass
class Prepared:
    lines: list[Line]
    paragraphs: list[str]            # прозаические абзацы (для ритма)
    paragraph_lines: list[int]       # номер первой строки каждого абзаца
    sentences: list[str]
    sentence_words: list[int]
    words: int
    headings: int
    list_items: int
    prose_text: str                  # вся проза и списки одной строкой (плотности)
    original: str = field(repr=False, default="")


def classify(line: str) -> tuple[str, str]:
    if not line.strip():
        return "blank", ""
    if HR.match(line):
        return "hr", ""
    if TABLE_ROW.match(line):
        return "table", ""
    if BLOCKQUOTE.match(line) or DIALOGUE.match(line):
        return "quote", ""
    m = HEADING.match(line)
    if m:
        return "heading", MD_BOLD.sub("", m.group(1))
    m = LIST_ITEM.match(line)
    if m:
        return "list", MD_BOLD.sub("", m.group(1))
    body = MD_BOLD.sub("", line)
    if is_label(body):
        return "label", body
    return "prose", body


def is_label(line: str) -> bool:
    """«Задача 2:», «Итого», «Cursor» — строка-ярлык вместо заголовка."""
    if not _LABEL_START.match(line) or _LABEL_END.search(line):
        return False
    return 0 < len(WORD.findall(line)) <= LABEL_MAX_WORDS


def _lines_are_paragraphs(lines: list[Line]) -> bool:
    """Экспорт без пустых строк: медианная строка прозы длиннее, чем бывает при переносе по ширине."""
    counts = sorted(word_count(ln.text) for ln in lines if ln.kind == "prose")
    if len(counts) < 3:
        return False
    return counts[len(counts) // 2] >= PARAGRAPH_LINE_WORDS


def prepare(text: str) -> Prepared:
    original = text
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    text = strip_frontmatter(text)
    raw = CODE_BLOCK.sub(_blank_keep_lines, text)
    raw = INLINE_CODE.sub(lambda m: " " * len(m.group(0)), raw)
    clean = URL.sub(lambda m: " " * len(m.group(0)), raw)

    lines: list[Line] = []
    for no, (r, c) in enumerate(zip(raw.split("\n"), clean.split("\n")), start=1):
        kind, body = classify(c)
        lines.append(Line(no=no, raw=r, text=body, kind=kind))

    paragraphs: list[str] = []
    paragraph_lines: list[int] = []
    buf: list[str] = []
    buf_start = 0
    line_is_paragraph = _lines_are_paragraphs(lines)
    for ln in lines:
        if ln.kind == "prose":
            if buf and line_is_paragraph:
                paragraphs.append("\n".join(buf))
                paragraph_lines.append(buf_start)
                buf = []
            if not buf:
                buf_start = ln.no
            buf.append(ln.text.strip())
        else:
            if buf:
                paragraphs.append("\n".join(buf))
                paragraph_lines.append(buf_start)
                buf = []
    if buf:
        paragraphs.append("\n".join(buf))
        paragraph_lines.append(buf_start)

    sentences: list[str] = []
    for p in paragraphs:
        sentences.extend(split_sentences(p))
    sentence_words = [word_count(s) for s in sentences]
    # Пустые «предложения» из одних знаков не считаем.
    pairs = [(s, n) for s, n in zip(sentences, sentence_words) if n > 0]
    sentences = [s for s, _ in pairs]
    sentence_words = [n for _, n in pairs]

    prose_parts = [ln.text for ln in lines if ln.kind in ("prose", "list", "heading", "label")]
    prose_text = "\n".join(prose_parts)
    words = word_count(prose_text)

    return Prepared(
        lines=lines,
        paragraphs=paragraphs,
        paragraph_lines=paragraph_lines,
        sentences=sentences,
        sentence_words=sentence_words,
        words=words,
        headings=sum(1 for ln in lines if ln.kind == "heading"),
        list_items=sum(1 for ln in lines if ln.kind == "list"),
        prose_text=prose_text,
        original=original,
    )
