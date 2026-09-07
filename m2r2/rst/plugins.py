from __future__ import annotations

import re
from re import Match
from typing import Any

from mistune import BlockParser
from mistune.core import BlockState, InlineState

# Block patterns
# Multiline directive: starts with .., continues with indented lines
# Blank lines within indented content are part of the directive
# The directive ends when we hit a non-indented, non-blank line
DIRECTIVE_PATTERN = (
    r"^(?P<directive_multiline>"
    r" *\.\..*\n"  # First line: spaces, .., optional text, newline
    r"(?:"
    r"(?:[ \t]+.*\n)"  # Indented line
    r"|"
    r"(?:[ \t]*\n(?=[ \t\n]*[ \t]))"  # Blank line(s) only if eventually followed by indented line
    r")*"
    r"(?:[ \t]*\n(?=[ \t]*$|[ \t]*\n*$))?"  # Trailing blank line only if at end of input
    r")"
)
# One-line directive: just .. followed by content on same line, at end of input
ONELINE_DIRECTIVE_PATTERN = r"^(?P<directive_oneline> *\.\.[^\n]*)$"
REST_CODE_BLOCK_PATTERN = r"^(?P<code_block>::\s*)$"

# Custom list pattern that allows any indentation for visual nesting
VISUAL_LIST_PATTERN = (
    r"^(?P<visual_list_spaces> *)"  # Allow any number of leading spaces
    r"(?P<visual_list_marker>[*+\-]|\d{1,9}[.)])"
    r"(?P<visual_list_content>[ \t]*|[ \t].+)$"
)

# Inline patterns
REST_ROLE_PATTERN = r":.*?:`.*?`|`[^`]+`:.*?:"
REST_LINK_PATTERN = r"`[^`]*?`_"
RST_FOOTNOTE_REF_PATTERN = r"\[[#][^\]]+\]_"  # [#ref]_ style references
INLINE_MATH_PATTERN = r"`\$(?P<math>.*?)\$`"
EOL_LITERAL_MARKER_PATTERN = r"(?P<spaces>\s+)?::\s*$"


# Block parsers
def parse_directive(block, m: Match, state: BlockState):
    """Parse RST directive"""
    text = m.group("directive_multiline")
    # Use 'raw' to prevent mistune from processing through inline parser
    token = {"type": "directive", "raw": text}
    state.append_token(token)
    return m.end()


def parse_oneline_directive(block, m: Match, state: BlockState):
    """Parse one-line RST directive"""
    text = m.group("directive_oneline")
    # Use 'raw' to prevent mistune from processing through inline parser
    token = {"type": "directive", "raw": text}
    state.append_token(token)
    return m.end()


def parse_rest_code_block(block, m: Match, state: BlockState):
    """Parse RST code block (::)"""
    token = {"type": "rest_code_block", "raw": ""}
    state.append_token(token)
    return m.end()


# Inline parsers
def parse_rest_role(inline, m: Match, state: InlineState):
    """Parse RST role"""
    text = m.group(0)
    token = {"type": "rest_role", "text": text}
    state.append_token(token)
    return m.end()


def parse_rest_link(inline, m: Match, state: InlineState):
    """Parse RST link"""
    text = m.group(0)
    token = {"type": "rest_link", "text": text}
    state.append_token(token)
    return m.end()


def parse_rst_footnote_ref(inline, m: Match, state: InlineState):
    """Parse RST footnote reference like [#a]_"""
    text = m.group(0)
    token = {"type": "rst_footnote_ref", "text": text}
    state.append_token(token)
    return m.end()


def parse_inline_math(inline, m: Match, state: InlineState):
    """Parse inline math"""
    math = m.group("math")
    token = {"type": "inline_math", "math": math}
    state.append_token(token)
    return m.end()


def parse_eol_literal_marker(inline, m: Match, state: InlineState):
    """Parse end-of-line literal marker"""
    spaces = m.group("spaces")
    marker = ":" if spaces is None else ""
    token = {"type": "eol_literal_marker", "marker": marker}
    state.append_token(token)
    return m.end()


def parse_visual_list_nested(
    block: BlockParser, m: Match[str], state: BlockState
) -> int:
    """Parse list blocks, accepting two-space indentation for nested content."""
    indent = len(m.group("visual_list_spaces"))
    ordered = len(m.group("visual_list_marker")) > 1
    items: list[dict[str, Any]] = []
    interrupt = block.compile_sc(
        [
            "fenced_code",
            "atx_heading" if "atx_heading" in block.specification else "axt_heading",
            "thematic_break",
            "block_quote",
            "list",
            "directive",
        ]
    )

    while True:
        marker = m.group("visual_list_marker")
        if len(m.group("visual_list_spaces")) != indent or (len(marker) > 1) != ordered:
            break

        content_indent = indent + len(marker) + 1
        first_line = m.group("visual_list_content").lstrip() + "\n"
        lines = []
        state.cursor = m.end() + 1

        while state.cursor < state.cursor_max:
            end = state.find_line_end()
            line = state.get_text(end)
            if line.strip() == "":
                lines.append("\n")
            else:
                width = len(line) - len(line.lstrip(" "))
                if width < indent + 2:
                    if (len(lines) > 0 and lines[-1].strip() == "") or interrupt.match(
                        line
                    ):
                        break
                else:
                    content_indent = min(content_indent, width)
                lines.append(line)
            state.cursor = end

        content = first_line + "".join(
            line[content_indent:] if line.startswith(" " * content_indent) else line
            for line in lines
        )
        child = state.child_state(content.rstrip("\n") + "\n")
        block.parse(child)
        items.append({"type": "list_item", "children": child.tokens})
        next_match = re.compile(VISUAL_LIST_PATTERN, re.M).match(
            state.src, state.cursor
        )
        if next_match is None or block.compile_sc(["thematic_break"]).match(
            state.src, state.cursor
        ):
            break
        m = next_match

    state.append_token(
        {
            "type": "list",
            "children": items,
            "tight": False,
            "attrs": {"ordered": ordered},
        }
    )
    return state.cursor


def rst_directives(md):
    """Plugin to handle RST directives and inline elements"""
    md.block.register("list", VISUAL_LIST_PATTERN, parse_visual_list_nested)

    # Register directive parsers before indent_code so indented directives are recognized
    md.block.register(
        "directive", DIRECTIVE_PATTERN, parse_directive, before="indent_code"
    )
    md.block.register(
        "oneline_directive",
        ONELINE_DIRECTIVE_PATTERN,
        parse_oneline_directive,
        before="indent_code",
    )
    md.block.register(
        "rest_code_block",
        REST_CODE_BLOCK_PATTERN,
        parse_rest_code_block,
        before="paragraph",
    )

    # Register inline parsers - math and roles need to run before codespan
    md.inline.register(
        "inline_math", INLINE_MATH_PATTERN, parse_inline_math, before="codespan"
    )
    md.inline.register(
        "rest_role", REST_ROLE_PATTERN, parse_rest_role, before="codespan"
    )
    md.inline.register(
        "rest_link", REST_LINK_PATTERN, parse_rest_link, before="codespan"
    )
    md.inline.register(
        "rst_footnote_ref",
        RST_FOOTNOTE_REF_PATTERN,
        parse_rst_footnote_ref,
        before="codespan",
    )
    md.inline.register(
        "eol_literal_marker",
        EOL_LITERAL_MARKER_PATTERN,
        parse_eol_literal_marker,
        before="text",
    )
