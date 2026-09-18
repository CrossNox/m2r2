from __future__ import annotations

import re
from re import Match
from typing import Any

from mistune import BlockParser
from mistune.core import BlockState, InlineState

# Multiline directive: starts with .., continues with indented lines
# Blank lines within indented content are part of the directive
# The directive ends when we hit a non-indented, non-blank line
DIRECTIVE_PATTERN = (
    r"^(?P<directive_multiline>"
    r" *\.\..*\n"
    r"(?:"
    r"(?:[ \t]+.*\n)"
    r"|"
    r"(?:[ \t]*\n(?=[ \t\n]*[ \t]))"  # Blank line(s) only if eventually followed by indented line
    r")*"
    r"(?:[ \t]*\n(?=[ \t]*$|[ \t]*\n*$))?"  # Trailing blank line only if at end of input
    r")"
)

ONELINE_DIRECTIVE_PATTERN = r"^(?P<directive_oneline> *\.\.[^\n]*)$"
RST_LITERAL_BLOCK_MARKER_PATTERN = r"^(?P<code_block>::\s*)$"

VISUAL_LIST_PATTERN = (
    r"^(?P<visual_list_spaces> *)"
    r"(?P<visual_list_marker>[*+\-]|\d{1,9}[.)])"
    r"(?P<visual_list_content>[ \t]*|[ \t].+)$"
)

REST_ROLE_PATTERN = r":.*?:`.*?`|`[^`]+`:.*?:"
REST_LINK_PATTERN = r"`[^`]*?`_"
RST_FOOTNOTE_REF_PATTERN = r"\[[#][^\]]+\]_"
INLINE_MATH_PATTERN = r"`\$(?P<math>.*?)\$`"
EOL_LITERAL_MARKER_PATTERN = r"(?P<spaces>\s+)?::\s*$"


def parse_directive(block, match: Match[str], state: BlockState):
    """Preserve an RST directive."""
    text = match.group("directive_multiline")
    # Use "raw" to bypass Mistune's inline parser.
    token = {"type": "directive", "raw": text}
    state.append_token(token)
    return match.end()


def parse_oneline_directive(block, match: Match[str], state: BlockState):
    """Preserve a one-line RST directive."""
    text = match.group("directive_oneline")
    token = {"type": "directive", "raw": text}
    state.append_token(token)
    return match.end()


def parse_rst_literal_block_marker(block, match: Match[str], state: BlockState):
    """Recognize a standalone :: marker introducing an RST literal block."""
    token = {"type": "rest_code_block", "raw": ""}
    state.append_token(token)
    return match.end()


def parse_autolink(inline, match: Match[str], state: InlineState):
    """Leave URL and email autolinking to RST, without creating named targets."""
    text = match.group(0)
    if not state.in_link:
        text = text[1:-1]
    inline.process_text(text, state)
    return match.end()


def parse_rest_role(inline, match: Match[str], state: InlineState):
    """Preserve an RST role without interpreting its contents."""
    text = match.group(0)
    token = {"type": "rest_role", "text": text}
    state.append_token(token)
    return match.end()


def parse_rest_link(inline, match: Match[str], state: InlineState):
    """Preserve an RST link."""
    text = match.group(0)
    token = {"type": "rest_link", "text": text}
    state.append_token(token)
    return match.end()


def parse_rst_footnote_ref(inline, match: Match[str], state: InlineState):
    """Preserve an RST footnote reference such as [#a]_."""
    text = match.group(0)
    token = {"type": "rst_footnote_ref", "text": text}
    state.append_token(token)
    return match.end()


def parse_inline_math(inline, match: Match[str], state: InlineState):
    """Parse inline math."""
    math = match.group("math")
    token = {"type": "inline_math", "math": math}
    state.append_token(token)
    return match.end()


def parse_eol_literal_marker(inline, match: Match[str], state: InlineState):
    """Parse an end-of-line literal marker."""
    preceding_whitespace = match.group("spaces")
    # Keep one colon when :: is attached to the preceding text.
    marker = ":" if preceding_whitespace is None else ""
    token = {"type": "eol_literal_marker", "marker": marker}
    state.append_token(token)
    return match.end()


