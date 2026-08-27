"""Командная строка.

    humanizer-ru lint файл.txt [--genre doc] [--json] [--fail-below 60]
    humanizer-ru analyze файл.txt [--mode deep]      # JSON с чек-листом
    humanizer-ru brief файл.txt [--voice голос.md] [--output prompt.md]  # промпт для любой LLM
    humanizer-ru selftest
    humanizer-ru genres

Вместо файла можно передать «-» — текст читается из stdin.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__
from .brief import build_brief
from .core import analyze_text
from .linter import format_report, lint
from .rules import GENRE_HELP, GENRES


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def _read(src: str) -> str:
    if src == "-":
        return sys.stdin.read()
    try:
        return Path(src).read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.exit(f"[ошибка] файл не найден: {src}")
    except UnicodeDecodeError:
        return Path(src).read_text(encoding="cp1251")


FIRST_BLOCK_SEP = re.compile(r"^\s*-{3,}\s*$", re.M)


def _first_block(text: str) -> str:
    """Текст до первого разделителя «---»: чистовик без резюме «что изменено»."""
    m = FIRST_BLOCK_SEP.search(text)
    return text[:m.start()] if m else text


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("input", help="файл с текстом или «-» для stdin")
    p.add_argument("--genre", choices=GENRES, default="auto",
                   help="жанр: снимает правила, которые для него не дефект (см. genres)")
    p.add_argument("--first-block", action="store_true",
                   help="проверять только текст до первого «---» (чистовик без резюме правок)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="humanizer-ru",
                                     description="Линтер читаемости русского текста после нейросети.")
    parser.add_argument("--version", action="version", version=f"humanizer-ru {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("lint", help="проверить текст, показать находки и оценку")
    _add_common(p)
    p.add_argument("--json", action="store_true", help="машинный вывод")
    p.add_argument("--fail-below", type=int, default=0, metavar="N",
                   help="код возврата 1, если оценка ниже N (0 — только по ошибкам)")

    p = sub.add_parser("analyze", help="JSON-отчёт с редакторским чек-листом")
    _add_common(p)
    p.add_argument("--mode", choices=("careful", "deep"), default="careful")

    p = sub.add_parser("brief", help="собрать промпт для LLM: инструкция + находки + текст")
    _add_common(p)
    p.add_argument("--mode", choices=("careful", "deep"), default="careful")
    p.add_argument("--voice", type=Path, metavar="FILE",
                   help="файл с паспортом голоса автора (например, skills/humanizer-ru/knowledge/voice-author.md)")
    p.add_argument("--output", type=Path, help="куда сохранить промпт (по умолчанию — stdout)")

    sub.add_parser("selftest", help="проверить правила на встроенных примерах")
    sub.add_parser("genres", help="список жанров и что они снимают")
    return parser


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    args = build_parser().parse_args(argv)

    if args.command == "genres":
        from .rules import GENRE_MUTE
        for g in GENRES:
            muted = ", ".join(sorted(GENRE_MUTE.get(g, ()))) or "—"
            print(f"{g:<9} {GENRE_HELP[g]}\n          снимает: {muted}")
        return 0

    if args.command == "selftest":
        from .selftest import run
        return run()

    text = _read(args.input)
    if getattr(args, "first_block", False):
        text = _first_block(text)
    name = args.input if args.input != "-" else "stdin"

    if args.command == "lint":
        report = lint(text, args.genre)
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(format_report(report, name))
        if report.errors:
            return 1
        if args.fail_below and report.score < args.fail_below:
            return 1
        return 0

    if args.command == "analyze":
        print(json.dumps(analyze_text(text, args.genre, args.mode), ensure_ascii=False, indent=2))
        return 0

    if args.command == "brief":
        report = lint(text, args.genre)
        voice = None
        if args.voice:
            try:
                voice = args.voice.read_text(encoding="utf-8")
            except FileNotFoundError:
                sys.exit(f"[ошибка] файл голоса не найден: {args.voice}")
        brief = build_brief(text, report, args.mode, voice)
        if args.output:
            args.output.write_text(brief, encoding="utf-8")
            print(f"промпт записан: {args.output} ({len(brief)} символов)")
        else:
            print(brief)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
