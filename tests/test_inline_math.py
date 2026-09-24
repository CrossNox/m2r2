"""Check inline math syntax selection and delimiter boundaries."""

import pytest
from docutils import nodes
from docutils.core import publish_doctree

from m2r2 import M2R2, convert


def parse_converted_markdown(source, inline_math):
    return publish_doctree(
        convert(source, inline_math=inline_math),
        settings_overrides={"halt_level": 2},
    )


@pytest.mark.parametrize(
    ("mode", "source", "expected_math", "expected_code"),
    [
        ("legacy", "`$x$`", ["x"], []),
        ("legacy", "$x$", [], []),
        ("legacy", "$`x`$", [], ["x"]),
        ("dollar", "`$x$`", [], ["$x$"]),
        ("dollar", "$x$", ["x"], []),
        ("dollar", "$`x`$", ["x"], []),
        (None, "`$x$` $x$ $`x`$", [], ["$x$", "x"]),
    ],
)
def test_select_inline_math_syntax(mode, source, expected_math, expected_code):
    document = parse_converted_markdown(source, mode)
    assert [node.astext() for node in document.findall(nodes.math)] == expected_math
    assert [node.astext() for node in document.findall(nodes.literal)] == expected_code


def test_legacy_math_does_not_cross_code_spans():
    source = r"`$x$` and `$5-$10` and `$20,000 and $30,000` and `\$`"
    document = parse_converted_markdown(source, "legacy")

    assert [node.astext() for node in document.findall(nodes.math)] == ["x"]
    assert [node.astext() for node in document.findall(nodes.literal)] == [
        "$5-$10",
        "$20,000 and $30,000",
        r"\$",
    ]


@pytest.mark.parametrize("value", ["none", "unknown", True, False])
def test_reject_invalid_inline_math_option(value):
    with pytest.raises(ValueError, match="inline_math"):
        M2R2(inline_math=value)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("$x$ and $y^2$", ["x", "y^2"]),
        ("$`x`$ and $`y^2`$", ["x", "y^2"]),
        (r"$\alpha + \$5$", [r"\alpha + \$5"]),
        (r"$`\alpha + \$5`$", [r"\alpha + \$5"]),
        ("$` x + y `$", ["x + y"]),
        ("before$x$after", ["x"]),
        ("($x$), $y$.", ["x", "y"]),
        ("**value $x$**", ["x"]),
        ("[value $x$](https://example.org)", ["x"]),
    ],
)
def test_parse_dollar_math_without_losing_content(source, expected):
    document = parse_converted_markdown(source, "dollar")
    paragraph = next(document.findall(nodes.paragraph))
    assert [node.astext() for node in paragraph.findall(nodes.math)] == expected


@pytest.mark.parametrize(
    "source",
    [
        "$5-$10",
        "$20,000 and $30,000",
        r"\$x\$",
        "$ x$",
        "$x $",
        "$x$2",
        "$",
        "$$",
        "$$x$$",
        "$` `$",
        "$x",
        "$x\ny$",
        "`$x$`",
        "``$`x`$``",
        "```text\n$x$\n```",
    ],
)
def test_leave_non_math_dollar_content_as_text_or_code(source):
    document = parse_converted_markdown(source, "dollar")
    assert list(document.findall(nodes.math)) == []


def test_keep_block_math_when_inline_math_is_disabled():
    document = parse_converted_markdown("```math\nx^2\n```", None)
    assert next(document.findall(nodes.math_block)).astext() == "x^2"


def test_empty_quoted_math_preserves_its_code_space():
    document = parse_converted_markdown("$` `$", "dollar")
    paragraph = next(document.findall(nodes.paragraph))
    assert next(paragraph.findall(nodes.raw)).astext() == "<code> </code>"
    assert [
        node.astext() for node in paragraph.children if isinstance(node, nodes.Text)
    ] == ["$", "$"]


@pytest.mark.parametrize(
    ("source", "expected"),
    [("$5-$10", "$5-$10"), (r"\$x\$", "$x$"), ("$20 and $30", "$20 and $30")],
)
def test_preserve_currency_and_escaped_dollars(source, expected):
    document = parse_converted_markdown(source, "dollar")
    assert next(document.findall(nodes.paragraph)).astext() == expected
