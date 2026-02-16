import os
from collections.abc import Iterable
from typing import Any, ClassVar
from urllib.parse import urlparse

from docutils.utils import column_width
from mistune.core import BlockState
from mistune.renderers.rst import RSTRenderer


class RestRenderer(RSTRenderer):
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
    ):
        self.parse_relative_links = parse_relative_links
        self.anonymous_references = anonymous_references
        self.use_mermaid = use_mermaid
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

            prev_tok = tok
            yield self.render_token(tok, state)

    def __call__(self, tokens, state):
        """Override to avoid stripping trailing newlines"""
        state.env["inline_images"] = []
        out = self.render_tokens(tokens, state)
        # Handle inline image references
        refs = list(self.render_referrences(state))
        if refs:
            out += "\n\n".join(refs) + "\n"
        return out

    def finalize(self, data):
        return "".join(x for x in data if x is not None)

    def thematic_break(self, token, state):
        """Override to use shorter horizontal rule"""
        return "\n----\n"

    def linebreak(self, token, state):
        """Override to use raw HTML format instead of line blocks"""
        return "\\ :raw-html-m2r:`<br>`\n"

    def paragraph(self, token, state):
        """Override to preserve line breaks in paragraphs"""
        text = self.render_children(token, state)
        # Check if this paragraph only contains block-level elements that handle their own spacing
        if text.strip().startswith("\n\n") or text.startswith("\n\n.. image::"):
            return text
        return f"\n{text}\n"

    def softbreak(self, token, state):
        """Override to preserve line breaks instead of converting to spaces"""
        return "\n"

    def _indent_block(self, block):
        return "\n".join(
            self.indent + line if line else "" for line in block.splitlines()
        )

    def _raw_html(self, html):
        return rf"\ :raw-html-m2r:`{html}`\ "

    def block_code(self, token: dict[str, Any], state: BlockState):
        # Extract code content from token
        code_text = token.get("raw", "")

        # Extract language info from token attributes
        lang = token.get("attrs", {}).get("info", "") if "attrs" in token else ""

        if lang == "math":
            first_line = "\n.. math::\n\n"
        elif lang == "mermaid" and self.use_mermaid:
            first_line = "\n.. mermaid::\n\n"
        elif lang:
            first_line = f"\n.. code-block:: {lang}\n\n"
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

    def image_link(self, token, state):
        """Render image link"""
        alt = token.get("alt", "")
        url = token.get("url", "")
        target = token.get("target", "")
        return f"\n\n.. image:: {url}\n   :target: {target}\n   :alt: {alt}\n\n"

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

    def link(self, token, state):
        """Override to use single underscore for named references"""
        # Extract URL from token attrs in mistune v3
        if "attrs" in token and "url" in token["attrs"]:
            link = token["attrs"]["url"]
        else:
            link = token.get("url", "")

        if "attrs" in token and "title" in token["attrs"]:
            title = token["attrs"]["title"]
        else:
            title = token.get("title", "")

        text = self.render_children(token, state)

        if self.anonymous_references:
            underscore = "__"
        else:
            underscore = "_"

        if title:
            return self._raw_html(f'<a href="{link}" title="{title}">{text}</a>')

        if not self.parse_relative_links:
            return f"`{text} <{link}>`{underscore}"

        url_info = urlparse(link)
        if url_info.scheme:
            return f"`{text} <{link}>`{underscore}"

        link_type = "doc"
        anchor = url_info.fragment
        if url_info.fragment:
            if url_info.path:
                # Can't link to anchors via doc directive.
                anchor = ""
            else:
                # Example: [text](#anchor)
                link_type = "ref"
        doc_link = f"{os.path.splitext(url_info.path)[0]}{anchor}"
        # splitext approach works whether or not path is set. It
        # will return an empty string if unset, which leads to
        # anchor only ref.
        return f":{link_type}:`{text} <{doc_link}>`"

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

    def image(self, token, state):
        """Render image"""
        # Extract from our custom token structure
        src = token.get("src", "")
        alt = token.get("alt", "")

        if not src:
            return ""

        # RST image directive format
        lines = [
            "",
            f".. image:: {src}",
            f"   :target: {src}",
        ]
        if alt:
            lines.append(f"   :alt: {alt}")
        lines.append("")
        return "\n".join(lines)

    def block_html(self, token, state):
        """Render block HTML as raw HTML directive"""
        html = token.get("raw", "").rstrip("\n")
        indented = self._indent_block(html)
        return f"\n\n.. raw:: html\n\n{indented}\n\n"

    def inline_html(self, token, state):
        """Render inline HTML as raw HTML role"""
        html = token.get("raw", "")
        return self._raw_html(html)

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
            # Use raw HTML for code with backticks
            return self._raw_html(
                f'<code class="docutils literal">'
                f'<span class="pre">{code.replace("`", "&#96;")}</span>'
                "</code>"
            )

    def emphasis(self, token, state):
        """Override to handle custom emphasis tokens"""
        if "raw" in token:
            # For our custom no_underscore_emphasis tokens
            text = token["raw"]
        else:
            # For standard tokens, use children
            text = self.render_children(token, state)
        return f"*{text}*"

    def strong(self, token, state):
        """Override to handle custom strong tokens"""
        if "raw" in token:
            # For our custom no_underscore_emphasis tokens
            text = token["raw"]
        else:
            # For standard tokens, use children
            text = self.render_children(token, state)
        return f"**{text}**"

    def block_text(self, token, state):
        """Override to omit trailing newline that the parent adds.

        The parent's ``+ "\\n"`` would break list item formatting.
        """
        return self.render_children(token, state)

    def list(self, token, state):
        """Render list with proper RST formatting"""
        attrs = token.get("attrs", {})
        ordered = attrs.get("ordered", False)
        tight = token.get("tight", True)

        # Track list depth and cumulative indent for proper nesting
        state.env.setdefault("list_depth", 0)
        state.env.setdefault("list_indent", "")

        current_depth = state.env["list_depth"]
        current_indent = state.env["list_indent"]
        state.env["list_depth"] += 1

        # Calculate indent for nested content based on marker width
        # Ordered lists use "#. " (3 chars), unordered use "* " (2 chars)
        marker_width = 3 if ordered else 2
        state.env["list_indent"] = current_indent + " " * marker_width

        # Process list items
        items = []
        for i, item_token in enumerate(token["children"]):
            if item_token["type"] == "list_item":
                is_last_item = i == len(token["children"]) - 1
                item_content = self._render_list_item(
                    item_token, state, ordered, current_indent, tight, is_last_item
                )
                items.append(item_content)

        state.env["list_depth"] -= 1
        state.env["list_indent"] = current_indent

        # Join items
        result = "".join(items)

        # Add leading spacing for top-level lists
        if current_depth == 0:
            result = "\n\n" + result
        elif not tight:
            result = "\n" + result

        return result

    def _render_list_item(
        self, token, state, ordered, indent, tight, is_last_item=False
    ):
        """Render a single list item"""
        # Choose marker
        if ordered:
            marker = "#. "
        else:
            marker = "* "

        # Separate text content from nested lists
        text_parts = []
        nested_lists = []
        has_nested_list = False

        for child_token in token["children"]:
            if child_token["type"] == "list":
                has_nested_list = True
                nested_content = self.render_token(child_token, state)
                nested_lists.append(nested_content)
            elif child_token["type"] != "blank_line":
                text_parts.append(self.render_token(child_token, state))

        # Process text content
        text_content = "".join(text_parts).rstrip("\n")
        if not text_content and not has_nested_list:
            return indent + marker + "\n"

        # Handle multi-line text content with proper indentation
        if text_content:
            lines = text_content.split("\n")
            first_line = lines[0] if lines else ""

            # Build result starting with the marker and first line
            result = indent + marker + first_line + "\n"

            # Add continuation lines with proper indentation
            continuation_indent = indent + " " * len(marker)
            for line in lines[1:]:
                if line.strip():  # Only indent non-empty lines
                    result += continuation_indent + line + "\n"
                else:
                    result += "\n"
        else:
            result = indent + marker + "\n"

        # Add nested content with proper spacing
        if nested_lists:
            # Add blank line before nested lists
            result += "\n"
            for nested in nested_lists:
                # The nested content should already be properly indented
                result += nested.rstrip("\n") + "\n"
            # Add blank line after nested lists only if this isn't the last item at this level
            if not is_last_item:
                result += "\n"

        return result

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

    def table_head(self, token, state):
        """Render table header"""
        cells = token.get("children", [])
        if not cells:
            return ""

        result = "   * - " + self.render_children(cells[0], state).strip() + "\n"
        for cell in cells[1:]:
            result += "     - " + self.render_children(cell, state).strip() + "\n"
        return result

    def table_body(self, token, state):
        """Render table body"""
        result = ""
        for row in token.get("children", []):
            result += self.table_row(row, state)
        return result

    def table_row(self, token, state):
        """Render table row"""
        cells = token.get("children", [])
        if not cells:
            return ""

        result = "   * - " + self.render_children(cells[0], state).strip() + "\n"
        for cell in cells[1:]:
            result += "     - " + self.render_children(cell, state).strip() + "\n"
        return result

    def table_cell(self, token, state):
        """Render table cell"""
        return self.render_children(token, state)

    # Footnote rendering methods
    def footnote_ref(self, token, state):
        """Render footnote reference"""
        # Key can be in attrs or directly in raw
        attrs = token.get("attrs", {})
        key = token.get("raw", attrs.get("key", str(attrs.get("index", ""))))
        # Use lowercase for consistency with original m2r behavior
        key = key.lower()
        return rf"\ [#fn-{key}]_\ "

    def footnote_item(self, token, state):
        """Render footnote item"""
        attrs = token.get("attrs", {})
        key = attrs.get("key", str(attrs.get("index", "")))
        # Use lowercase for consistency with original m2r behavior
        key = key.lower()
        content = self.render_children(token, state).strip()
        return f".. [#fn-{key}] {content}\n"

    def footnotes(self, token, state):
        """Render footnotes block"""
        content = self.render_children(token, state)
        if content:
            return "\n\n" + content
        return ""