def parse_list_with_visual_indentation(
    block: BlockParser, match: Match[str], state: BlockState
) -> int:
    """Parse list blocks, accepting two-space indentation for nested content."""
    list_indent = len(match.group("visual_list_spaces"))
    is_ordered = len(match.group("visual_list_marker")) > 1
    items: list[dict[str, Any]] = []
    block_interrupt_pattern = block.compile_sc(
        [
            "fenced_code",
            "atx_heading" if "atx_heading" in block.specification else "axt_heading",
            "thematic_break",
            "block_quote",
            "list",
            "directive",
        ]
    )
    list_item_pattern = re.compile(VISUAL_LIST_PATTERN, re.MULTILINE)
    thematic_break_pattern = block.compile_sc(["thematic_break"])

    while True:
        marker = match.group("visual_list_marker")
        item_indent = len(match.group("visual_list_spaces"))
        item_is_ordered = len(marker) > 1
        if item_indent != list_indent or item_is_ordered != is_ordered:
            break

        content_indent = list_indent + len(marker) + 1
        first_line = match.group("visual_list_content").lstrip() + "\n"
        lines = []
        state.cursor = match.end() + 1

        while state.cursor < state.cursor_max:
            line_end = state.find_line_end()
            line = state.get_text(line_end)
            if line.strip() == "":
                lines.append("\n")
            else:
                line_indent = len(line) - len(line.lstrip(" "))
                if line_indent < list_indent + 2:
                    previous_line_is_blank = len(lines) > 0 and lines[-1].strip() == ""
                    # Less indentation can continue a paragraph unless a blank
                    # line or a new block separates it from the list item.
                    if (
                        previous_line_is_blank
                        or block_interrupt_pattern.match(line) is not None
                    ):
                        break
                else:
                    content_indent = min(content_indent, line_indent)
                lines.append(line)
            state.cursor = line_end

        item_content = first_line + "".join(
            line[content_indent:] if line.startswith(" " * content_indent) else line
            for line in lines
        )
        item_state = state.child_state(item_content.rstrip("\n") + "\n")
        block.parse(item_state)
        items.append(
            {
                "type": "list_item",
                "children": item_state.tokens,
                "blank_after": len(lines) > 0 and lines[-1] == "\n",
            }
        )
        next_match = list_item_pattern.match(state.src, state.cursor)
        if (
            next_match is None
            or thematic_break_pattern.match(state.src, state.cursor) is not None
        ):
            break
        match = next_match

    state.append_token(
        {
            "type": "list",
            "children": items,
            "tight": False,
            "attrs": {"ordered": is_ordered},
        }
    )
    return state.cursor


def configure_markdown_parser_for_rst(markdown):
    """Configure Markdown parsing for conversion to reStructuredText."""
    markdown.block.register(
        "list", VISUAL_LIST_PATTERN, parse_list_with_visual_indentation
    )
    markdown.inline.register("auto_link", None, parse_autolink)
    markdown.inline.register("auto_email", None, parse_autolink)

    # Register directive parsers before indent_code so indented directives are recognized
    markdown.block.register(
        "directive", DIRECTIVE_PATTERN, parse_directive, before="indent_code"
    )
    markdown.block.register(
        "oneline_directive",
        ONELINE_DIRECTIVE_PATTERN,
        parse_oneline_directive,
        before="indent_code",
    )
    markdown.block.register(
        "rest_code_block",
        RST_LITERAL_BLOCK_MARKER_PATTERN,
        parse_rst_literal_block_marker,
        before="paragraph",
    )

    # Recognize backtick-delimited math and RST syntax before Markdown code spans.
    markdown.inline.register(
        "inline_math", INLINE_MATH_PATTERN, parse_inline_math, before="codespan"
    )
    markdown.inline.register(
        "rest_role", REST_ROLE_PATTERN, parse_rest_role, before="codespan"
    )
    markdown.inline.register(
        "rest_link", REST_LINK_PATTERN, parse_rest_link, before="codespan"
    )
    markdown.inline.register(
        "rst_footnote_ref",
        RST_FOOTNOTE_REF_PATTERN,
        parse_rst_footnote_ref,
        before="codespan",
    )
    markdown.inline.register(
        "eol_literal_marker",
        EOL_LITERAL_MARKER_PATTERN,
        parse_eol_literal_marker,
        before="text",
    )
