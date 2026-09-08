from __future__ import annotations

import re
from collections.abc import Iterable
from importlib.metadata import version
from typing import TYPE_CHECKING, cast

import mistune
from mistune.core import BaseRenderer
from mistune.plugins.footnotes import footnotes
from mistune.plugins.formatting import strikethrough
from mistune.plugins.table import table

from m2r2.rst.plugins import rst_directives
from m2r2.rst.renderer import RestRenderer

if TYPE_CHECKING:
    from mistune.plugins import Plugin

__version__ = version("m2r2")

# Keep Mistune's recursive emphasis parser, restricting only its start marker.
_ASTERISK_EMPHASIS = r"\*{1,3}(?=[^\s*])"


# RST role definition prepended to output when raw HTML is used
PROLOG = """\
.. role:: raw-html-m2r(raw)
   :format: html

"""

# Pattern to merge adjacent raw-html-m2r roles on the same line.
# Matches: :raw-html-m2r:`<tag>`\ text\ :raw-html-m2r:`</tag>`
# and combines into: :raw-html-m2r:`<tag>text</tag>`
# The middle group excludes backslashes and newlines to prevent
# cross-line merges that would consume unrelated RST content.
_RAW_HTML_MERGE_PATTERN = re.compile(
    r":raw-html-m2r:`([^`]+)`\\ ([^\\\n]+)\\ :raw-html-m2r:`([^`]+)`"
)


class M2R2:
    """Convert Markdown documents using configurable RST rendering options."""

    def __init__(
        self,
        renderer: BaseRenderer | None = None,
        plugins: Iterable[str | Plugin] | None = None,
        *,
        no_underscore_emphasis: bool = False,
        disable_inline_math: bool = False,
        parse_relative_links: bool = False,
        anonymous_references: bool = False,
        use_mermaid: bool = False,
    ) -> None:
        if renderer is None:
            renderer = RestRenderer(
                parse_relative_links=parse_relative_links,
                anonymous_references=anonymous_references,
                use_mermaid=use_mermaid,
            )
        self.renderer = renderer

        if plugins is None:
            plugins = []
        else:
            plugins = list(plugins)

        # Create custom plugin function that respects options
        def custom_rst_directives(md):
            rst_directives(md)
            if disable_inline_math and "inline_math" in md.inline.rules:
                md.inline.rules.remove("inline_math")
            if no_underscore_emphasis:
                md.inline.specification["emphasis"] = _ASTERISK_EMPHASIS

        plugins.extend([custom_rst_directives, table, footnotes, strikethrough])

        # Create markdown parser with RST directive support
        self.md = mistune.create_markdown(renderer=renderer, plugins=plugins)

    def parse(self, s: str) -> str:
        """Convert one Markdown document to RST."""
        output = cast(str, self.md(s))
        return self.post_process(output)

    def __call__(self, s: str) -> str:
        return self.parse(s)

    def post_process(self, text: str) -> str:
        """Normalize inline RST boundaries and define the raw HTML role."""
        # Ensure output starts with exactly one leading newline
        text = "\n" + text.lstrip("\n")

        # Merge adjacent raw-html-m2r roles that mistune v3 splits across tokens.
        # e.g. :raw-html-m2r:`<s>`\ text\ :raw-html-m2r:`</s>`
        #   -> :raw-html-m2r:`<s>text</s>`
        while _RAW_HTML_MERGE_PATTERN.search(text) is not None:
            text = _RAW_HTML_MERGE_PATTERN.sub(r":raw-html-m2r:`\1\2\3`", text)

        # Clean up RST escape sequences ("\ ") inserted by the renderer around
        # inline roles. These backslash-space pairs are needed in RST to separate
        # inline markup from surrounding text, but become redundant at line
        # boundaries, before periods, or between spaces.
        output = (
            text.replace("\\ \n", "\n")
            .replace("\n\\ ", "\n")
            .replace(" \\ ", " ")
            .replace("\\  ", " ")
            .replace("\\ .", ".")
        )

        if ":raw-html-m2r:" in output:
            return PROLOG + output
        return output


def convert(
    text: str,
    *,
    no_underscore_emphasis: bool = False,
    disable_inline_math: bool = False,
    parse_relative_links: bool = False,
    anonymous_references: bool = False,
    use_mermaid: bool = False,
) -> str:
    """Convert a Markdown string to reStructuredText.

    Args:
        text: Markdown source text.
        no_underscore_emphasis: Disable underscore-based emphasis.
        disable_inline_math: Disable inline math parsing.
        parse_relative_links: Convert relative links to RST references.
        anonymous_references: Use anonymous RST references.
        use_mermaid: Render mermaid code blocks as directives.

    Returns:
        The converted reStructuredText string.
    """
    return M2R2(
        no_underscore_emphasis=no_underscore_emphasis,
        disable_inline_math=disable_inline_math,
        parse_relative_links=parse_relative_links,
        anonymous_references=anonymous_references,
        use_mermaid=use_mermaid,
    )(text)
