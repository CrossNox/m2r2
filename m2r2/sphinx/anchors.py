"""Resolve Markdown anchor links within Sphinx projects."""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Iterable
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from docutils import nodes, utils
from sphinx import addnodes
from sphinx.util import docname_join, logging
from sphinx.util.nodes import make_refnode, split_explicit_title

from m2r2.sphinx.constants import DOCUMENT_ANCHOR_ROLE_NAME, IMAGE_ANCHOR_ROLE_NAME

if TYPE_CHECKING:
    from docutils.parsers.rst.states import Inliner
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment

logger = logging.getLogger(__name__)


class VisibleHtmlTextParser(HTMLParser):
    """Collect heading text from raw HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visible_text_parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.visible_text_parts.append(data)


def slugify_heading_like_github(title: str) -> str:
    """Generate a GitHub-style heading slug without a collision suffix."""
    slug_characters = "".join(
        character
        for character in title.lower()
        if character in (" ", "-")
        or unicodedata.category(character).startswith(("L", "M", "N"))
        or unicodedata.category(character) == "Pc"
    )
    return slug_characters.replace(" ", "-")


def assign_github_heading_slugs(titles: Iterable[str]) -> list[str]:
    """Assign unique GitHub-style slugs to headings in document order.

    Append numeric suffixes to resolve collisions with previously assigned slugs.
    """
    slug_collision_counts: dict[str, int] = {}
    slugs = []

    for title in titles:
        base_slug = slugify_heading_like_github(title)
        unique_slug = base_slug
        while unique_slug in slug_collision_counts:
            slug_collision_counts[base_slug] += 1
            unique_slug = f"{base_slug}-{slug_collision_counts[base_slug]}"
        slug_collision_counts[unique_slug] = 0
        slugs.append(unique_slug)

    return slugs


def get_or_create_document_anchor_map(
    env: BuildEnvironment,
) -> dict[str, dict[str, str]]:
    """Get or create the map from document anchors to element ids."""
    try:
        return env.m2r2_document_anchors
    except AttributeError:
        env.m2r2_document_anchors = {}
        return env.m2r2_document_anchors


def get_or_create_document_anchor_references(
    env: BuildEnvironment,
) -> dict[str, dict[tuple[str, str], str | None]]:
    """Return the anchor references and their last resolved IDs for each document."""
    try:
        return env.m2r2_document_anchor_references
    except AttributeError:
        env.m2r2_document_anchor_references = {}
        return env.m2r2_document_anchor_references


def normalize_target_document_path(
    link_source_docname: str, destination_path: str
) -> str:
    """Resolve an encoded link path relative to its source document."""
    if destination_path == "":
        return link_source_docname
    return docname_join(
        link_source_docname, os.path.splitext(unquote(destination_path))[0]
    )


def find_documents_with_changed_anchor_references(
    app: Sphinx, env: BuildEnvironment
) -> list[str]:
    """Find documents whose anchor links need updating after a target changes."""
    anchors = get_or_create_document_anchor_map(env)
    documents_to_rewrite = set()
    for docname, references in get_or_create_document_anchor_references(env).items():
        for (target_docname, slug), previous_element_id in references.items():
            element_id = anchors.get(target_docname, {}).get(slug)
            if element_id != previous_element_id:
                documents_to_rewrite.add(docname)
                references[target_docname, slug] = element_id

    if len(documents_to_rewrite) > 0:
        logger.debug("m2r2 updating anchor links in %s", sorted(documents_to_rewrite))
    return sorted(documents_to_rewrite)


def record_document_anchors(app: Sphinx, doctree: nodes.document) -> None:
    """Map a document's anchor names to its element IDs."""
    sections = list(doctree.findall(nodes.section))
    titles = [extract_visible_heading_text(section[0]) for section in sections]
    slugs = assign_github_heading_slugs(titles)
    anchors = {slug: section["ids"][0] for slug, section in zip(slugs, sections)}
    for element_id in doctree.ids:
        anchors.setdefault(element_id, element_id)
    for name, is_explicit in doctree.nametypes.items():
        if is_explicit:
            element_id = doctree.nameids[name]
            anchors[name] = element_id
            anchors[element_id] = element_id
    get_or_create_document_anchor_map(app.env)[app.env.docname] = anchors


def extract_visible_heading_text(node: nodes.Node) -> str:
    """Return heading text without HTML tags."""
    if isinstance(node, nodes.raw):
        html_text_parser = VisibleHtmlTextParser()
        html_text_parser.feed(node.astext())
        html_text_parser.close()
        return "".join(html_text_parser.visible_text_parts)
    if isinstance(node, nodes.Text):
        return node.astext()
    return "".join(extract_visible_heading_text(child) for child in node.children)


