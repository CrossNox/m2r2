from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import version
from typing import TYPE_CHECKING, cast

import mistune
from mistune.plugins.footnotes import footnotes
from mistune.plugins.formatting import strikethrough
from mistune.plugins.table import table

from m2r2.rst.plugins import (
    LITERAL_UNDERSCORE_PATTERN,
    configure_markdown_parser_for_rst,
    parse_literal_underscore,
)
from m2r2.rst.renderer import RestRenderer, register_document_definition_hook

if TYPE_CHECKING:
    from mistune.plugins import Plugin

__version__ = version("m2r2")


class M2R2:
    """Convert Markdown documents using configurable RST rendering options."""

    def __init__(
        self,
        plugins: Iterable[str | Plugin] | None = None,
        *,
        no_underscore_emphasis: bool = False,
        disable_inline_math: bool = False,
        parse_relative_links: bool = False,
        anonymous_references: bool = False,
        use_mermaid: bool = False,
    ) -> None:
        self.renderer = self.build_rest_renderer(
            parse_relative_links=parse_relative_links,
            anonymous_references=anonymous_references,
            use_mermaid=use_mermaid,
        )

        if plugins is None:
            plugins = []
        else:
            plugins = list(plugins)

        # Create custom plugin function that respects options
        def custom_rst_directives(md):
            configure_markdown_parser_for_rst(md)
            if disable_inline_math and "inline_math" in md.inline.rules:
                md.inline.rules.remove("inline_math")
            if no_underscore_emphasis:
                md.inline.register(
                    "literal_underscore",
                    LITERAL_UNDERSCORE_PATTERN,
                    parse_literal_underscore,
                    before="emphasis",
                )

        # The definition hook goes last so it runs after the one
        # the footnote plugin registers.
        plugins.extend(
            [
                custom_rst_directives,
                table,
                footnotes,
                strikethrough,
                register_document_definition_hook,
            ]
        )

        # Create markdown parser with RST directive support
        self.md = mistune.create_markdown(renderer=self.renderer, plugins=plugins)

    def build_rest_renderer(
        self,
        *,
        parse_relative_links: bool,
        anonymous_references: bool,
        use_mermaid: bool,
    ) -> RestRenderer:
        """Build the renderer that turns Markdown tokens into RST."""
        return RestRenderer(
            parse_relative_links=parse_relative_links,
            anonymous_references=anonymous_references,
            use_mermaid=use_mermaid,
        )

    def parse(self, s: str) -> str:
        """Convert one Markdown document to RST."""
        return cast(str, self.md(s))

    def __call__(self, s: str) -> str:
        return self.parse(s)


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
        parse_relative_links: Convert relative document links to ``:doc:`` roles.
        anonymous_references: Use anonymous RST references for plain link text.
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
