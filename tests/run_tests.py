"""Регрессионный прогон без зависимостей: python tests/run_tests.py

1. Встроенная самопроверка правил (humanizer_ru.selftest).
2. cases из tests/fixtures/evals.json: фраза → обязательные и запрещённые коды.
3. corpus: живые тексты обязаны получать ≥ min_score без ошибок,
   тексты нейросети — ≤ max_score.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from humanizer_ru.linter import lint  # noqa: E402
from humanizer_ru.selftest import run as selftest  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def load_evals() -> dict:
    return json.loads((FIXTURES / "evals.json").read_text(encoding="utf-8"))


def check_case(case: dict) -> list[str]:
    codes = {f.code for f in lint(case["text"], case.get("genre", "auto")).findings}
    problems = []
    for c in case.get("must", []):
        if c not in codes:
            problems.append(f"[{case['id']}] ожидался {c}, получено {sorted(codes)}")
    for c in case.get("must_not", []):
        if c in codes:
            problems.append(f"[{case['id']}] лишний {c}")
    return problems


def check_corpus(item: dict) -> tuple[list[str], str]:
    text = (FIXTURES / item["file"]).read_text(encoding="utf-8")
    r = lint(text, item.get("genre", "auto"))
    problems = []
    if item["kind"] == "human":
        if r.errors:
            problems.append(f"[{item['file']}] ошибки на живом тексте: {[f.code for f in r.errors]}")
        if r.score < item.get("min_score", 85):
            problems.append(f"[{item['file']}] живой текст получил {r.score} < {item.get('min_score', 85)}: "
                            + ", ".join(f"{f.code}" for f in r.findings if f.level in ("high", "low")))
    else:
        if r.score > item.get("max_score", 59):
            problems.append(f"[{item['file']}] текст нейросети получил {r.score} > {item.get('max_score', 59)}")
        if item.get("errors_min") and len(r.errors) < item["errors_min"]:
            problems.append(f"[{item['file']}] ожидались ошибки, найдено {len(r.errors)}")
    summary = f"  {r.score:>3}/100 {r.band:<16} {item['kind']:<5} {item['file']}"
    return problems, summary


def main() -> int:
    failures: list[str] = []
    print("== selftest ==")
    if selftest() != 0:
        failures.append("selftest")

    data = load_evals()
    print(f"\n== cases: {len(data['cases'])} ==")
    for case in data["cases"]:
        failures.extend(check_case(case))

    print(f"\n== corpus: {len(data['corpus'])} ==")
    for item in data["corpus"]:
        problems, summary = check_corpus(item)
        print(summary)
        failures.extend(problems)

    print()
    if failures:
        for f in failures:
            print("FAIL", f)
        print(f"\n{len(failures)} провал(ов)")
        return 1
    print(f"OK: selftest, {len(data['cases'])} cases, {len(data['corpus'])} текстов корпуса")
    return 0


if __name__ == "__main__":
    sys.exit(main())
