"""Resolve links to document anchors and GitHub-style heading anchors.

Markdown authors link to a heading with the anchor GitHub gives it, such as
``#bugfixes-1`` for the second "Bugfixes". docutils and Sphinx name sections
differently. Record each document's ids and GitHub heading anchors so links
can point to their targets.
"""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from docutils import nodes, utils
from sphinx import addnodes
from sphinx.util import docname_join, logging
from sphinx.util.nodes import make_refnode, split_explicit_title

from m2r2.rst.renderer import extract_visible_html_text
from m2r2.sphinx.constants import DOCUMENT_ANCHOR_ROLE_NAME, IMAGE_ANCHOR_ROLE_NAME

if TYPE_CHECKING:
    from docutils.parsers.rst.states import Inliner
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment

logger = logging.getLogger(__name__)

#: Unicode categories GitHub keeps in an anchor: letters, marks, numbers, and
#: connector punctuation such as the underscore.
_KEPT_CATEGORY_PREFIXES = ("L", "M", "N")
_KEPT_CATEGORIES = ("Pc",)


def slugify_heading_like_github(title: str) -> str:
    """Turn the text of a heading into the anchor GitHub gives it, before numbering."""
    kept = "".join(
        character
        for character in title.lower()
        if character in (" ", "-")
        or unicodedata.category(character).startswith(_KEPT_CATEGORY_PREFIXES)
        or unicodedata.category(character) in _KEPT_CATEGORIES
    )
    return kept.replace(" ", "-")


def assign_github_heading_slugs(titles: Iterable[str]) -> list[str]:
    """Name each heading of a document the way GitHub does, numbering repeats.

    The second "Bugfixes" becomes ``bugfixes-1``. A number GitHub would give
    that another heading already has as its own anchor is skipped.
    """
    occurrences: dict[str, int] = {}
    slugs = []
    for title in titles:
        original = slugify_heading_like_github(title)
        slug = original
        while slug in occurrences:
            occurrences[original] += 1
            slug = f"{original}-{occurrences[original]}"
        occurrences[slug] = 0
        slugs.append(slug)
    return slugs


def get_or_create_document_anchor_map(
    env: BuildEnvironment,
) -> dict[str, dict[str, str]]:
    """Get or create the map from document anchors to element ids."""
    if not hasattr(env, "m2r2_document_anchors"):
        env.m2r2_document_anchors = {}
    return env.m2r2_document_anchors


def get_or_create_document_anchor_references(
    env: BuildEnvironment,
) -> dict[str, dict[tuple[str, str], str | None]]:
    """Track the resolved element id of each document's anchor references."""
    if not hasattr(env, "m2r2_document_anchor_references"):
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


def find_source_docname_for_link(
    env: BuildEnvironment, link_source_path: str | os.PathLike[str]
) -> str:
    """Name the source file that holds a link relative to the Sphinx source root."""
    source_relative_path = os.path.relpath(link_source_path, env.srcdir)
    return os.path.splitext(source_relative_path)[0].replace(os.sep, "/")


def find_documents_with_changed_anchor_references(
    app: Sphinx, env: BuildEnvironment
) -> list[str]:
    """Select pages to rewrite after all target anchor maps have been collected."""
    anchors = get_or_create_document_anchor_map(env)
    documents_to_rewrite = set()
    for docname, references in get_or_create_document_anchor_references(env).items():
        for (target_docname, slug), previous_id in references.items():
            element_id = anchors.get(target_docname, {}).get(slug)
            if element_id != previous_id:
                documents_to_rewrite.add(docname)
                references[target_docname, slug] = element_id

    if len(documents_to_rewrite) > 0:
        logger.debug("m2r2 updating anchor links in %s", sorted(documents_to_rewrite))
    return sorted(documents_to_rewrite)


def record_document_anchors(app: Sphinx, doctree: nodes.document) -> None:
    """Record the ids and GitHub heading anchors of the document just read."""
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
        return extract_visible_html_text(node.astext())
    if isinstance(node, nodes.Text):
        return node.astext()
    return "".join(extract_visible_heading_text(child) for child in node.children)


def forget_document_anchors(app: Sphinx, env: BuildEnvironment, docname: str) -> None:
    """Drop the anchors of a document Sphinx is about to read again."""
    get_or_create_document_anchor_map(env).pop(docname, None)
    get_or_create_document_anchor_references(env).pop(docname, None)


def merge_document_anchors(
    app: Sphinx,
    env: BuildEnvironment,
    docnames: Iterable[str],
    other: BuildEnvironment,
) -> None:
    """Take the anchors a worker process of a parallel build recorded."""
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
    """Create a reference that resolves from a document anchor."""
    has_title, role_title, link_destination = split_explicit_title(utils.unescape(text))
    destination_path, _, anchor_fragment = link_destination.partition("#")
    env = inliner.document.settings.env
    link_source_docname = env.docname
    if destination_path != "":
        markdown_source_path = inliner.reporter.get_source_and_line(lineno)[0]
        if markdown_source_path is None:
            raise ValueError("Cannot resolve an anchor link without a source path")
        link_source_docname = find_source_docname_for_link(env, markdown_source_path)
    target_docname = normalize_target_document_path(
        link_source_docname, destination_path
    )
    document_anchor_references = get_or_create_document_anchor_references(
        env
    ).setdefault(env.docname, {})
    document_anchor_references[target_docname, unquote(anchor_fragment)] = None
    pending_anchor_reference = addnodes.pending_xref(
        rawtext,
        refdomain="",
        reftype=name,
        reftarget=link_destination,
        refexplicit=has_title,
        refdoc=inliner.document.settings.env.docname,
        refsource=link_source_docname,
    )
    if name == IMAGE_ANCHOR_ROLE_NAME:
        image_substitution_definition = inliner.document.substitution_defs[role_title]
        pending_anchor_reference += next(
            image_substitution_definition.findall(nodes.image)
        ).deepcopy()
    else:
        pending_anchor_reference += nodes.inline(role_title, role_title)
    return [pending_anchor_reference], []


def resolve_document_anchor_reference(
    app: Sphinx,
    env: BuildEnvironment,
    node: addnodes.pending_xref,
    contnode: nodes.Element,
) -> nodes.Element | None:
    """Point a link at the element whose document anchor it names.

    A link naming a document or an anchor the project lacks gets a warning and
    renders as its text alone.
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
    """Register the role and handlers that resolve document anchors."""
    app.add_role(DOCUMENT_ANCHOR_ROLE_NAME, create_document_anchor_reference)
    app.add_role(IMAGE_ANCHOR_ROLE_NAME, create_document_anchor_reference)
    app.connect("doctree-read", record_document_anchors)
    app.connect("env-purge-doc", forget_document_anchors)
    app.connect("env-merge-info", merge_document_anchors)
    app.connect("env-updated", find_documents_with_changed_anchor_references)
    app.connect("missing-reference", resolve_document_anchor_reference)
