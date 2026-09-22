from __future__ import annotations

import html
import os
import re
from collections.abc import Container, Iterable
from hashlib import sha256
from typing import TYPE_CHECKING, Any, ClassVar, cast
from urllib.parse import urlparse

from docutils.utils import column_width
from mistune.core import BlockState
from mistune.renderers.rst import RSTRenderer

if TYPE_CHECKING:
    from mistune import Markdown

RAW_HTML_ROLE_NAME = "raw-html-m2r"
RAW_HTML_ROLE_DEFINITION = f".. role:: {RAW_HTML_ROLE_NAME}(raw)\n   :format: html"

#: Hex characters of the hash a substitution is named after. Twelve leaves the
#: chance of two substitutions colliding in one document near one in a billion.
SUBSTITUTION_NAME_HASH_LENGTH = 12


class SubstitutionNameCollision(Exception):
    """Two substitution definitions in one document want the same name."""


# Matches: :raw-html-m2r:`<tag>`\ text\ :raw-html-m2r:`</tag>`
# and combines into: :raw-html-m2r:`<tag>text</tag>`
# The middle group excludes backslashes and newlines to prevent
# cross-line merges that would consume unrelated RST content.
_RAW_HTML_MERGE_PATTERN = re.compile(
    rf":{RAW_HTML_ROLE_NAME}:`([^`]+)`\\ ([^\\\n]+)\\ :{RAW_HTML_ROLE_NAME}:`([^`]+)`"
)


def record_role_definition(state: BlockState, name: str, definition: str) -> None:
    """Record a role the body uses, to be defined above it."""
    state.env.setdefault("role_definitions", {})[name] = definition


def define_substitution(
    state: BlockState,
    name_prefix: str,
    directive: str,
    target_url: str | None = None,
) -> str:
    """Record a substitution the body references, and return the name to use.

    The name holds a hash of the directive, so the same content is defined once
    per document and an ``mdinclude`` can tell whether its host already has it.
    A ``target_url`` adds the named target that turns the substitution into a
    link.
    """
    hashed = directive if target_url is None else f"{directive}\n{target_url}"
    digest = sha256(hashed.encode("utf-8")).hexdigest()
    name = f"{name_prefix}-{digest[:SUBSTITUTION_NAME_HASH_LENGTH]}"
    definition = f".. |{name}| {directive}"
    if target_url is not None:
        definition += f"\n.. _{name}: {target_url}"

    definitions = state.env.setdefault("substitution_definitions", {})
    if definitions.get(name, definition) != definition:
        raise SubstitutionNameCollision(
            f"Two substitutions want the name {name}:\n{definitions[name]}\n{definition}"
        )
    definitions[name] = definition

    return name


def merge_adjacent_raw_html_roles(text: str) -> str:
    """Join raw HTML roles that mistune splits across tokens."""
    while _RAW_HTML_MERGE_PATTERN.search(text) is not None:
        text = _RAW_HTML_MERGE_PATTERN.sub(rf":{RAW_HTML_ROLE_NAME}:`\1\2\3`", text)
    return text


def trim_inline_escapes(text: str) -> str:
    """Drop the escapes around an inline fragment taken out of a document.

    A definition holds inline text that never sees the pass over the body, so
    the escapes the renderer wrote at its edges have nothing left to separate.
    """
    return remove_redundant_inline_escapes(text.removeprefix("\\ ").removesuffix("\\ "))


def remove_redundant_inline_escapes(text: str) -> str:
    """Drop the ``\\ `` escapes this renderer writes where RST does not need them.

    The renderer separates inline markup from its surroundings with an escaped
    space. At a line boundary, between spaces, or before a period, that escape
    carries no meaning.
    """
    return (
        text.replace("\\ \n", "\n")
        .replace("\n\\ ", "\n")
        .replace(" \\ ", " ")
        .replace("\\  ", " ")
        .replace("\\ .", ".")
    )


