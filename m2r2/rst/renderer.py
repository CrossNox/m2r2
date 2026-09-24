from __future__ import annotations

import html
import os
import re
from collections.abc import Container, Iterable, Iterator
from contextlib import contextmanager
from hashlib import sha256
from typing import Any, ClassVar
from urllib.parse import urlparse

from docutils.utils import column_width, escape2null, unescape
from mistune.core import BlockState
from mistune.renderers.rst import RSTRenderer

RAW_HTML_ROLE_NAME = "raw-html-m2r"
RAW_HTML_ROLE_DEFINITION = f".. role:: {RAW_HTML_ROLE_NAME}(raw)\n   :format: html"


class SubstitutionNameCollision(Exception):
    """Report conflicting substitution definitions with the same name."""


def record_role_definition(
    state: BlockState, role_name: str, role_definition: str
) -> None:
    """Register a role definition for the rendered document."""
    state.env.setdefault("role_definitions", {})[role_name] = role_definition


def define_substitution(
    state: BlockState,
    name_prefix: str,
    directive: str,
    target_url: str | None = None,
) -> str:
    """Register a substitution and return a name based on its content.

    Reuse the name for identical definitions. If ``target_url`` is supplied,
    also register a hyperlink target with that name.
    """
    content_to_hash = directive if target_url is None else f"{directive}\n{target_url}"
    digest = sha256(content_to_hash.encode("utf-8")).hexdigest()
    substitution_name = f"{name_prefix}-{digest[:12]}"
    substitution_definition = f".. |{substitution_name}| {directive}"
    if target_url is not None:
        substitution_definition += f"\n.. _{substitution_name}: {target_url}"

    substitution_definitions = state.env.setdefault("substitution_definitions", {})
    if (
        substitution_definitions.get(substitution_name, substitution_definition)
        != substitution_definition
    ):
        raise SubstitutionNameCollision(
            f"Two substitutions want the name {substitution_name}:\n"
            f"{substitution_definitions[substitution_name]}\n{substitution_definition}"
        )
    substitution_definitions[substitution_name] = substitution_definition

    return substitution_name


@contextmanager
def rendering_link_text(state: BlockState) -> Iterator[None]:
    """Mark the current rendering context as link text."""
    state.env["inside_link_text"] = True
    yield
    state.env["inside_link_text"] = False


def is_inside_link_text(state: BlockState) -> bool:
    return state.env.get("inside_link_text", False)


@contextmanager
def rendering_heading(state: BlockState) -> Iterator[None]:
    """Mark the current rendering context as a heading."""
    state.env["inside_heading"] = True
    yield
    state.env["inside_heading"] = False


def flatten_to_plain_text(token: dict[str, Any]) -> str:
    """Extract plain text from an inline token and its children."""
    token_type = token["type"]
    if token_type in ("text", "codespan", "standalone_hyperlink"):
        return str(token.get("raw", ""))
    if token_type == "inline_math":
        return str(token["math"])
    if token_type in ("rest_role", "rest_link"):
        return extract_visible_rst_token_text(token)
    if token_type == "rst_footnote_ref":
        return str(token["text"])
    if token_type == "footnote_ref":
        return f"[{str(token['raw']).lower()}]"
    if token_type == "eol_literal_marker":
        return str(token["marker"])
    if token_type == "inline_html":
        # Mistune emits tags separately from their text.
        return ""
    if token_type in ("softbreak", "linebreak"):
        return " "
    if "children" in token:
        return "".join(flatten_to_plain_text(child) for child in token["children"])
    raise ValueError(f"Cannot flatten inline token {token_type!r}")


