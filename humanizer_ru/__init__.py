"""Humanizer RU — линтер читаемости русского текста после нейросети.

Публичный API: lint_text (объект-отчёт), analyze_text (dict для JSON).
"""

__version__ = "0.3.0"

from .core import analyze_text, lint_text  # noqa: E402,F401
from .linter import Finding, Report, format_report, lint  # noqa: E402,F401

__all__ = ["analyze_text", "lint_text", "lint", "format_report", "Report", "Finding", "__version__"]
