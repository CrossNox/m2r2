from __future__ import annotations

import re
from re import Match
from typing import Any, Literal

from mistune import BlockParser
from mistune.core import BlockState, InlineState

VISUAL_LIST_PATTERN = (
    r"^(?P<visual_list_spaces> *)"
    r"(?P<visual_list_marker>[*+\-]|\d{1,9}[.)])"
    r"(?P<visual_list_content>[ \t]*|[ \t].+)$"
)


def parse_block_quote_with_github_alert(
    block: BlockParser, match: Match[str], state: BlockState
) -> int:
    """Recognize GitHub alerts at the start of top-level block quotes."""
    alert_match = re.fullmatch(
        r" {0,4}\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*",
        match.group("quote_1"),
    )
    if state.depth() != 0 or alert_match is None:
        return block.parse_block_quote(match, state)

    quote_text, end_position = block.extract_block_quote(match, state)
    alert_state = state.child_state(quote_text.partition("\n")[2])
    block.parse(alert_state, block.block_quote_rules)
    alert_token = {
        "type": "github_alert",
        "attrs": {"kind": alert_match.group(1).lower()},
        "children": alert_state.tokens,
    }
    if end_position is not None:
        state.prepend_token(alert_token)
        return end_position
    state.append_token(alert_token)
    return state.cursor


def parse_directive(block, match: Match[str], state: BlockState):
    """Preserve an RST directive."""
    # Use "raw" to bypass Mistune's inline parser.
    token = {"type": "directive", "raw": match.group(0)}
    state.append_token(token)
    return match.end()


def parse_rst_literal_block_marker(block, match: Match[str], state: BlockState):
    """Recognize a standalone :: marker introducing an RST literal block."""
    state.append_token({"type": "rest_code_block"})
    return match.end()


def parse_autolink(inline, match: Match[str], state: InlineState):
    """Leave URL and email autolinking to RST, without creating named targets."""
    text = match.group(0)
    if state.in_link:
        inline.process_text(text, state)
        return match.end()

    # A separate token type hides the address from Mistune's emphasis pass.
    token = {"type": "standalone_hyperlink", "raw": text[1:-1]}
    state.append_token(token)
    return match.end()


def parse_rst_inline_token(inline, match: Match[str], state: InlineState):
    """Preserve an RST inline construct without interpreting its contents."""
    # Mistune uses the matched outer group as the registered token type.
    state.append_token({"type": match.lastgroup, "text": match.group(0)})
    return match.end()


def parse_inline_math(inline, match: Match[str], state: InlineState):
    """Parse inline math."""
    math = match.group("math")
    token = {"type": "inline_math", "math": math}
    state.append_token(token)
    return match.end()


def parse_dollar_inline_math(inline, match: Match[str], state: InlineState):
    """Preserve LaTeX within dollar or dollar-backtick delimiters."""
    quoted_math = match.group("quoted_math")
    math = match.group("math") if quoted_math is None else quoted_math.strip()
    if math == "":
        return None
    state.append_token({"type": "inline_math", "math": math})
    return match.end()


def parse_eol_literal_marker(inline, match: Match[str], state: InlineState):
    """Parse an end-of-line literal marker."""
    preceding_whitespace = match.group("spaces")
    # Keep one colon when :: is attached to the preceding text.
    marker = ":" if preceding_whitespace is None else ""
    token = {"type": "eol_literal_marker", "marker": marker}
    state.append_token(token)
    return match.end()


def parse_literal_underscore(inline, match: Match[str], state: InlineState):
    """Keep an underscore run as literal text that never delimits emphasis."""
    # The escape parser emits literal text, which Mistune's emphasis pass skips.
    return inline.parse_escape(match, state)


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
            "atx_heading",
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


def configure_markdown_parser_for_rst(
    markdown, *, inline_math: Literal["legacy", "dollar"] | None = "legacy"
):
    """Configure Markdown parsing for conversion to reStructuredText."""
    markdown.block.register(
        "list", VISUAL_LIST_PATTERN, parse_list_with_visual_indentation
    )
    markdown.block.register("block_quote", None, parse_block_quote_with_github_alert)
    markdown.inline.register("auto_link", None, parse_autolink)
    markdown.inline.register("auto_email", None, parse_autolink)

    # Multiline directives include indented content and blank lines within it.
    # A trailing blank line is included only at the end of input.
    markdown.block.register(
        "directive",
        (
            r"^(?P<directive_multiline>"
            r" *\.\..*\n"
            r"(?:"
            r"(?:[ \t]+.*\n)"
            r"|"
            r"(?:[ \t]*\n(?=[ \t\n]*[ \t]))"
            r")*"
            r"(?:[ \t]*\n(?=[ \t]*$|[ \t]*\n*$))?"
            r")"
        ),
        parse_directive,
        before="indent_code",
    )
    markdown.block.register(
        "oneline_directive",
        r"^(?P<directive_oneline> *\.\.[^\n]*)$",
        parse_directive,
        before="indent_code",
    )
    markdown.block.register(
        "rest_code_block",
        r"^(?P<code_block>::\s*)$",
        parse_rst_literal_block_marker,
        before="paragraph",
    )

    if inline_math == "legacy":
        markdown.inline.register(
            "inline_math",
            r"`\$(?P<math>[^`\n]*?)\$`",
            parse_inline_math,
            before="codespan",
        )
    elif inline_math == "dollar":
        # Bare dollar delimiters cannot touch whitespace or close before a digit.
        # Escapes stay inside the expression, and double dollars are excluded.
        markdown.inline.register(
            "inline_math",
            (
                r"(?<!\$)\$(?!\$)(?:"
                r"`(?P<quoted_math>(?:\\[^\n]|[^\\`\n])+?)`\$(?!\$)"
                r"|(?![\s`])(?P<math>(?:\\[^\n]|[^\\$`\n])+?)(?<!\s)\$(?![\d$])"
                r")"
            ),
            parse_dollar_inline_math,
            before="codespan",
        )
    elif "inline_math" in markdown.inline.rules:
        markdown.inline.rules.remove("inline_math")

    # Recognize RST syntax before Markdown code spans.
    markdown.inline.register(
        "rest_role",
        r":.*?:`.*?`|`[^`]+`:.*?:",
        parse_rst_inline_token,
        before="codespan",
    )
    markdown.inline.register(
        "rest_link", r"`[^`]*?`_", parse_rst_inline_token, before="codespan"
    )
    markdown.inline.register(
        "rst_footnote_ref",
        r"\[[#][^\]]+\]_",
        parse_rst_inline_token,
        before="codespan",
    )
    markdown.inline.register(
        "eol_literal_marker",
        r"(?P<spaces>\s+)?::\s*$",
        parse_eol_literal_marker,
        before="text",
    )