def extract_visible_rst_token_text(token: dict[str, Any]) -> str:
    """Extract role content, stripping explicit targets only from references.

    Built-in Sphinx reference roles accept a title followed by a target in
    angle brackets. Ordinary roles keep their entire body, including comparisons.
    """
    prefix, body, suffix = str(token["text"]).split("`", 2)
    role_name = (prefix + suffix).strip(":").split(":")[-1]
    if (
        token["type"] == "rest_link"
        or role_name
        in (
            "any doc download eq numref ref term token keyword option envvar "
            "mod func data const class meth attr exc obj "
            "member var type macro enumerator struct union enum expr "
            "function method attribute module directive role"
        ).split()
    ):
        title, separator, target = body.rpartition(" <")
        if separator != "" and target.endswith(">"):
            return title
    return body


def escape_role_title(text: str) -> str:
    """Escape characters that would end or alter an RST role's title."""
    return text.replace("\\", "\\\\").replace("`", "\\`")


def remove_footnote_references(token: dict[str, Any]) -> list[dict[str, Any]]:
    """Remove footnote references from a token's children and return them in order."""
    removed: list[dict[str, Any]] = []
    children = token.get("children")
    if children is None:
        return removed

    kept = []
    for child in children:
        if child["type"] in ("footnote_ref", "rst_footnote_ref"):
            removed.append(child)
            continue
        removed.extend(remove_footnote_references(child))
        kept.append(child)
    token["children"] = kept

    return removed


def merge_adjacent_raw_html_roles(text: str) -> str:
    """Join raw HTML roles that mistune splits across tokens."""
    # The middle group accepts escaped characters, but stops at line boundaries
    # and inline markup that must still be parsed as RST.
    pattern = re.compile(
        rf":{RAW_HTML_ROLE_NAME}:`([^`]+)`\\ "
        rf"((?:\\[^\n]|[^\\\n`*|])+?)\\ :{RAW_HTML_ROLE_NAME}:`([^`]+)`"
    )

    while (match := pattern.search(text)) is not None:
        plain_text = unescape(escape2null(match[2]))
        html_text = html.escape(plain_text, quote=False).replace("`", "&#96;")
        replacement = f":{RAW_HTML_ROLE_NAME}:`{match[1]}{html_text}{match[3]}`"
        text = text[: match.start()] + replacement + text[match.end() :]

    return text


def remove_redundant_inline_escapes(text: str) -> str:
    """Remove escaped spaces where RST needs no inline markup separator."""
    return (
        text.replace("\\ \n", "\n")
        .replace("\n\\ ", "\n")
        .replace(" \\ ", " ")
        .replace("\\  ", " ")
        .replace("\\ .", ".")
    )