class RestRenderer(RSTRenderer):
    """Render Markdown as RST with embedded directives and inline roles."""

    indent = " " * 3
    hmarks: ClassVar[dict[int, str]] = {
        1: "=",
        2: "-",
        3: "^",
        4: "~",
        5: '"',
        6: "#",
    }

    def __init__(
        self,
        *,
        parse_relative_links: bool = False,
        anonymous_references: bool = False,
        use_mermaid: bool = False,
        is_sphinx: bool = False,
        existing_substitutions: Container[str] = (),
    ) -> None:
        self.parse_relative_links = parse_relative_links
        self.anonymous_references = anonymous_references
        self.use_mermaid = use_mermaid
        self.is_sphinx = is_sphinx
        self.existing_substitutions = existing_substitutions
        super().__init__()

    def iter_tokens(
        self, tokens: Iterable[dict[str, Any]], state: BlockState
    ) -> Iterable[str]:
        """Override to preserve blank lines around RST directives.

        The parent RSTRenderer ignores blank_line tokens, but we need them
        to maintain proper spacing for RST directives. We emit blank lines:
        1. Before a directive (RST requires blank line before directives)
        2. Between consecutive directives (preserve exact spacing)
        3. After a directive before other content (only if directive doesn't
           already have trailing blank lines)
        """
        prev_tok = None
        pending_blank_lines = 0

        for tok in tokens:
            if tok["type"] == "blank_line":
                pending_blank_lines += 1
                continue

            # Emit pending blank lines in these cases:
            if pending_blank_lines > 0:
                if tok["type"] == "directive":
                    # Always emit blank lines before a directive
                    for _ in range(pending_blank_lines):
                        yield "\n"
                elif prev_tok is not None and prev_tok["type"] == "directive":
                    # After a directive, only emit if the directive didn't
                    # already have trailing blank lines (single trailing \n)
                    prev_raw = prev_tok.get("raw", "")
                    trailing = len(prev_raw) - len(prev_raw.rstrip("\n"))
                    if trailing <= 1:
                        # No trailing blank lines in directive, emit them
                        for _ in range(pending_blank_lines):
                            yield "\n"
            pending_blank_lines = 0

            # Maintain parent's contract: each token carries a reference
            # to the previous non-blank token.  The parent's block_quote()
            # (and potentially future methods) relies on token["prev"].
            tok["prev"] = prev_tok
            prev_tok = tok
            yield self.render_token(tok, state)

    def __call__(self, tokens: Iterable[dict[str, Any]], state: BlockState) -> str:
        """Render tokens into the body of a document.

        Mistune calls this once for the body and again for the footnotes, so
        the definitions the body relies on are written by
        ``prepend_document_definitions`` once both passes are done.
        """
        return self.render_tokens(tokens, state)

    def thematic_break(self, token, state):
        """Override to use shorter horizontal rule"""
        return "\n----\n"

    def linebreak(self, token, state):
        """Override to use raw HTML format instead of line blocks"""
        record_role_definition(state, RAW_HTML_ROLE_NAME, RAW_HTML_ROLE_DEFINITION)
        return f"\\ :{RAW_HTML_ROLE_NAME}:`<br>`\n"

    def paragraph(self, token: dict[str, Any], state: BlockState) -> str:
        """Render a paragraph or a standalone image block."""
        children = token["children"]
        target = None
        if len(children) == 1 and children[0]["type"] == "link":
            target = children[0]["attrs"]["url"]
            children = children[0]["children"]
        if len(children) == 1 and children[0]["type"] == "image":
            if target is None:
                target = children[0]["attrs"]["url"]
            return self.render_image(children[0], state, target=target, inline=False)
        text = self.render_children(token, state)
        return f"\n{text}\n"

    def softbreak(self, token, state):
        """Override to preserve line breaks instead of converting to spaces"""
        return "\n"

    def _indent_block(self, block):
        return "\n".join(
            self.indent + line if line else "" for line in block.splitlines()
        )

    def _raw_html(self, raw, state):
        record_role_definition(state, RAW_HTML_ROLE_NAME, RAW_HTML_ROLE_DEFINITION)
        # Escape backticks to prevent breaking the RST role syntax
        raw = raw.replace("`", "&#96;")
        return rf"\ :{RAW_HTML_ROLE_NAME}:`{raw}`\ "

    def block_code(self, token: dict[str, Any], state: BlockState):
        # Extract code content from token
        code_text = token.get("raw", "")

        # Extract language from the info string (first word only, e.g. "python title=x" -> "python")
        info = token.get("attrs", {}).get("info", "") if "attrs" in token else ""
        lang = info.split()[0] if info else ""

        if lang == "math":
            first_line = "\n.. math::\n\n"
        elif lang == "mermaid" and self.use_mermaid:
            first_line = "\n.. mermaid::\n\n"
        elif lang:
            first_line = f"\n.. code-block:: {lang}\n\n"
        elif self.is_sphinx:
            first_line = "\n::\n\n"
        else:
            first_line = "\n.. code-block::\n\n"
        return first_line + self._indent_block(code_text) + "\n"

    def directive(self, token, state):
        """Render RST directive token.

        Preserves the raw RST directive text. Trailing newlines are preserved
        as-is for proper RST spacing between directives. The trailing newlines
        represent blank lines in the source markdown.
        """
        text = token.get("raw", "")

        # Count trailing newlines
        content = text.rstrip("\n")
        trailing_newlines = len(text) - len(content)

        if trailing_newlines > 1:
            # Multiple trailing newlines = blank lines, preserve them all
            return content + "\n" * trailing_newlines
        else:
            # Single or no trailing newline - just return content without newline
            return content

    def rest_role(self, token, state):
        """Pass through RST role"""
        return token.get("text", "")

    def rest_link(self, token, state):
        """Pass through RST link"""
        return token.get("text", "")

    def rst_footnote_ref(self, token, state):
        """Pass through RST footnote reference like [#a]_"""
        return token.get("text", "")

    def inline_math(self, token, state):
        """Render inline math"""
        math = token.get("math", "")
        return f":math:`{math}`"

    def eol_literal_marker(self, token, state):
        """Render end-of-line literal marker"""
        marker = token.get("marker", "")
        return marker

    def standalone_hyperlink(self, token: dict[str, Any], state: BlockState) -> str:
        """Render a bare URL or email address for docutils to recognize."""
        return self.text(token, state)

    def link(self, token: dict[str, Any], state: BlockState) -> str:
        """Render a hyperlink or a Sphinx document reference."""
        return self.render_link(token, state, emphasis_marker="")

    def render_link(
        self, token: dict[str, Any], state: BlockState, emphasis_marker: str
    ) -> str:
        """Render a hyperlink, a Sphinx cross-reference, or a linked image.

        ``emphasis_marker`` is the RST emphasis around the link, empty for none.
        """
        url = token["attrs"]["url"]
        title = token["attrs"].get("title")
        children = token["children"]
        if len(children) == 1 and children[0]["type"] == "image":
            return self.render_image(children[0], state, target=url)

        if title:
            text = self.render_children(token, state)
            return self._raw_html(
                f'<a href="{html.escape(url)}" title="{html.escape(title)}">{text}</a>',
                state,
            )

        url_info = urlparse(url)
        if not self.parse_relative_links or url_info.scheme != "":
            return self.render_hyperlink_reference(token, state, url, emphasis_marker)

        # A Sphinx role holds plain text, so emphasis around the link is lost.
        text = self.render_children(token, state)
        if url_info.fragment and not url_info.path:
            # Anchor-only link, e.g. [text](#anchor)
            return rf"\ :ref:`{text} <{url_info.fragment}>`\ "

        # Document link, e.g. [text](page.md) or [text](page.md#anchor).
        # The :doc: directive does not support anchors, so the fragment
        # is intentionally discarded — matching the original m2r behavior.
        doc_link = os.path.splitext(url_info.path)[0]
        return rf"\ :doc:`{text} <{doc_link}>`\ "

    def render_hyperlink_reference(
        self, token: dict[str, Any], state: BlockState, url: str, emphasis_marker: str
    ) -> str:
        """Render a link to a URL, keeping emphasis around it and markup in its text."""
        text = self.render_children(token, state)
        if len(text.strip()) == 0:
            # An empty link has nothing to emphasize and nothing to show. The
            # escaped space keeps docutils reading a reference, and the
            # anonymous form keeps two of them from claiming one name.
            return rf"\ `\ <{url}>`__\ "

        holds_only_text = all(
            child["type"] in ("text", "softbreak") for child in token["children"]
        )
        if emphasis_marker == "" and holds_only_text:
            underscore = "__" if self.anonymous_references else "_"
            return rf"\ `{text} <{url}>`{underscore}\ "

        # RST cannot nest inline markup in a hyperlink reference, so the text
        # goes in a substitution and a named target makes it a link. The
        # replacement opens with an escaped space, which docutils drops, so that
        # text starting with "- " or "1. " cannot turn into a list.
        if emphasis_marker != "":
            text = self.render_emphasis(token, state, emphasis_marker)
        replacement = trim_inline_escapes(text).replace("\n", " ")
        name = define_substitution(
            state, "m2r-link", f"replace:: \\ {replacement}", target_url=url
        )
        return rf"\ |{name}|_\ "

    def heading(self, token, state):
        """Override to fix heading underlines for multibyte characters"""
        # Extract level from token attrs in mistune v3
        if "attrs" in token and "level" in token["attrs"]:
            level = token["attrs"]["level"]
        else:
            level = token.get("level", 1)

        text = self.render_children(token, state)

        if level in self.hmarks:
            mark = self.hmarks[level]
            # Use column_width for proper multibyte character counting
            width = column_width(text)
            return f"\n{text}\n{mark * width}\n"
        else:
            return f"\n{text}\n"

    def rest_code_block(self, token, state):
        """Absorb standalone ``::`` lines.

        Without this, a bare ``::`` would be parsed as a paragraph and
        potentially trigger the eol_literal_marker inline rule. The actual
        code block following ``::`` is handled by mistune's standard rules.
        """
        return "\n\n"

    def block_quote(self, token, state):
        """Render block quote"""
        children = self.render_children(token, state)
        # Indent all lines by 3 spaces and add blank line before/after
        indented = self._indent_block(children.strip())
        return f"\n..\n\n{indented}\n\n"

    def image(self, token: dict[str, Any], state: BlockState) -> str:
        """Render an inline image with a link to its source."""
        return self.render_image(token, state, target=token["attrs"]["url"])

    def render_image(
        self,
        token: dict[str, Any],
        state: BlockState,
        target: str,
        *,
        inline: bool = True,
    ) -> str:
        """Render an image as a block directive or an inline substitution."""
        source = token["attrs"]["url"]
        alt = trim_inline_escapes(self.render_children(token, state)).replace("\n", " ")
        content = f"image:: {source}\n   :target: {target}\n   :alt: {alt}"
        if not inline:
            return f"\n\n.. {content}\n\n"
        name = define_substitution(state, "m2r-image", content)
        return rf"\ |{name}|\ "

    def block_html(self, token, state):
        """Render block HTML as raw HTML directive"""
        raw = token.get("raw", "").rstrip("\n")
        indented = self._indent_block(raw)
        return f"\n\n.. raw:: html\n\n{indented}\n\n"

    def inline_html(self, token, state):
        """Render inline HTML as raw HTML role"""
        raw = token.get("raw", "")
        return self._raw_html(raw, state)

    def codespan(self, token, state):
        """Render inline code span.

        Leading/trailing whitespace is stripped because CommonMark's
        double-backtick code spans can preserve spaces (e.g.
        `` `text`:role: ``), and a leading space after RST's ``
        breaks docutils' inline literal parser.
        """
        code = token.get("raw", "").strip()
        if "``" not in code:
            return rf"\ ``{code}``\ "
        else:
            # Use raw HTML for code with backticks.
            # Backticks in the code are already escaped by _raw_html(),
            # but we also escape them in the visible <span> content for
            # correct HTML rendering.
            return self._raw_html(
                '<code class="docutils literal">'
                f'<span class="pre">{code.replace("`", "&#96;")}</span>'
                "</code>",
                state,
            )

    def strikethrough(self, token, state):
        """Render strikethrough as raw HTML ``<del>`` via raw-html-m2r role."""
        text = self.render_children(token, state)
        return self._raw_html(f"<del>{text}</del>", state)

    def emphasis(self, token: dict[str, Any], state: BlockState) -> str:
        return self.render_emphasis(token, state, "*")

    def strong(self, token: dict[str, Any], state: BlockState) -> str:
        return self.render_emphasis(token, state, "**")

    def render_emphasis(
        self, token: dict[str, Any], state: BlockState, marker: str
    ) -> str:
        """Apply emphasis to text without nesting RST inline markup."""

        def emphasize(text):
            content = text.strip()
            if content:
                return text.replace(content, rf"\ {marker}{content}{marker}\ ", 1)
            return text

        parts = []
        text = ""
        for child in token["children"]:
            if child["type"] in ("text", "softbreak", "standalone_hyperlink"):
                text += self.render_token(child, state)
                continue
            parts.append(emphasize(text))
            text = ""
            if child["type"] == "link":
                # A link carries the emphasis itself, since RST cannot nest one
                # inside the other.
                parts.append(self.render_link(child, state, emphasis_marker=marker))
            else:
                parts.append(self.render_token(child, state))
        parts.append(emphasize(text))
        return "".join(parts)

    def list(self, token: dict[str, Any], state: BlockState) -> str:
        """Render list items with their blocks in source order."""
        marker = "#. " if token["attrs"]["ordered"] else "* "
        items = []
        separator = ""
        for item in token["children"]:
            content = self.render_children(item, state).strip("\n")
            lines = content.split("\n")
            continuation = "\n".join(
                " " * len(marker) + line if line != "" else "" for line in lines[1:]
            )
            items.append(
                separator
                + marker
                + lines[0]
                + ("\n" + continuation if len(lines) > 1 else "")
            )
            # Keep simple siblings compact, but terminate nested/multiple blocks
            # and preserve blank lines explicitly separating source items.
            blocks = [
                child for child in item["children"] if child["type"] != "blank_line"
            ]
            separator = "\n\n" if item.get("blank_after") or len(blocks) > 1 else "\n"
        previous = token.get("prev")
        # Preserve the legacy spacing after headings and preceding lists.
        prefix = (
            "\n\n" if previous and previous["type"] in ("heading", "list") else "\n"
        )
        return prefix + "".join(items) + "\n"

    def table(self, token, state):
        """Render table as RST list-table directive"""
        children = token.get("children", [])
        head_content = ""
        body_content = ""

        for child in children:
            if child["type"] == "table_head":
                head_content = self.table_head(child, state)
            elif child["type"] == "table_body":
                body_content = self.table_body(child, state)

        result = "\n.. list-table::\n"
        if head_content:
            result += "   :header-rows: 1\n\n"
            result += head_content
        else:
            result += "\n"
        result += body_content
        result += "\n"
        return result

    def _table_row_head_helper(self, token, state):
        """Helper method for table_head and table_row."""
        cells = token.get("children", [])
        if not cells:
            return ""

        result = "   * - " + self.render_children(cells[0], state).strip() + "\n"
        for cell in cells[1:]:
            result += "     - " + self.render_children(cell, state).strip() + "\n"
        return result

    def table_head(self, token, state):
        """Render table header."""
        return self._table_row_head_helper(token, state)

    def table_body(self, token, state):
        """Render table body"""
        result = ""
        for row in token.get("children", []):
            result += self.table_row(row, state)
        return result

    def table_row(self, token, state):
        """Render table row"""
        return self._table_row_head_helper(token, state)

    # Footnote rendering methods
    def footnote_ref(self, token, state):
        """Render footnote reference"""
        # Key can be in attrs or directly in raw
        attrs = token.get("attrs", {})
        key = token.get("raw", attrs.get("key", str(attrs.get("index", ""))))
        # Normalize to lowercase: mistune v3 uppercases footnote keys internally
        key = key.lower()
        return rf"\ [#fn-{key}]_\ "

    def footnote_item(self, token, state):
        """Render footnote item"""
        attrs = token.get("attrs", {})
        key = attrs.get("key", str(attrs.get("index", "")))
        # Normalize to lowercase: mistune v3 uppercases footnote keys internally
        key = key.lower()
        content = self.render_children(token, state).strip()
        return f".. [#fn-{key}] {content}\n"

    def footnotes(self, token, state):
        """Render footnotes block"""
        content = self.render_children(token, state)
        if content:
            return "\n\n" + content
        return ""


