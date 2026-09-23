from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from m2r2.m2r2 import M2R2
from m2r2.rst.renderer import RestRenderer

if TYPE_CHECKING:
    from docutils import nodes
    from mistune.core import BlockState


class SphinxRestRenderer(RestRenderer):
    """Render Markdown with image paths relative to the Sphinx document."""

    def __init__(
        self,
        document: nodes.document,
        source_path: str,
        *,
        parse_relative_links: bool,
        anonymous_references: bool,
        use_mermaid: bool,
    ) -> None:
        self.source_directory = os.path.dirname(os.path.abspath(source_path))
        self.document_directory = os.path.dirname(os.path.abspath(document["source"]))
        super().__init__(
            parse_relative_links=parse_relative_links,
            anonymous_references=anonymous_references,
            use_mermaid=use_mermaid,
            is_sphinx=True,
            existing_substitutions=document.substitution_defs,
        )

    def resolve_image_path(self, source: str) -> str:
        """Resolve a local image from its Markdown file to the Sphinx document."""
        url = urlsplit(source)
        if (
            url.scheme != ""
            or url.netloc != ""
            or url.path == ""
            or source.startswith("/")
        ):
            return source
        path = os.path.relpath(
            os.path.join(self.source_directory, url.path), self.document_directory
        ).replace(os.sep, "/")
        return url._replace(path=path).geturl()

    def render_image(
        self,
        token: dict[str, Any],
        state: BlockState,
        target: str | None,
        *,
        inline: bool = True,
    ) -> str:
        """Resolve an image path before creating its directive or substitution."""
        source = token["attrs"]["url"]
        resolved = self.resolve_image_path(source)
        if target == source:
            target = resolved
        token = {**token, "attrs": {**token["attrs"], "url": resolved}}
        return super().render_image(token, state, target, inline=inline)


class SphinxM2R2(M2R2):
    """Convert Markdown for insertion into a Sphinx document.

    The options come from the project's configuration, and the substitutions
    the document already defines are left out of the conversion's own.
    """

    def __init__(
        self, document: nodes.document, *, source_path: str | None = None
    ) -> None:
        self.document = document
        self.source_path = document["source"] if source_path is None else source_path
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
        return SphinxRestRenderer(
            self.document,
            self.source_path,
            parse_relative_links=parse_relative_links,
            anonymous_references=anonymous_references,
            use_mermaid=use_mermaid,
        )
