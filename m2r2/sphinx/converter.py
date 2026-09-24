from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse, urlsplit

from m2r2.m2r2 import BaseM2R2
from m2r2.rst.renderer import (
    RestRenderer,
    escape_role_title,
    flatten_to_plain_text,
)
from m2r2.sphinx.constants import DOCUMENT_ANCHOR_ROLE_NAME, IMAGE_ANCHOR_ROLE_NAME

if TYPE_CHECKING:
    from docutils import nodes
    from mistune.core import BlockState


class SphinxRestRenderer(RestRenderer):
    """Render Markdown inside a Sphinx document."""

    def __init__(
        self,
        document: nodes.document,
        source_path: str,
        *,
        parse_relative_links: bool,
        anonymous_references: bool,
        use_mermaid: bool,
    ) -> None:
        self.markdown_source_directory = os.path.dirname(os.path.abspath(source_path))
        self.sphinx_document_directory = os.path.dirname(
            os.path.abspath(document["source"])
        )
        super().__init__(
            parse_relative_links=parse_relative_links,
            anonymous_references=anonymous_references,
            use_mermaid=use_mermaid,
            existing_substitutions=document.substitution_defs,
        )

    def render_unlabeled_code_block(self) -> str:
        """Open an unlabeled literal block using Sphinx's default lexer."""
        return "\n::\n\n"

    def render_linked_text(
        self, token: dict[str, Any], state: BlockState, emphasis_marker: str
    ) -> str:
        """Render local anchor links as Sphinx cross-references."""
        link_destination = token["attrs"]["url"]
        destination_parts = urlparse(link_destination)
        links_to_project_anchor = (
            destination_parts.scheme == ""
            and destination_parts.netloc == ""
            and destination_parts.fragment != ""
            and (destination_parts.path == "" or self.parse_relative_links)
        )
        if links_to_project_anchor:
            link_label_tokens = token["children"]
            if len(link_label_tokens) == 1 and link_label_tokens[0]["type"] == "image":
                document_relative_image_token = self.resolve_image_token(
                    link_label_tokens[0]
                )
                image_substitution_name = self.define_image_substitution(
                    document_relative_image_token, state, None
                )
                return (
                    rf"\ :{IMAGE_ANCHOR_ROLE_NAME}:`"
                    rf"{image_substitution_name} <{link_destination}>`\ "
                )
            escaped_link_label = escape_role_title(flatten_to_plain_text(token))
            return (
                rf"\ :{DOCUMENT_ANCHOR_ROLE_NAME}:`"
                rf"{escaped_link_label} <{link_destination}>`\ "
            )
        return super().render_linked_text(token, state, emphasis_marker)

    def resolve_image_token(self, image_token: dict[str, Any]) -> dict[str, Any]:
        """Copy an image token with its path resolved for the Sphinx document."""
        image_uri = image_token["attrs"]["url"]
        document_relative_image_uri = self.resolve_image_path(image_uri)
        return {
            **image_token,
            "attrs": {
                **image_token["attrs"],
                "url": document_relative_image_uri,
            },
        }

    def resolve_image_path(self, image_uri: str) -> str:
        """Translate Markdown image paths to paths relative to the Sphinx document."""
        image_url_parts = urlsplit(image_uri)
        if (
            image_url_parts.scheme != ""
            or image_url_parts.netloc != ""
            or image_url_parts.path == ""
            or image_uri.startswith("/")
        ):
            return image_uri
        document_relative_image_path = os.path.relpath(
            os.path.join(self.markdown_source_directory, image_url_parts.path),
            self.sphinx_document_directory,
        ).replace(os.sep, "/")
        return image_url_parts._replace(path=document_relative_image_path).geturl()

    def render_image(
        self,
        token: dict[str, Any],
        state: BlockState,
        target: str | None,
        *,
        inline: bool = True,
    ) -> str:
        """Render an image with its path resolved for the Sphinx document."""
        original_image_uri = token["attrs"]["url"]
        document_relative_image_token = self.resolve_image_token(token)
        document_relative_image_uri = document_relative_image_token["attrs"]["url"]
        if target == original_image_uri:
            target = document_relative_image_uri
        return super().render_image(
            document_relative_image_token, state, target, inline=inline
        )


class SphinxM2R2(BaseM2R2):
    """Convert Markdown using a Sphinx document's configuration and context."""

    def __init__(
        self, document: nodes.document, *, source_path: str | None = None
    ) -> None:
        sphinx_config = document.settings.env.config
        markdown_source_path = (
            document["source"] if source_path is None else source_path
        )
        renderer = SphinxRestRenderer(
            document,
            markdown_source_path,
            parse_relative_links=sphinx_config.m2r_parse_relative_links,
            anonymous_references=sphinx_config.m2r_anonymous_references,
            use_mermaid=sphinx_config.m2r_use_mermaid,
        )
        super().__init__(
            renderer=renderer,
            plugins=None,
            no_underscore_emphasis=sphinx_config.m2r_no_underscore_emphasis,
            inline_math=sphinx_config.m2r_inline_math,
        )