def prepend_document_definitions(
    md: Markdown, result: str | list[dict[str, Any]], state: BlockState
) -> str | list[dict[str, Any]]:
    """Write the role and substitution definitions above the rendered body.

    The definitions come first so that an ``mdinclude`` directive further down
    the document sees them already defined.
    """
    renderer = cast("RestRenderer", md.renderer)
    substitution_definitions = [
        definition
        for name, definition in state.env.get("substitution_definitions", {}).items()
        if name not in renderer.existing_substitutions
    ]

    # The definitions hold inline text that was cleaned when it was recorded,
    # and escapes that docutils needs, so only the body is cleaned here.
    body = remove_redundant_inline_escapes(
        merge_adjacent_raw_html_roles("\n" + cast("str", result).lstrip("\n"))
    )

    if len(substitution_definitions) > 0:
        document = "\n" + "\n\n".join(substitution_definitions) + "\n\n" + body
    else:
        document = body

    role_definitions = list(state.env.get("role_definitions", {}).values())
    if len(role_definitions) > 0:
        document = "\n\n".join(role_definitions) + "\n\n" + document

    return document


def write_document_definitions(md: Markdown) -> None:
    """Register the hook that writes definitions above a rendered document.

    Mistune runs after-render hooks in registration order, so this plugin goes
    last, once the footnote plugin has rendered its own pass.
    """
    md.after_render_hooks.append(prepend_document_definitions)
