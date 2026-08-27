"""pytest-обёртка над тем же корпусом, что и run_tests.py."""

import json
from pathlib import Path

import pytest

from humanizer_ru import analyze_text, lint_text
from humanizer_ru.brief import build_brief
from humanizer_ru.selftest import run as selftest

FIXTURES = Path(__file__).parent / "fixtures"
EVALS = json.loads((FIXTURES / "evals.json").read_text(encoding="utf-8"))


def test_selftest():
    assert selftest() == 0


@pytest.mark.parametrize("case", EVALS["cases"], ids=[c["id"] for c in EVALS["cases"]])
def test_case(case):
    codes = {f.code for f in lint_text(case["text"], case.get("genre", "auto")).findings}
    for c in case.get("must", []):
        assert c in codes, (case["id"], sorted(codes))
    for c in case.get("must_not", []):
        assert c not in codes, (case["id"], sorted(codes))


@pytest.mark.parametrize("item", EVALS["corpus"], ids=[c["file"] for c in EVALS["corpus"]])
def test_corpus(item):
    text = (FIXTURES / item["file"]).read_text(encoding="utf-8")
    r = lint_text(text, item.get("genre", "auto"))
    if item["kind"] == "human":
        assert not r.errors, [f.code for f in r.errors]
        assert r.score >= item.get("min_score", 85), [f.code for f in r.findings]
    else:
        assert r.score <= item.get("max_score", 59)
        if item.get("errors_min"):
            assert len(r.errors) >= item["errors_min"]


@pytest.mark.skipif(not __import__("humanizer_ru.metrics", fromlist=["morphology_available"]).morphology_available(),
                    reason="pymorphy3 не установлен")
def test_genitive_chain_with_pymorphy():
    r = lint_text("Порядок формирования проводок документов реализации товаров подразделений компании.")
    assert "gen-chain" in {f.code for f in r.findings}, [f.code for f in r.findings]
    ok = lint_text("Обработка проведения формирует движения по регистру накопления.")
    assert "gen-chain" not in {f.code for f in ok.findings}


def test_analyze_keeps_numbers_and_checklist():
    data = analyze_text("Сервис обработал 218 файлов за 43 секунды.", mode="deep")
    assert data["score"] >= 85
    assert any("218" not in c for c in data["editorial_checks"])
    assert len(data["editorial_checks"]) > 4


def test_brief_contains_text_and_findings():
    text = "В современном мире данный отчёт играет ключевую роль."
    r = lint_text(text)
    brief = build_brief(text, r)
    assert text in brief
    assert "intro-empty" in brief or "Пустой зачин" in brief or "high" in brief
