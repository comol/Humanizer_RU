"""Публичный API пакета.

    from humanizer_ru import lint_text, analyze_text

lint_text(text, genre) -> Report (объект с находками, метриками и оценкой).
analyze_text(text, genre, mode) -> dict, пригодный для JSON; в режиме «deep»
дополняется редакторским чек-листом для человека или LLM.
"""

from __future__ import annotations

from typing import Any

from .linter import Report, lint

EDITORIAL_CHECKS_CAREFUL = [
    "Сверить числа, имена, даты, ссылки и цитаты с исходником: ничего нового не появилось.",
    "Не менять степень уверенности утверждений без источника.",
    "Термины ИТ и 1С оставить как есть, даже если они похожи на канцелярит.",
    "Прочитать результат вслух: где сбивается дыхание — там точка.",
]
EDITORIAL_CHECKS_DEEP = [
    "Разбить абзацы, которые одновременно вводят тему, объясняют её и подводят итог.",
    "Заменить общие оценки наблюдением, примером или числом из исходника — либо удалить.",
    "Проверить, что каждый абзац цепляется за предыдущий, а не начинается с чистого листа.",
    "Вкусовые правки (ритм, синонимы, разговорность) вынести в список «на решение автора».",
]


def lint_text(text: str, genre: str = "auto") -> Report:
    return lint(text, genre)


def analyze_text(text: str, genre: str = "auto", mode: str = "careful") -> dict[str, Any]:
    if mode not in {"careful", "deep"}:
        raise ValueError("mode must be 'careful' or 'deep'")
    report = lint(text, genre)
    data = report.to_dict()
    data["mode"] = mode
    data["editorial_checks"] = EDITORIAL_CHECKS_CAREFUL + (EDITORIAL_CHECKS_DEEP if mode == "deep" else [])
    data["manual_review_required"] = report.score < 85 or bool(report.errors)
    return data
