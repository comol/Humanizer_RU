"""Проверки переносимого Agent Skill и установки из GitHub."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "humanizer-ru"
SKILL_FILE = SKILL_DIR / "SKILL.md"
REPOSITORY = "comol/Humanizer_RU"
LINTER_REVISION = "e33188284ddd30b442ac86d91a00a79e3b3f3f2b"
LINTER_SOURCE = f"git+https://github.com/{REPOSITORY}@{LINTER_REVISION}"
INSTALL_COMMAND = (
    f"npx skills add {REPOSITORY} --skill humanizer-ru --global --yes"
)


def _skill_text() -> str:
    return SKILL_FILE.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict[str, Any]:
    assert text.startswith("---\n"), "SKILL.md: нет начального frontmatter"
    separator = "\n---\n"
    assert separator in text[4:], "SKILL.md: frontmatter не закрыт"
    raw, body = text[4:].split(separator, 1)
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise AssertionError("SKILL.md: frontmatter содержит некорректный YAML") from exc
    assert isinstance(parsed, dict), "SKILL.md: frontmatter должен быть YAML mapping"
    assert body.strip(), "SKILL.md: после frontmatter нет инструкций"
    return parsed


def test_frontmatter_rejects_an_unterminated_yaml_block() -> None:
    malformed = "---\nname: humanizer-ru\ndescription: test\n# body without closing delimiter"

    with pytest.raises(AssertionError, match="frontmatter не закрыт"):
        _frontmatter(malformed)


def test_skill_has_portable_agent_skills_metadata() -> None:
    frontmatter = _frontmatter(_skill_text())

    assert frontmatter["name"] == "humanizer-ru"
    assert isinstance(frontmatter["description"], str) and frontmatter["description"]
    assert frontmatter["license"] == "MIT"
    assert isinstance(frontmatter["compatibility"], str) and frontmatter["compatibility"]
    assert frontmatter["metadata"]["repository"] == "https://github.com/comol/Humanizer_RU"


def test_skill_description_is_compact_but_keeps_russian_triggers() -> None:
    frontmatter = _frontmatter(_skill_text())
    description = frontmatter["description"]

    assert len(description) <= 400
    for trigger in ("очеловечь", "убери канцелярит", "проверь на слоп"):
        assert trigger in description


def test_standalone_skill_carries_its_license_notices() -> None:
    required = (ROOT / "LICENSE", SKILL_DIR / "LICENSE", SKILL_DIR / "THIRD_PARTY_NOTICES.md")
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"Не хватает файлов лицензий: {missing}"

    assert "MIT License" in (SKILL_DIR / "LICENSE").read_text(encoding="utf-8")
    notices = (SKILL_DIR / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    root_notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert notices == root_notices, "Standalone skill должен нести те же уведомления, что репозиторий"
    for source in ("smixs/humanizer-ru", "Vladimir-Human/humanizer-ru", "ilyautov/humanizer-ru", "beaverbeard/chukovsky"):
        assert source in notices
    assert "общий полный текст MIT" in notices
    assert "Permission is hereby granted" in notices
    assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in notices
    assert "тот же, что выше" not in notices


def test_readme_gives_an_agent_one_canonical_github_install_command() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Установи skill по ссылке" in readme
    assert "https://github.com/comol/Humanizer_RU" in readme
    assert INSTALL_COMMAND in readme
    assert readme.count(INSTALL_COMMAND) == 1


def test_readme_is_agent_neutral_instead_of_claude_only() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Claude Code — скопировать папку" not in readme
    assert "Copy-Item -Recurse skills\\humanizer-ru" not in readme
    for agent in ("Claude Code", "Codex", "Cursor", "Gemini CLI"):
        assert agent in readme


def test_installed_skill_does_not_assume_a_repository_checkout() -> None:
    text = _skill_text()

    assert "Пакет лежит в корне репозитория" not in text
    assert "pip install -e ." not in text
    command = re.search(
        r"uvx --from (git\+https://github\.com/comol/Humanizer_RU@([0-9a-f]{40})) ",
        text,
    )
    assert command, "Необязательный линтер должен быть закреплён на commit SHA"
    assert command.group(1) == LINTER_SOURCE
    assert command.group(2) == LINTER_REVISION


def test_every_documented_skill_resource_is_inside_the_package() -> None:
    resources = (
        "knowledge/corrections.md",
        "knowledge/voice-author.md",
        "references/patterns.md",
        "references/false-positives.md",
        "references/terms-it-1c.md",
        "references/voice.md",
    )

    missing = [relative for relative in resources if not (SKILL_DIR / relative).is_file()]
    assert not missing, f"В skill-пакете не хватает файлов: {missing}"