class RestRenderer(RSTRenderer):
    """Render Markdown tokens as reStructuredText."""

    indent = " " * 3
    unlabeled_code_block_start = "\n.. code-block::\n\n"
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
        existing_substitutions: Container[str] = (),
    ) -> None:
        self.parse_relative_links = parse_relative_links
        self.anonymous_references = anonymous_references
        self.use_mermaid = use_mermaid
        self.existing_substitutions = existing_substitutions
        super().__init__()

    def iter_tokens(
        self, tokens: Iterable[dict[str, Any]], state: BlockState
    ) -> Iterable[str]:
        """Render tokens while preserving blank lines around RST directives."""
        prev_tok = None
        pending_blank_lines = 0

        for tok in tokens:
            if tok["type"] == "blank_line":
                pending_blank_lines += 1
                continue

            if pending_blank_lines > 0 and (
                tok["type"] == "directive"
                or (
                    prev_tok is not None
                    and prev_tok["type"] == "directive"
                    and not prev_tok.get("raw", "").endswith("\n\n")
                )
            ):
                yield "\n" * pending_blank_lines
            pending_blank_lines = 0

            tok["prev"] = prev_tok
            prev_tok = tok
            yield self.render_token(tok, state)

    def __call__(self, tokens: Iterable[dict[str, Any]], state: BlockState) -> str:
        """Render a token sequence without emitting document definitions.

        Call ``finalize_document`` after all token sequences have been rendered.
        """
        return self.render_tokens(tokens, state)

    def thematic_break(self, token, state):
        """Render a thematic break as an RST transition."""
        return "\n----\n"

    def linebreak(self, token, state):
        """Render a hard line break as HTML."""
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
        """Preserve a soft line break as a newline."""
        return "\n"

    def _indent_block(self, block):
        return "\n".join(
            self.indent + line if line else "" for line in block.splitlines()
        )

    def _raw_html(self, raw, state):
        record_role_definition(state, RAW_HTML_ROLE_NAME, RAW_HTML_ROLE_DEFINITION)
        raw = raw.replace("`", "&#96;")
        return rf"\ :{RAW_HTML_ROLE_NAME}:`{raw}`\ "

    def block_code(self, token: dict[str, Any], state: BlockState):
        code_text = token.get("raw", "")
        info = token.get("attrs", {}).get("info", "")
        lang = info.split()[0] if info else ""

        if lang == "math":
            first_line = "\n.. math::\n\n"
        elif lang == "mermaid" and self.use_mermaid:
            first_line = "\n.. mermaid::\n\n"
        elif lang:
            first_line = f"\n.. code-block:: {lang}\n\n"
        else:
            first_line = self.unlabeled_code_block_start
        return first_line + self._indent_block(code_text) + "\n"

    def directive(self, token, state):
        """Preserve an RST directive and any trailing blank lines."""
        text = token.get("raw", "")

        return text if text.endswith("\n\n") else text.rstrip("\n")

    def rest_role(self, token, state):
        """Preserve an RST inline construct verbatim."""
        return token.get("text", "")

    rest_link = rest_role
    rst_footnote_ref = rest_role

    def inline_math(self, token, state):
        """Render inline math as an RST math role."""
        math = token.get("math", "")
        return rf"\ :math:`{math}`\ "

    def eol_literal_marker(self, token, state):
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
        """Render a link followed by any footnote references from its label.

        ``emphasis_marker`` is the RST emphasis around the link, empty for none.
        """
        footnote_references = remove_footnote_references(token)
        rendered = self.render_linked_text(token, state, emphasis_marker)
        return rendered + "".join(
            self.render_token(reference, state) for reference in footnote_references
        )

    def render_linked_text(
        self, token: dict[str, Any], state: BlockState, emphasis_marker: str
    ) -> str:
        """Render a link using the configured reference format."""
        link_destination = token["attrs"]["url"]
        link_label_tokens = token["children"]
        if len(link_label_tokens) == 1 and link_label_tokens[0]["type"] == "image":
            return self.render_image(
                link_label_tokens[0], state, target=link_destination
            )

        destination_parts = urlparse(link_destination)
        if (
            not self.parse_relative_links
            or destination_parts.scheme != ""
            or destination_parts.netloc != ""
            or destination_parts.path == ""
        ):
            return self.render_hyperlink_reference(
                token, state, link_destination, emphasis_marker
            )

        # Document link, e.g. [text](page.md). A :doc: role carries no fragment,
        # so outside Sphinx a link to page.md#anchor loses its anchor.
        escaped_link_label = escape_role_title(flatten_to_plain_text(token))
        target_docname = os.path.splitext(destination_parts.path)[0]
        return rf"\ :doc:`{escaped_link_label} <{target_docname}>`\ "

    def render_hyperlink_reference(
        self, token: dict[str, Any], state: BlockState, url: str, emphasis_marker: str
    ) -> str:
        """Render an RST hyperlink with a formatted label.

        Flatten label markup in headings.
        """
        if state.env.get("inside_heading", False):
            # docutils names a section after the text of its title as the title
            # reads when parsed, so a substitution reference there would put its
            # own name in the section id. The anonymous form writes no target,
            # which would otherwise claim the id the section wants.
            return rf"\ `{flatten_to_plain_text(token)} <{url}>`__\ "

        holds_only_text = all(
            child["type"] in ("text", "softbreak") for child in token["children"]
        )
        if holds_only_text:
            text = self.render_children(token, state)
            if len(text.strip()) == 0:
                # An empty link has nothing to emphasize and nothing to show.
                # The escaped space keeps docutils reading a reference, and the
                # anonymous form keeps two of them from claiming one name.
                return rf"\ `\ <{url}>`__\ "
            if emphasis_marker == "":
                underscore = "__" if self.anonymous_references else "_"
                return rf"\ `{text} <{url}>`{underscore}\ "

        # RST cannot nest inline markup in a hyperlink reference, so the text
        # goes in a substitution and a named target makes it a link. The
        # replacement opens with an escaped space, which docutils drops, so that
        # text starting with "- " or "1. " cannot turn into a list.
        with rendering_link_text(state):
            if emphasis_marker == "":
                text = self.render_children(token, state)
            else:
                text = self.render_emphasis(token, state, emphasis_marker)
        replacement = remove_redundant_inline_escapes(
            text.removeprefix("\\ ").removesuffix("\\ ")
        )
        replacement = merge_adjacent_raw_html_roles(replacement).replace("\n", " ")
        link_substitution_name = define_substitution(
            state, "m2r-link", f"replace:: \\ {replacement}", target_url=url
        )
        return rf"\ |{link_substitution_name}|_\ "

    def heading(self, token, state):
        """Render a heading with an underline sized to its display width."""
        level = token["attrs"]["level"]

        with rendering_heading(state):
            text = self.render_children(token, state)

        if level in self.hmarks:
            mark = self.hmarks[level]
            # Use column_width for proper multibyte character counting
            width = column_width(text)
            return f"\n{text}\n{mark * width}\n"
        return f"\n{text}\n"

    def rest_code_block(self, token, state):
        """Consume a standalone literal block marker without rendering it."""
        return "\n\n"

    def github_alert(self, token, state):
        """Render a GitHub alert as an RST admonition."""
        children = self.render_children(token, state).strip()
        if children == "":
            # RST admonitions require content, even for an empty Markdown alert.
            children = ".."
        indented = self._indent_block(children)
        kind = token["attrs"]["kind"]
        return f"\n.. {kind}::\n\n{indented}\n\n"

    def block_quote(self, token, state):
        """Render a block quote as indented RST."""
        children = self.render_children(token, state)
        # Indent all lines by 3 spaces and add blank line before/after
        indented = self._indent_block(children.strip())
        return f"\n..\n\n{indented}\n\n"

    def text(self, token: dict[str, Any], state: BlockState) -> str:
        """Escape parsed Markdown text for its RST context."""
        text = token["raw"].replace("\\", "\\\\").replace("|", "\\|")
        if is_inside_link_text(state):
            return re.sub(r"[:@_]", r"\\\g<0>", text)
        return text

    def image(self, token: dict[str, Any], state: BlockState) -> str:
        """Render an inline image with a source link unless already inside a link."""
        image_link_target = (
            None if is_inside_link_text(state) else token["attrs"]["url"]
        )
        return self.render_image(token, state, target=image_link_target)

    def render_image(
        self,
        token: dict[str, Any],
        state: BlockState,
        target: str | None,
        *,
        inline: bool = True,
    ) -> str:
        """Render an image as a block directive or an inline substitution."""
        if not inline:
            image_directive = self.build_image_directive(token, target)
            return f"\n\n.. {image_directive}\n\n"
        image_substitution_name = self.define_image_substitution(token, state, target)
        return rf"\ |{image_substitution_name}|\ "

    def build_image_directive(
        self, token: dict[str, Any], image_link_target: str | None
    ) -> str:
        """Build an image directive from its URI, link target, and alt text."""
        image_uri = token["attrs"]["url"]
        image_alt_text = flatten_to_plain_text(token).replace("\n", " ")
        image_directive = f"image:: {image_uri}"
        if image_link_target is not None:
            image_directive += f"\n   :target: {image_link_target}"
        image_directive += f"\n   :alt: {image_alt_text}"
        return image_directive

    def define_image_substitution(
        self,
        token: dict[str, Any],
        state: BlockState,
        image_link_target: str | None,
    ) -> str:
        """Define an inline image and return its substitution name."""
        return define_substitution(
            state,
            "m2r-image",
            self.build_image_directive(token, image_link_target),
        )

    def block_html(self, token, state):
        """Render block HTML as an RST raw directive."""
        raw = token.get("raw", "").rstrip("\n")
        indented = self._indent_block(raw)
        return f"\n\n.. raw:: html\n\n{indented}\n\n"

    def inline_html(self, token, state):
        """Render inline HTML as an RST raw role."""
        raw = token.get("raw", "")
        return self._raw_html(raw, state)

    def codespan(self, token, state):
        """Render inline code as an RST literal or raw HTML.

        Trim surrounding whitespace from nonempty code spans. Preserve spans
        containing only whitespace as HTML.
        """
        raw = token.get("raw", "")
        code = raw.strip()
        if code == "":
            # RST inline literals cannot contain only whitespace.
            return self._raw_html(f"<code>{html.escape(raw)}</code>", state)
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
        """Wrap rendered inline content in HTML deletion tags."""
        footnote_references = remove_footnote_references(token)
        opening_del_name = define_substitution(
            state, "m2r-del-open", "raw:: html\n\n   <del>"
        )
        closing_del_name = define_substitution(
            state, "m2r-del-close", "raw:: html\n\n   </del>"
        )
        struck_content = (
            rf"\ |{opening_del_name}|\ "
            + self.render_children(token, state)
            + rf"\ |{closing_del_name}|\ "
        )
        return struck_content + "".join(
            self.render_token(reference, state) for reference in footnote_references
        )

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
        """Render a table as an RST list-table directive."""
        children = token.get("children", [])
        has_header = any(child["type"] == "table_head" for child in children)
        header_option = "   :header-rows: 1\n\n" if has_header else "\n"
        body = self.render_children(token, state)
        return f"\n.. list-table::\n{header_option}{body}\n"

    def table_head(self, token, state):
        """Render table cells as a row in an RST list-table."""
        cells = token.get("children", [])
        if not cells:
            return ""

        result = "   * - " + self.render_children(cells[0], state).strip() + "\n"
        for cell in cells[1:]:
            result += "     - " + self.render_children(cell, state).strip() + "\n"
        return result

    def table_body(self, token, state):
        return self.render_children(token, state)

    table_row = table_head

    # Footnote rendering methods
    def footnote_ref(self, token, state):
        """Render an automatically numbered RST footnote reference."""
        # Key can be in attrs or directly in raw
        attrs = token.get("attrs", {})
        key = token.get("raw", attrs.get("key", str(attrs.get("index", ""))))
        # Normalize to lowercase: mistune v3 uppercases footnote keys internally
        key = key.lower()
        return rf"\ [#fn-{key}]_\ "

    def footnote_item(self, token, state):
        """Render an RST footnote definition."""
        attrs = token.get("attrs", {})
        key = attrs.get("key", str(attrs.get("index", "")))
        # Normalize to lowercase: mistune v3 uppercases footnote keys internally
        key = key.lower()
        content = self.render_children(token, state).strip()
        return f".. [#fn-{key}] {content}\n"

    def footnotes(self, token, state):
        content = self.render_children(token, state)
        return "\n\n" + content if content else ""

    def finalize_document(self, rendered_body: str, markdown_state: BlockState) -> str:
        """Assemble the rendered document with its required definitions."""
        role_definitions = list(markdown_state.env.get("role_definitions", {}).values())
        substitution_definitions = [
            substitution_definition
            for substitution_name, substitution_definition in markdown_state.env.get(
                "substitution_definitions", {}
            ).items()
            if substitution_name not in self.existing_substitutions
        ]

        rest_body = remove_redundant_inline_escapes(
            merge_adjacent_raw_html_roles("\n" + rendered_body.lstrip("\n"))
        )

        parts = []
        if len(role_definitions) > 0:
            parts.append("\n\n".join(role_definitions))
        if len(substitution_definitions) > 0:
            parts.append("\n" + "\n\n".join(substitution_definitions))

        parts.append(rest_body)
        return "\n\n".join(parts)
