from __future__ import annotations

import re
from re import Match
from typing import Any

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
IMAGE_PATTERN = r"!\[(?P<img_alt>.*?)\]\((?P<src>.*?)\)"
IMAGE_LINK_PATTERN = r"\[!\[(?P<alt>.*?)\]\((?P<url>.*?)\).*?\]\((?P<target>.*?)\)"
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
def parse_image(inline, m: Match, state: InlineState):
    """Parse image"""
    alt = m.group("img_alt")
    src = m.group("src")
    token = {"type": "image", "alt": alt, "src": src}
    state.append_token(token)
    return m.end()


def parse_image_link(inline, m: Match, state: InlineState):
    """Parse image link"""
    alt = m.group("alt")
    url = m.group("url")
    target = m.group("target")
    token = {"type": "image_link", "alt": alt, "url": url, "target": target}
    state.append_token(token)
    return m.end()


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


def parse_visual_list_nested(block, m: Match, state: BlockState):
    """Parse lists with visual nesting detection for m2r2 compatibility."""
    # Collect all consecutive list items first
    all_items = _collect_all_list_items(block, state, m)

    if not all_items:
        return state.cursor

    # Build nested structure from the flat list
    root_lists = _build_nested_lists(all_items)

    # Add all root lists to state
    for list_token in root_lists:
        state.append_token(list_token)

    return state.cursor


def _collect_all_list_items(block, state: BlockState, first_match: Match):
    """Collect all consecutive list items from the current position.

    Handles multiline list items where continuation lines are indented
    but don't have a list marker.
    """
    items = []

    # Add the first item from the match
    leading_spaces = first_match.group("visual_list_spaces")
    marker = first_match.group("visual_list_marker")
    text = first_match.group("visual_list_content")

    current_item = {
        "indent": len(leading_spaces),
        "marker": marker,
        "content_lines": [text.strip()] if text and text.strip() else [],
        "ordered": len(marker) > 1,
    }

    # Advance cursor past the first matched line
    state.cursor = first_match.end()
    if state.cursor < state.cursor_max and state.src[state.cursor] == "\n":
        state.cursor += 1

    # Continue reading lines to find more list items and continuation lines
    while state.cursor < state.cursor_max:
        line_end = state.find_line_end()
        line = state.get_text(line_end)

        # Check if this is a blank line
        if block.BLANK_LINE.match(line):
            state.cursor = line_end
            continue

        # Check if this is another list item
        list_match = re.match(VISUAL_LIST_PATTERN, line)
        if list_match:
            # Save the current item
            items.append(
                {
                    "indent": current_item["indent"],
                    "marker": current_item["marker"],
                    "content": "\n".join(current_item["content_lines"]),
                    "ordered": current_item["ordered"],
                }
            )

            # Start a new item
            spaces = list_match.group("visual_list_spaces")
            marker = list_match.group("visual_list_marker")
            content = list_match.group("visual_list_content")

            current_item = {
                "indent": len(spaces),
                "marker": marker,
                "content_lines": [content.strip()]
                if content and content.strip()
                else [],
                "ordered": len(marker) > 1,
            }
            state.cursor = line_end
        else:
            # Check if this is a continuation line (indented text that's part of current item)
            # Line must be indented and we haven't seen a blank line that would end continuation
            stripped = line.rstrip("\n")
            line_indent = len(stripped) - len(stripped.lstrip())

            # Continuation if indented at least to the marker end column
            # or if indented more than the item's leading spaces (for visually nested content)
            if line_indent >= current_item["indent"] + 2 and stripped.strip():
                # This is a continuation line
                # Strip the leading indent to match the item's base indent level
                content_text = stripped[current_item["indent"] + 2 :]
                current_item["content_lines"].append(content_text)
                state.cursor = line_end
            else:
                # Not a list item or continuation - stop collecting
                break

    # Don't forget to add the last item
    items.append(
        {
            "indent": current_item["indent"],
            "marker": current_item["marker"],
            "content": "\n".join(current_item["content_lines"]),
            "ordered": current_item["ordered"],
        }
    )

    return items


def _build_nested_lists(items: list[dict]) -> list[dict[str, Any]]:
    """Build nested list structure from flat items using a stack-based approach."""
    if not items:
        return []

    # Stack to keep track of current lists at each indentation level
    # Each element is (indent_level, list_token, last_item)
    list_stack: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    root_lists: list[dict[str, Any]] = []

    for item in items:
        current_indent = item["indent"]

        # Pop from stack until we find the right parent level
        while list_stack and list_stack[-1][0] >= current_indent:
            list_stack.pop()

        # Create list item
        list_item: dict[str, Any] = {"type": "list_item", "children": []}

        if item["content"]:
            # Use "text" key so mistune's _iter_render runs the inline
            # parser, producing proper children (codespan, emphasis, etc.)
            text_token = {
                "type": "block_text",
                "text": item["content"],
            }
            list_item["children"].append(text_token)

        if not list_stack:
            # This is a root-level item
            # Check if we can add to existing root list or need a new one
            if (
                root_lists
                and root_lists[-1]["attrs"]["ordered"] == item["ordered"]
                and current_indent == 0
            ):
                # Add to existing root list
                current_list = root_lists[-1]
            else:
                # Create new root list
                current_list = {
                    "type": "list",
                    "children": [],
                    "tight": True,
                    "attrs": {
                        "ordered": item["ordered"],
                    },
                }
                root_lists.append(current_list)

            # Add item to the list
            current_list["children"].append(list_item)
            list_stack.append((current_indent, current_list, list_item))

        else:
            # This is a nested item
            _, _, parent_item = list_stack[-1]

            # Check if we need a new nested list or can add to existing
            if (
                parent_item["children"]
                and parent_item["children"][-1]["type"] == "list"
                and parent_item["children"][-1]["attrs"]["ordered"] == item["ordered"]
            ):
                # Add to existing nested list
                nested_list = parent_item["children"][-1]
            else:
                # Create new nested list
                nested_list = {
                    "type": "list",
                    "children": [],
                    "tight": True,
                    "attrs": {
                        "ordered": item["ordered"],
                    },
                }
                parent_item["children"].append(nested_list)

            # Add item to nested list
            nested_list["children"].append(list_item)
            list_stack.append((current_indent, nested_list, list_item))

    return root_lists


def rst_directives(md):
    """Plugin to handle RST directives and inline elements"""
    # Use custom visual list parser for backward compatibility with m2r's lenient
    # indentation handling. The original m2r allowed 2-space indentation for nesting.

    # Replace standard list parser with visual list parser (keep same name for compatibility)
    if "list" in md.block.specification:
        del md.block.specification["list"]
        if "list" in md.block.rules:
            md.block.rules.remove("list")
    md.block.register(
        "list", VISUAL_LIST_PATTERN, parse_visual_list_nested, before="paragraph"
    )

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
    md.inline.register("image", IMAGE_PATTERN, parse_image, before="escape")
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
        "image_link", IMAGE_LINK_PATTERN, parse_image_link, before="image"
    )
    md.inline.register(
        "eol_literal_marker",
        EOL_LITERAL_MARKER_PATTERN,
        parse_eol_literal_marker,
        before="text",
    )
