from pathlib import Path

import pytest

from loadout.errors import ValidationError
from loadout.frontmatter import is_agent_definition, parse_rule, parse_skill_md


def test_parse_skill_md_returns_validated_skill_metadata() -> None:
    meta = parse_skill_md(
        Path("skills/db-migrations/SKILL.md"),
        """---
name: db-migrations
description: Create and apply database migrations.
allowed-tools: [Bash, Read]
---

# Database migrations
""",
        dir_name="db-migrations",
    )

    assert meta.name == "db-migrations"
    assert meta.description == "Create and apply database migrations."
    assert meta.allowed_tools == ["Bash", "Read"]


def test_parse_skill_md_rejects_unexpected_frontmatter_key() -> None:
    with pytest.raises(ValidationError, match="unknown key"):
        parse_skill_md(
            Path("skills/example/SKILL.md"),
            """---
name: example
description: An example skill.
unknown: value
---
""",
            dir_name="example",
        )


def test_parse_skill_md_rejects_name_different_from_directory() -> None:
    with pytest.raises(ValidationError, match="must equal"):
        parse_skill_md(
            Path("skills/example/SKILL.md"),
            """---
name: another-skill
description: An example skill.
---
""",
            dir_name="example",
        )


def test_parse_skill_md_rejects_description_with_angle_bracket() -> None:
    with pytest.raises(ValidationError, match="must not contain"):
        parse_skill_md(
            Path("skills/example/SKILL.md"),
            """---
name: example
description: Use <dangerous> syntax.
---
""",
            dir_name="example",
        )


def test_is_agent_definition_skips_underscore_prefixed_markdown() -> None:
    assert is_agent_definition(Path("agents/python_coder.md"))
    assert not is_agent_definition(Path("agents/_agent_template.md"))
    assert not is_agent_definition(Path("agents/_notes.txt"))
    assert not is_agent_definition(Path("agents/readme.txt"))


def test_parse_rule_rejects_missing_description() -> None:
    with pytest.raises(ValidationError, match="requires non-empty description"):
        parse_rule(
            Path("rules/example.mdc"),
            """---
globs: ["**/*.py"]
alwaysApply: false
---
""",
        )
