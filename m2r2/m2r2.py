from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import version
from typing import TYPE_CHECKING, Literal, cast

import mistune
from mistune.plugins.footnotes import footnotes
from mistune.plugins.formatting import strikethrough
from mistune.plugins.table import table

from m2r2.rst.plugins import (
    LITERAL_UNDERSCORE_PATTERN,
    configure_markdown_parser_for_rst,
    parse_literal_underscore,
)
from m2r2.rst.renderer import RestRenderer

if TYPE_CHECKING:
    from mistune.plugins import Plugin

__version__ = version("m2r2")


class BaseM2R2:
    """Convert Markdown documents using configurable RST rendering options."""

    def __init__(
        self,
        *,
        renderer: RestRenderer,
        plugins: Iterable[str | Plugin] | None = None,
        no_underscore_emphasis: bool = False,
        inline_math: Literal["legacy", "dollar"] | None = "legacy",
    ) -> None:
        """Initialize the Markdown parser with an RST renderer.

        Args:
            renderer: Renderer used for conversion and document assembly.
            plugins: Additional Mistune plugins.
            no_underscore_emphasis: Disable underscore-based emphasis.
            inline_math: Enable inline math with "legacy" or "dollar" syntax, or
                use None to disable it.
        """
        self.renderer = renderer

        if plugins is None:
            plugins = []
        else:
            plugins = list(plugins)

        # Create custom plugin function that respects options
        def custom_rst_directives(md):
            configure_markdown_parser_for_rst(md, inline_math=inline_math)
            if no_underscore_emphasis:
                md.inline.register(
                    "literal_underscore",
                    LITERAL_UNDERSCORE_PATTERN,
                    parse_literal_underscore,
                    before="emphasis",
                )

        plugins.extend([custom_rst_directives, table, footnotes, strikethrough])

        # Create markdown parser with RST directive support
        self.md = mistune.create_markdown(renderer=self.renderer, plugins=plugins)

    def parse(self, s: str) -> str:
        """Convert one Markdown document to RST."""
        rendered_body, markdown_state = self.md.parse(s)
        return self.renderer.finalize_document(cast(str, rendered_body), markdown_state)

    def __call__(self, s: str) -> str:
        return self.parse(s)


class M2R2(BaseM2R2):
    """Convert Markdown documents using configurable RST rendering options."""

    def __init__(
        self,
        plugins: Iterable[str | Plugin] | None = None,
        *,
        no_underscore_emphasis: bool = False,
        inline_math: Literal["legacy", "dollar"] | None = "legacy",
        parse_relative_links: bool = False,
        anonymous_references: bool = False,
        use_mermaid: bool = False,
    ) -> None:
        """Initialize a Markdown to reStructuredText converter.

        Args:
            plugins: Additional Mistune plugins.
            no_underscore_emphasis: Disable underscore-based emphasis.
            inline_math: Enable inline math with "legacy" or "dollar" syntax, or
                use None to disable it.
            parse_relative_links: Convert relative document links to ``:doc:`` roles.
            anonymous_references: Use anonymous RST references for plain link text.
            use_mermaid: Render Mermaid code blocks as directives.
        """
        renderer = RestRenderer(
            parse_relative_links=parse_relative_links,
            anonymous_references=anonymous_references,
            use_mermaid=use_mermaid,
        )
        super().__init__(
            renderer=renderer,
            plugins=plugins,
            no_underscore_emphasis=no_underscore_emphasis,
            inline_math=inline_math,
        )


def convert(
    text: str,
    *,
    no_underscore_emphasis: bool = False,
    inline_math: Literal["legacy", "dollar"] | None = "legacy",
    parse_relative_links: bool = False,
    anonymous_references: bool = False,
    use_mermaid: bool = False,
) -> str:
    """Convert a Markdown string to reStructuredText.

    Args:
        text: Markdown source text.
        no_underscore_emphasis: Disable underscore-based emphasis.
        inline_math: Enable inline math with "legacy" or "dollar" syntax, or
            use None to disable it.
        parse_relative_links: Convert relative document links to ``:doc:`` roles.
        anonymous_references: Use anonymous RST references for plain link text.
        use_mermaid: Render mermaid code blocks as directives.

    Returns:
        The converted reStructuredText string.
    """
    return M2R2(
        no_underscore_emphasis=no_underscore_emphasis,
        inline_math=inline_math,
        parse_relative_links=parse_relative_links,
        anonymous_references=anonymous_references,
        use_mermaid=use_mermaid,
    )(text)
