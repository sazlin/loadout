import pytest

from loadout.blocks import (
    AGENT_RULES_BEGIN,
    AGENT_RULES_END,
    RuleIndexRow,
    render_agent_rules_block,
    render_claude_import_block,
    splice_block,
)
from loadout.errors import ValidationError


def test_render_agent_rules_block_orders_always_rules_before_paths() -> None:
    block = render_agent_rules_block(
        [
            RuleIndexRow(
                path="infra/.cursor/rules/aws.mdc",
                scope="`infra/**/*.tf`",
                description="AWS conventions.",
            ),
            RuleIndexRow(
                path=".cursor/rules/commit.mdc",
                scope="Always",
                description="Commit conventions.",
            ),
            RuleIndexRow(
                path=".cursor/rules/python.mdc",
                scope="`**/*.py`",
                description="Python conventions.",
            ),
        ]
    )

    assert block is not None
    assert block.index("`.cursor/rules/commit.mdc`") < block.index("`.cursor/rules/python.mdc`")
    assert block.index("`.cursor/rules/python.mdc`") < block.index("`infra/.cursor/rules/aws.mdc`")
    assert "| Rule | Scope | What it covers |" in block
    assert "Managed by [loadout](https://github.com/sazlin/loadout)." in block


def test_render_agent_rules_block_returns_none_for_no_rules() -> None:
    assert render_agent_rules_block([]) is None


def test_splice_block_replaces_only_marked_span() -> None:
    old_block = f"{AGENT_RULES_BEGIN}\nold generated content\n{AGENT_RULES_END}"
    new_block = f"{AGENT_RULES_BEGIN}\nnew generated content\n{AGENT_RULES_END}"
    text = f"# Hand-owned heading\n\n{old_block}\n\nHand-owned footer.\n"

    result = splice_block(text, AGENT_RULES_BEGIN, AGENT_RULES_END, new_block)

    assert result == f"# Hand-owned heading\n\n{new_block}\n\nHand-owned footer.\n"


def test_splice_block_removes_existing_marked_block() -> None:
    block = f"{AGENT_RULES_BEGIN}\ngenerated\n{AGENT_RULES_END}"

    assert splice_block(f"before\n{block}\nafter\n", AGENT_RULES_BEGIN, AGENT_RULES_END, None) == "before\n\nafter\n"


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (f"before\n{AGENT_RULES_BEGIN}\n", "exactly one"),
        (f"before\n{AGENT_RULES_END}\n", "exactly one"),
        (f"{AGENT_RULES_END}\nbody\n{AGENT_RULES_BEGIN}", "precedes"),
    ],
)
def test_splice_block_rejects_mangled_markers(text: str, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        splice_block(text, AGENT_RULES_BEGIN, AGENT_RULES_END, "replacement")


def test_splice_block_appends_absent_block_by_default() -> None:
    assert splice_block("Hand-owned text.", AGENT_RULES_BEGIN, AGENT_RULES_END, "block") == "Hand-owned text.\n\nblock"


def test_splice_block_prepends_absent_block_when_requested() -> None:
    assert (
        splice_block(
            "Claude-specific instructions.\n",
            AGENT_RULES_BEGIN,
            AGENT_RULES_END,
            "block",
            placement="prepend",
        )
        == "block\n\nClaude-specific instructions.\n"
    )


def test_render_claude_import_block_contains_markers_and_agents_import() -> None:
    assert (
        render_claude_import_block()
        == """<!-- BEGIN LOADOUT: agents-import (generated, do not edit) -->
@AGENTS.md
<!-- END LOADOUT: agents-import -->"""
    )
