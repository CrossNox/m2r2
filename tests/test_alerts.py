"""Check GitHub alerts and their RST admonition bodies."""

import pytest
from docutils import nodes
from docutils.core import publish_doctree

from m2r2 import convert


def parse_converted_alerts(source):
    return publish_doctree(convert(source), settings_overrides={"halt_level": 2})


@pytest.mark.parametrize("kind", ["NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"])
def test_convert_alert_to_matching_admonition(kind):
    source = f"> [!{kind}]\n> Some message"
    assert convert(source) == f"\n.. {kind.lower()}::\n\n   Some message\n\n"
    document = parse_converted_alerts(source)
    admonition = next(document.findall(nodes.Admonition))
    assert admonition.tagname == kind.lower()
    assert admonition.astext() == "Some message"
    assert list(document.findall(nodes.block_quote)) == []


def test_preserve_alert_body_markdown_and_document_boundaries():
    document = parse_converted_alerts(
        "Before.\n\n"
        "> [!WARNING]\n"
        "> **Back up** your `files`. See [help](https://example.org).\n"
        ">\n"
        "> Another paragraph.\n"
        ">\n"
        "> - First step\n"
        "> - Second step\n"
        ">\n"
        "> ```text\n"
        "> [!NOTE]\n"
        "> ```\n\n"
        "After."
    )
    assert [node.tagname for node in document.children] == [
        "paragraph",
        "warning",
        "paragraph",
    ]
    warning = document[1]
    assert next(warning.findall(nodes.strong)).astext() == "Back up"
    assert next(warning.findall(nodes.literal)).astext() == "files"
    assert next(warning.findall(nodes.reference))["refuri"] == "https://example.org"
    assert len(list(warning.findall(nodes.list_item))) == 2
    assert next(warning.findall(nodes.literal_block)).astext() == "[!NOTE]"
    assert document[-1].astext() == "After."


@pytest.mark.parametrize(
    "source",
    [
        "> [!UNKNOWN]\n> Text",
        "> [!WARNING] Same line",
        "> \\[!WARNING]\n> Text",
        "> `[!WARNING]`\n> Text",
        ">     [!WARNING]\n>     Text",
        "> A quote\n> [!WARNING]\n> Text",
        ">\n> [!WARNING]\n> Text",
        "> > [!WARNING]\n> > Text",
        "- Item\n\n  > [!WARNING]\n  > Text",
        "> :warning: Text",
        "```markdown\n> [!WARNING]\n> Text\n```",
        "    > [!WARNING]\n    > Text",
    ],
)
def test_leave_other_quotes_and_code_without_admonitions(source):
    document = parse_converted_alerts(source)
    assert list(document.findall(nodes.Admonition)) == []


@pytest.mark.parametrize("following", ["- Outside", "```text\nOutside\n```"])
def test_end_alert_before_following_block(following):
    document = parse_converted_alerts(f"> [!NOTE]\n> Inside\n{following}")
    assert len(document.children) == 2
    assert isinstance(document[0], nodes.note)
    assert document[0].astext() == "Inside"
    assert not isinstance(document[1], nodes.Admonition)


def test_keep_separate_alerts_separate():
    document = parse_converted_alerts("> [!NOTE]\n> First\n\n> [!TIP]\n> Second")
    assert [node.tagname for node in document.children] == ["note", "tip"]


def test_keep_nested_alert_marker_as_an_ordinary_quote():
    document = parse_converted_alerts(
        "> [!NOTE]\n> Outer\n>\n> > [!WARNING]\n> > Inner"
    )
    assert len(list(document.findall(nodes.Admonition))) == 1
    assert next(document.findall(nodes.block_quote)).astext() == "[!WARNING]\nInner"


def test_keep_transition_outside_alert():
    document = parse_converted_alerts("> [!NOTE]\n> Inside\n---\n\nOutside")
    assert [node.tagname for node in document.children] == [
        "note",
        "transition",
        "paragraph",
    ]


def test_parse_list_immediately_after_alert_marker():
    document = parse_converted_alerts("> [!TIP]\n> - First\n> - Second")
    tip = next(document.findall(nodes.tip))
    assert isinstance(tip[0], nodes.bullet_list)
    assert [node.astext() for node in tip.findall(nodes.list_item)] == [
        "First",
        "Second",
    ]


def test_convert_empty_alert_without_invalid_rst():
    document = parse_converted_alerts("> [!NOTE]")
    assert isinstance(document[0], nodes.note)
    assert document[0].astext() == ""
