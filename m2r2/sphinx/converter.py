from __future__ import annotations

from typing import TYPE_CHECKING

from m2r2.m2r2 import M2R2
from m2r2.rst.renderer import RestRenderer

if TYPE_CHECKING:
    from docutils import nodes


class SphinxM2R2(M2R2):
    """Convert Markdown for insertion into a Sphinx document.

    The options come from the project's configuration, and the substitutions
    the document already defines are left out of the conversion's own.
    """

    def __init__(self, document: nodes.document) -> None:
        self.document = document
        config = document.settings.env.config
        super().__init__(
            no_underscore_emphasis=config.m2r_no_underscore_emphasis,
            inline_math=config.m2r_inline_math,
            parse_relative_links=config.m2r_parse_relative_links,
            anonymous_references=config.m2r_anonymous_references,
            use_mermaid=config.m2r_use_mermaid,
        )

    def build_rest_renderer(
        self,
        *,
        parse_relative_links: bool,
        anonymous_references: bool,
        use_mermaid: bool,
    ) -> RestRenderer:
        """Build a renderer that writes RST for the document being built."""
        return RestRenderer(
            parse_relative_links=parse_relative_links,
            anonymous_references=anonymous_references,
            use_mermaid=use_mermaid,
            is_sphinx=True,
            existing_substitutions=self.document.substitution_defs,
        )