def forget_document_anchors(app: Sphinx, env: BuildEnvironment, docname: str) -> None:
    """Remove a document's cached anchors and anchor references."""
    get_or_create_document_anchor_map(env).pop(docname, None)
    get_or_create_document_anchor_references(env).pop(docname, None)


def merge_document_anchors(
    app: Sphinx,
    env: BuildEnvironment,
    docnames: Iterable[str],
    other: BuildEnvironment,
) -> None:
    """Merge anchor data collected by a parallel build worker."""
    anchors = get_or_create_document_anchor_map(env)
    other_anchors = get_or_create_document_anchor_map(other)
    references = get_or_create_document_anchor_references(env)
    other_references = get_or_create_document_anchor_references(other)
    for docname in docnames:
        anchors[docname] = other_anchors[docname]
        references[docname] = other_references.get(docname, {})


def create_document_anchor_reference(
    name: str,
    rawtext: str,
    text: str,
    lineno: int,
    inliner: Inliner,
    options: dict[str, Any] | None = None,
    content: list[str] | None = None,
) -> tuple[list[nodes.Node], list[nodes.system_message]]:
    """Create a pending anchor reference with its source document context."""
    unescaped_text = utils.unescape(text)
    has_title, role_title, link_destination = split_explicit_title(unescaped_text)
    destination_path, _, anchor_fragment = link_destination.partition("#")

    env = inliner.document.settings.env
    link_source_docname = env.docname

    if destination_path != "":
        markdown_source_path = inliner.reporter.get_source_and_line(lineno)[0]
        if markdown_source_path is None:
            raise ValueError("Cannot resolve an anchor link without a source path")

        source_relative_path = os.path.relpath(markdown_source_path, env.srcdir)
        link_source_docname = os.path.splitext(source_relative_path)[0].replace(
            os.sep, "/"
        )

    target_docname = normalize_target_document_path(
        link_source_docname, destination_path
    )

    references_by_document = get_or_create_document_anchor_references(env)
    document_anchor_references = references_by_document.setdefault(env.docname, {})
    document_anchor_references[target_docname, unquote(anchor_fragment)] = None

    pending_anchor_reference = addnodes.pending_xref(
        rawtext,
        refdomain="",
        reftype=name,
        reftarget=link_destination,
        refexplicit=has_title,
        refdoc=env.docname,
        refsource=link_source_docname,
    )

    if name == IMAGE_ANCHOR_ROLE_NAME:
        image_substitution_definition = inliner.document.substitution_defs[role_title]
        image_node = next(image_substitution_definition.findall(nodes.image)).deepcopy()
        pending_anchor_reference += image_node
    else:
        pending_anchor_reference += nodes.inline(role_title, role_title)

    return [pending_anchor_reference], []


def resolve_document_anchor_reference(
    app: Sphinx,
    env: BuildEnvironment,
    node: addnodes.pending_xref,
    contnode: nodes.Element,
) -> nodes.Element | None:
    """Resolve an anchor reference to its target element.

    Warn if the target is missing and return the link content without a hyperlink.
    """
    if node["reftype"] not in (DOCUMENT_ANCHOR_ROLE_NAME, IMAGE_ANCHOR_ROLE_NAME):
        return None

    destination_path, _, anchor_fragment = node["reftarget"].partition("#")
    anchor_slug = unquote(anchor_fragment)
    containing_docname = node["refdoc"]
    target_docname = normalize_target_document_path(node["refsource"], destination_path)

    if target_docname not in env.found_docs:
        logger.warning(
            "m2r2 found no document %r for the link to %r",
            target_docname,
            node["reftarget"],
            location=node,
            type="m2r2",
            subtype="anchor",
        )
        return contnode

    element_id = get_or_create_document_anchor_map(env)[target_docname].get(anchor_slug)
    if element_id is None:
        logger.warning(
            "m2r2 found no anchor #%s in %r",
            anchor_slug,
            target_docname,
            location=node,
            type="m2r2",
            subtype="anchor",
        )
        return contnode

    return make_refnode(
        app.builder, containing_docname, target_docname, element_id, contnode
    )


def register_document_anchors(app: Sphinx) -> None:
    """Register Sphinx roles and event handlers for anchor links."""
    app.add_role(DOCUMENT_ANCHOR_ROLE_NAME, create_document_anchor_reference)
    app.add_role(IMAGE_ANCHOR_ROLE_NAME, create_document_anchor_reference)
    app.connect("doctree-read", record_document_anchors)
    app.connect("env-purge-doc", forget_document_anchors)
    app.connect("env-merge-info", merge_document_anchors)
    app.connect("env-updated", find_documents_with_changed_anchor_references)
    app.connect("missing-reference", resolve_document_anchor_reference)
