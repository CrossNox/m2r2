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

from m2r2.rst.renderer import DOCUMENT_ANCHOR_ROLE_NAME, extract_visible_html_text

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


def normalize_target_document_path(source_docname: str, path: str) -> str:
    """Resolve an encoded link path relative to its source document."""
    if path == "":
        return source_docname
    return docname_join(source_docname, os.path.splitext(unquote(path))[0])


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
    has_title, title, target = split_explicit_title(utils.unescape(text))
    path, _, fragment = target.partition("#")
    env = inliner.document.settings.env
    target_docname = normalize_target_document_path(env.docname, path)
    references = get_or_create_document_anchor_references(env).setdefault(
        env.docname, {}
    )
    references[target_docname, unquote(fragment)] = None
    reference = addnodes.pending_xref(
        rawtext,
        refdomain="",
        reftype=DOCUMENT_ANCHOR_ROLE_NAME,
        reftarget=target,
        refexplicit=has_title,
        refdoc=inliner.document.settings.env.docname,
    )
    reference += nodes.inline(title, title)
    return [reference], []


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
    if node["reftype"] != DOCUMENT_ANCHOR_ROLE_NAME:
        return None

    path, _, fragment = node["reftarget"].partition("#")
    slug = unquote(fragment)
    source_docname = node["refdoc"]
    target_docname = normalize_target_document_path(source_docname, path)

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

    element_id = get_or_create_document_anchor_map(env)[target_docname].get(slug)
    if element_id is None:
        logger.warning(
            "m2r2 found no anchor #%s in %r",
            slug,
            target_docname,
            location=node,
            type="m2r2",
            subtype="anchor",
        )
        return contnode

    return make_refnode(
        app.builder, source_docname, target_docname, element_id, contnode
    )


def register_document_anchors(app: Sphinx) -> None:
    """Register the role and handlers that resolve document anchors."""
    app.add_role(DOCUMENT_ANCHOR_ROLE_NAME, create_document_anchor_reference)
    app.connect("doctree-read", record_document_anchors)
    app.connect("env-purge-doc", forget_document_anchors)
    app.connect("env-merge-info", merge_document_anchors)
    app.connect("env-updated", find_documents_with_changed_anchor_references)
    app.connect("missing-reference", resolve_document_anchor_reference)
